from __future__ import annotations

from datetime import datetime
from functools import reduce
from typing import Any, Dict, Optional

import numpy as np
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy
from pandas import DataFrame


class VolatilityAdaptiveSpotV3(IStrategy):
    """A basic spot strategy demonstrating Freqtrade interface v3."""

    INTERFACE_VERSION = 3

    can_short: bool = False
    timeframe: str = "1h"
    startup_candle_count: int = 200

    minimal_roi: Dict[int, float] = {
        0: 0.10,
        720: 0.05,
        1440: 0,
    }

    stoploss: float = -0.10
    trailing_stop: bool = True
    trailing_stop_positive: float = 0.02
    trailing_stop_positive_offset: float = 0.04
    trailing_only_offset_is_reached: bool = True

    position_adjustment_enable: bool = True

    protections = [
        {"method": "CooldownPeriod", "value": 60},
        {
            "method": "MaxDrawdown",
            "lookback_period": 1440,
            "trade_limit": 20,
            "stop_duration": 60,
            "max_allowed_drawdown": 0.2,
        },
        {
            "method": "StoplossGuard",
            "lookback_period": 60,
            "trade_limit": 2,
            "stop_duration": 60,
            "only_per_pair": True,
        },
    ]

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "emergencysell": "market",
        "stoploss": "market",
    }

    order_time_in_force = {"entry": "GTC", "exit": "GTC"}
    unfilledtimeout = {"entry": 20, "exit": 10, "unit": "minutes"}

    def populate_indicators(self, dataframe: DataFrame, metadata: Dict[str, Any]) -> DataFrame:
        dataframe["ema_fast"] = dataframe["close"].ewm(span=12, adjust=False).mean()
        dataframe["ema_slow"] = dataframe["close"].ewm(span=26, adjust=False).mean()

        delta = dataframe["close"].diff()
        up = delta.clip(lower=0)
        down = -delta.clip(upper=0)
        roll_up = up.ewm(alpha=1 / 14, adjust=False).mean()
        roll_down = down.ewm(alpha=1 / 14, adjust=False).mean()
        rs = roll_up / roll_down
        dataframe["rsi"] = 100 - (100 / (1 + rs))

        hl = dataframe["high"] - dataframe["low"]
        hc = (dataframe["high"] - dataframe["close"].shift()).abs()
        lc = (dataframe["low"] - dataframe["close"].shift()).abs()
        tr = reduce(np.maximum, [hl, hc, lc])
        dataframe["atr"] = tr.ewm(span=14, adjust=False).mean()

        dataframe["obv"] = (np.sign(dataframe["close"].diff()) * dataframe["volume"]).fillna(0).cumsum()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: Dict[str, Any]) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["ema_fast"] > dataframe["ema_slow"]) &
                (dataframe["rsi"].shift(1) < 30) &
                (dataframe["rsi"] > dataframe["rsi"].shift(1)) &
                (dataframe["obv"] > dataframe["obv"].rolling(5).mean())
            ),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: Dict[str, Any]) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["ema_fast"] < dataframe["ema_slow"]) |
                (dataframe["rsi"] > 70)
            ),
            "exit_long",
        ] = 1
        return dataframe

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        **kwargs: Any,
    ) -> bool:
        """
        Validate whether current market conditions allow opening a new trade.

        A trade will only be entered when all of the following conditions are
        met:

        * The spread between the best ask and bid is below 1 % of the ask
          price, indicating a reasonably tight market.
        * The latest candle volume is higher than the rolling 24-period
          average volume, signalling increased market participation.
        * The current time in UTC falls between 06:00 and 18:00. This avoids
          thinly traded hours that can introduce excessive slippage.

        Args:
            pair: Trading pair being evaluated.
            order_type: Type of order (limit/market).
            amount: Proposed stake amount.
            rate: Proposed rate for the order.
            time_in_force: Order's time in force.
            **kwargs: Additional keyword arguments passed by Freqtrade.

        Returns:
            True if all requirements are satisfied, otherwise False.
        """

        ticker = self.dp.ticker(pair) if hasattr(self.dp, "ticker") else None
        dataframe = self.dp.get_analyzed_dataframe(pair, self.timeframe)

        if not ticker or dataframe is None or dataframe.empty:
            return False

        best_ask = ticker.get("ask")
        best_bid = ticker.get("bid")

        if not best_ask or not best_bid:
            return False

        spread = (best_ask - best_bid) / best_ask

        recent_volume = dataframe["volume"].iloc[-1]
        avg_volume = dataframe["volume"].rolling(24).mean().iloc[-1]

        hour = datetime.utcnow().hour

        if (
            spread < 0.01
            and recent_volume > avg_volume
            and 6 <= hour < 18
        ):
            return True

        return False

    def confirm_trade_exit(
        self,
        pair: str,
        trade: Trade,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        **kwargs: Any,
    ) -> bool:
        return True

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs: Any,
    ) -> float:
        dataframe = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return self.stoploss
        atr = dataframe["atr"].iloc[-1]
        if atr <= 0:
            return self.stoploss
        stop_price = current_rate - 2 * atr
        return (stop_price - current_rate) / current_rate

    def adjust_trade_position(
        self,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs: Any,
    ) -> Optional[float]:
        max_adds = 2
        dca_spacing = 0.03
        if trade.nr_of_successful_entries >= max_adds:
            return None
        if current_profit < -(dca_spacing * (trade.nr_of_successful_entries + 1)):
            return trade.stake_amount
        return None
