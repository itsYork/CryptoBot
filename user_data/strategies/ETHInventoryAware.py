from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from pandas import DataFrame
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, merge_informative_pair

from utils.indicators import ema, adx, atr, donchian, vwap, anchored_vwap

logger = logging.getLogger(__name__)


class ETHInventoryAware(IStrategy):
    """Inventory aware ETH/USDT strategy for Kraken."""

    timeframe = '5m'
    informative_timeframe = '1h'
    can_short = False
    process_only_new_candles = True
    startup_candle_count = 240
    minimal_roi = {"0": 10}
    stoploss = -0.20
    position_adjustment_enable = True

    # internal state persistence
    state_file = Path('user_data') / 'ETHInventoryAware_state.json'
    last_exit_price: float | None = None

    def informative_pairs(self):
        return [(pair, self.informative_timeframe) for pair in self.dp.current_whitelist()]

    def _load_state(self) -> None:
        if self.state_file.exists():
            data = json.loads(self.state_file.read_text())
            self.last_exit_price = data.get('last_exit_price')

    def _save_state(self) -> None:
        self.state_file.write_text(json.dumps({'last_exit_price': self.last_exit_price}))

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata['pair']
        inf = self.dp.get_pair_dataframe(pair=pair, timeframe=self.informative_timeframe)
        inf['ema200'] = ema(inf['close'], 200)
        inf['ema200_slope'] = inf['ema200'].diff()
        inf['adx'] = adx(inf, 14)
        inf['atr'] = atr(inf, 14)
        inf['atr_pct'] = inf['atr'] / inf['close']
        inf['vwap'] = vwap(inf)
        inf['anchored_vwap'] = anchored_vwap(inf)
        dataframe = merge_informative_pair(dataframe, inf, self.timeframe, self.informative_timeframe, ffill=True)
        dc = donchian(dataframe, 20)
        dataframe = pd.concat([dataframe, dc], axis=1)
        dataframe['regime'] = ((dataframe['ema200_slope_1h'] > 0) & (dataframe['adx_1h'] >= 18)).astype(int)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe['regime'] == 1) &
            (
                (dataframe['close'] > dataframe['donchian_high']) |
                (dataframe['close'] > dataframe['anchored_vwap_1h'])
            ),
            ['enter_long', 'enter_tag']
        ] = (1, 'trend')

        step = dataframe[['atr_1h']].apply(lambda x: max(0.75 * x['atr_1h'], 0.007 * dataframe['close']), axis=1)
        dataframe.loc[
            (dataframe['regime'] == 0) &
            (dataframe['close'] < dataframe['vwap_1h'] - step),
            ['enter_long', 'enter_tag']
        ] = (1, 'range')
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        tp = dataframe[['atr_1h']].apply(lambda x: max(1.3 * x['atr_1h'], 0.011 * dataframe['close']), axis=1)
        dataframe.loc[
            (dataframe['enter_long'] > 0) &
            (dataframe['close'] > dataframe['open'] + tp),
            'exit_long'
        ] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time, current_rate, proposed_stake, **kwargs) -> float:
        balance = self.wallets.get_total(self.stake_currency)
        risk_budget = 0.006 * balance
        atr_val = self.get_indicator_value(pair, 'atr_1h')
        unit_risk = max(0.8 * atr_val, 0.012 * current_rate)
        stake = risk_budget / unit_risk
        exposure_cap = 0.3 * balance
        stake = min(stake, exposure_cap)
        return stake

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                             time_in_force: str, **kwargs) -> bool:
        ticker = self.dp.ticker(pair)
        spread = (ticker['ask'] - ticker['bid']) / ticker['bid']
        if spread > 0.0015:
            logger.info('spread_too_wide', extra={'pair': pair, 'spread': spread})
            return False
        last_close = self.get_indicator_value(pair, 'close')
        if rate > last_close * 1.0015:
            logger.info('slippage_guard', extra={'pair': pair, 'rate': rate, 'close': last_close})
            return False
        if self.last_exit_price:
            atr_val = self.get_indicator_value(pair, 'atr_1h')
            if rate < self.last_exit_price + 0.4 * atr_val:
                return False
        return True

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str,
                           amount: float, rate: float, time_in_force: str, **kwargs) -> bool:
        # allow all exits
        return True

    def custom_entry_price(self, pair: str, current_time, proposed_rate: float, entry_tag: str, **kwargs) -> float:
        return proposed_rate

    def custom_exit_price(self, pair: str, trade: Trade, current_time, proposed_rate: float, **kwargs) -> float:
        return proposed_rate

    def adjust_trade_position(self, trade: Trade, current_time, current_rate, current_profit, **kwargs) -> float:
        atr_val = self.get_indicator_value(trade.pair, 'atr_1h')
        if not trade.is_open:
            return 0
        add_count = trade.user_data.get('add_count', 0) if trade.user_data else 0
        last_add = trade.user_data.get('last_add', trade.open_rate) if trade.user_data else trade.open_rate
        if add_count >= 4:
            return 0
        if current_rate < last_add - 0.7 * atr_val:
            stake = self.custom_stake_amount(trade.pair, current_time, current_rate, 0)
            stake *= 0.8 ** add_count
            trade.user_data = {'add_count': add_count + 1, 'last_add': current_rate}
            return stake
        return 0

    def on_trade_exit(self, trade: Trade, order_type: str, amount: float, rate: float, **kwargs) -> None:
        self.last_exit_price = rate
        self._save_state()

    def on_strategy_start(self, **kwargs) -> None:
        self._load_state()

    def order_types(self) -> Dict[str, str]:
        return {'entry': 'limit', 'exit': 'limit', 'emergency_exit': 'market'}

    def order_time_in_force(self, trade: Trade, order_type: str, **kwargs) -> str:
        return 'gtc'
