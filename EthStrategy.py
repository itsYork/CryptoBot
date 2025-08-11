"""Advanced ETH/USDT strategy implementing risk-aware adaptive logic.

This module follows the specification provided in the ETH Strategy
Instruction Set.  It includes configuration constants, persistence,
indicator calculations and a simplified strategy class intended for
usage with Freqtrade or as a stand‑alone loop.  The implementation is
not intended to be production ready but provides a framework that
mirrors the pseudocode specification.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import ccxt
import pandas as pd


# ---------------------------------------------------------------------------
# 1. Configuration constants
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Config:
    """Static configuration used across the strategy.

    Values use fraction notation for percentages (e.g. 0.006 == 0.6%).
    """

    exchange_name: str = "kraken"
    pair: str = "ETH/USDT"
    equity_start: float = 8000.0
    exposure_cap_notional_pct: float = 0.30
    target_alloc_pct: float = 0.50
    target_band: float = 0.08
    base_risk_pct: float = 0.006  # 0.60 percent
    max_total_risk_mult: float = 2.0
    max_adds: int = 4
    add_size_decay: float = 0.80
    add_spacing_atr: float = 0.70
    grid_step_min_pct: float = 0.007
    trend_tp_floor_pct: float = 0.011
    range_tp_floor_pct: float = 0.008
    trail_arm_atr: float = 1.00
    trail_dist_trend_atr: float = 0.80
    trail_dist_range_atr: float = 1.10
    no_rebuy_buffer_atr: float = 0.40
    time_exit_days: int = 4
    cooldown_candles_1h: int = 3
    spread_max_bps: int = 15
    slippage_max_bps: int = 10
    unfilled_timeout_sec: int = 90
    fee_buffer_pct: float = 0.001


# ---------------------------------------------------------------------------
# 2. Persistent state handling
# ---------------------------------------------------------------------------


STATE_PATH = os.path.join(os.path.dirname(__file__), "state.json")


@dataclass
class StateStore:
    """Holds state that must persist across restarts."""

    last_regime: Optional[str] = None
    last_exit_price: Optional[float] = None
    last_grid_anchor: Optional[float] = None
    trail_active: bool = False
    trail_anchor_price: Optional[float] = None
    trail_dist_atr: Optional[float] = None
    add_count: int = 0
    last_add_price: Optional[float] = None
    bootstrap_state: str = "PENDING"  # or "DONE"
    daily_loss_realized: float = 0.0
    open_order_intent_hash: Optional[str] = None
    entry_price: Optional[float] = None

    @classmethod
    def load(cls) -> "StateStore":
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return cls(**data)
        return cls()

    def save(self) -> None:
        with open(STATE_PATH, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# 3. Data access helpers (placeholders for exchange queries)
# ---------------------------------------------------------------------------


class Data:
    """Container for data loading helpers using ccxt."""

    exchange: ccxt.kraken = ccxt.kraken(
        {
            "enableRateLimit": True,
            "apiKey": os.getenv("KRAKEN_API_KEY", ""),
            "secret": os.getenv("KRAKEN_API_SECRET", ""),
        }
    )

    @staticmethod
    def load_candles(pair: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
        """Return OHLCV candles for the pair/timeframe."""

        try:
            candles = Data.exchange.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
        except Exception:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume", "time"])
        df = pd.DataFrame(candles, columns=["time", "open", "high", "low", "close", "volume"])
        return df[["open", "high", "low", "close", "volume", "time"]]

    @staticmethod
    def load_orderbook_top(pair: str) -> Tuple[float, float, float]:
        """Return best bid, ask and spread for the pair."""

        try:
            ob = Data.exchange.fetch_order_book(pair, limit=1)
            bid = ob["bids"][0][0] if ob["bids"] else 0.0
            ask = ob["asks"][0][0] if ob["asks"] else 0.0
            spread = ask - bid
            return bid, ask, spread
        except Exception:
            return 0.0, 0.0, 0.0

    @staticmethod
    def load_exchange_meta(pair: str) -> Dict[str, float]:
        """Return precision, min notional and fees for the pair."""

        try:
            market = Data.exchange.market(pair)
            precision = market.get("precision", {})
            limits = market.get("limits", {})
            min_notional = limits.get("cost", {}).get("min", 0.0)
            return {
                "price_precision": precision.get("price", 2),
                "qty_precision": precision.get("amount", 6),
                "min_notional": min_notional or 10.0,
                "fees": market.get("taker", 0.0016),
            }
        except Exception:
            return {
                "price_precision": 2,
                "qty_precision": 6,
                "min_notional": 10.0,
                "fees": 0.0016,
            }

    @staticmethod
    def load_balances() -> Dict[str, float]:
        """Return balances from the exchange."""

        try:
            bal = Data.exchange.fetch_balance()
            return {
                "usdt_free": bal.get("USDT", {}).get("free", 0.0),
                "eth_free": bal.get("ETH", {}).get("free", 0.0),
                "usdt_locked": bal.get("USDT", {}).get("used", 0.0),
                "eth_locked": bal.get("ETH", {}).get("used", 0.0),
            }
        except Exception:
            return {
                "usdt_free": 0.0,
                "eth_free": 0.0,
                "usdt_locked": 0.0,
                "eth_locked": 0.0,
            }

    @staticmethod
    def load_open_orders(pair: str) -> List[Dict]:
        try:
            return Data.exchange.fetch_open_orders(symbol=pair)
        except Exception:
            return []

    @staticmethod
    def server_time() -> datetime:
        try:
            ts = Data.exchange.fetch_time()
        except Exception:
            ts = Data.exchange.milliseconds()
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc)


# ---------------------------------------------------------------------------
# 4. Indicator calculations
# ---------------------------------------------------------------------------


class Indicators:
    """Indicator calculation helpers using pandas."""

    @staticmethod
    def ema(series: pd.Series, period: int) -> pd.Series:
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        high_low = high - low
        high_close = (high - close.shift()).abs()
        low_close = (low - close.shift()).abs()
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.rolling(window=period, min_periods=period).mean()

    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        # Simplified ADX implementation.
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        tr = Indicators.atr(high, low, close, period)
        plus_di = 100 * (plus_dm.ewm(alpha=1 / period).mean() / tr)
        minus_di = 100 * (minus_dm.ewm(alpha=1 / period).mean() / tr)
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx = dx.ewm(alpha=1 / period).mean()
        return adx

    @staticmethod
    def vwap(candles: pd.DataFrame) -> float:
        if candles.empty:
            return 0.0
        pv = (candles["close"] * candles["volume"]).cumsum()
        vol = candles["volume"].cumsum()
        return float((pv / vol).iloc[-1])

    @staticmethod
    def anchored_vwap_weekly(candles_1h: pd.DataFrame) -> float:
        if candles_1h.empty:
            return 0.0
        # anchor at start of ISO week
        candles_1h = candles_1h.copy()
        candles_1h["time"] = pd.to_datetime(candles_1h["time"], unit="ms", utc=True)
        start = candles_1h["time"].iloc[-1] - timedelta(days=candles_1h["time"].iloc[-1].weekday())
        week = candles_1h[candles_1h["time"] >= start]
        return Indicators.vwap(week)

    @staticmethod
    def donchian_high(series: pd.Series, period: int) -> pd.Series:
        return series.rolling(window=period, min_periods=period).max()


# ---------------------------------------------------------------------------
# 5. Computation helpers
# ---------------------------------------------------------------------------


class Computations:
    @staticmethod
    def regime(c1: pd.DataFrame) -> str:
        ema200 = Indicators.ema(c1["close"], 200)
        slope = ema200.diff()
        adx14 = Indicators.adx(c1["high"], c1["low"], c1["close"], 14)
        if slope.iloc[-1] > 0 and adx14.iloc[-1] >= 18:
            return "TREND"
        return "RANGE"

    @staticmethod
    def atr_block(c1: pd.DataFrame) -> Tuple[float, float, float]:
        atr14 = Indicators.atr(c1["high"], c1["low"], c1["close"], 14).iloc[-1]
        price = float(c1["close"].iloc[-1]) if not c1.empty else 0.0
        atr_pct = atr14 / price if price else 0.0
        return atr14, atr_pct, price

    @staticmethod
    def unit_risk(atr14: float, price: float) -> float:
        return max(0.8 * atr14, 0.012 * price)

    @staticmethod
    def base_stake(equity: float, unit_risk: float, precision: int = 6) -> float:
        risk_budget = Config.base_risk_pct * equity
        stake_qty = risk_budget / unit_risk if unit_risk else 0.0
        return round(stake_qty, precision)

    @staticmethod
    def exposure_cap_notional(equity: float, price: float) -> float:
        return Config.exposure_cap_notional_pct * equity

    @staticmethod
    def allocation_pct(balances: Dict[str, float], price: float) -> float:
        eth_val = (balances.get("eth_free", 0) + balances.get("eth_locked", 0)) * price
        usdt_val = balances.get("usdt_free", 0) + balances.get("usdt_locked", 0)
        port_val = eth_val + usdt_val
        return eth_val / port_val if port_val else 0.0


# ---------------------------------------------------------------------------
# 6. Guards and protective checks
# ---------------------------------------------------------------------------


class Guards:
    @staticmethod
    def spread_ok(spread_bps: float) -> bool:
        return spread_bps <= Config.spread_max_bps

    @staticmethod
    def slippage_ok(projected_bps: float) -> bool:
        return projected_bps <= Config.slippage_max_bps

    @staticmethod
    def data_fresh(c5: pd.DataFrame, srv_time: datetime) -> bool:
        if c5.empty:
            return False
        last_time = pd.to_datetime(c5["time"].iloc[-1], unit="ms", utc=True)
        return srv_time - last_time <= timedelta(minutes=10)

    @staticmethod
    def daily_loss_ok(state: StateStore, equity: float) -> bool:
        return state.daily_loss_realized <= 0.012 * equity


# ---------------------------------------------------------------------------
# 7. Inventory bootstrap (simplified)
# ---------------------------------------------------------------------------


class InventoryBootstrap:
    @staticmethod
    def desired_inventory_orders(c1: pd.DataFrame, balances: Dict[str, float], price: float, atr14: float) -> List[Dict]:
        alloc = Computations.allocation_pct(balances, price)
        v = Indicators.vwap(c1)
        step = 0.6 * atr14
        orders: List[Dict] = []
        if alloc > Config.target_alloc_pct + Config.target_band:
            level = v + step
            qty = (alloc - (Config.target_alloc_pct + Config.target_band)) * (balances.get("eth_free", 0) + balances.get("eth_locked", 0))
            orders.append({"side": "sell", "price": level, "qty": abs(qty)})
        elif alloc < Config.target_alloc_pct - Config.target_band:
            level = v - step
            usdt_value = (Config.target_alloc_pct - Config.target_band - alloc) * (balances.get("usdt_free", 0) + balances.get("usdt_locked", 0) + price * (balances.get("eth_free", 0) + balances.get("eth_locked", 0)))
            qty = usdt_value / price if price else 0.0
            orders.append({"side": "buy", "price": level, "qty": abs(qty)})
        return orders


# ---------------------------------------------------------------------------
# 8. Entry / Exit signal generation
# ---------------------------------------------------------------------------


class EntryExit:
    @staticmethod
    def entry_signals(c1: pd.DataFrame, c5: pd.DataFrame, regime_value: str) -> Dict[str, bool]:
        atr14, _, _ = Computations.atr_block(c1)
        v = Indicators.vwap(c1)
        aw = Indicators.anchored_vwap_weekly(c1)
        dc_high = Indicators.donchian_high(c1["high"], 20).iloc[-1] if not c1.empty else 0
        signals: Dict[str, bool] = {}
        if regime_value == "TREND":
            last_close = c1["close"].iloc[-1] if not c1.empty else 0
            signals["long_breakout"] = bool(last_close > dc_high or last_close > aw)
        else:
            step = max(0.75 * atr14, Config.grid_step_min_pct * v)
            signals["grid_step"] = step
        return signals

    @staticmethod
    def exit_rules(regime_value: str, atr14: float, entry_price: float, last_exit_price: Optional[float]) -> Tuple[float, float, float, float]:
        if regime_value == "TREND":
            tp_dist = max(1.3 * atr14, Config.trend_tp_floor_pct * entry_price)
            trail_arm = Config.trail_arm_atr * atr14
            trail_dist = Config.trail_dist_trend_atr * atr14
        else:
            tp_dist = max(1.1 * atr14, Config.range_tp_floor_pct * entry_price)
            trail_arm = Config.trail_arm_atr * atr14
            trail_dist = Config.trail_dist_range_atr * atr14
        rebuy_buffer = Config.no_rebuy_buffer_atr * atr14
        return tp_dist, trail_arm, trail_dist, rebuy_buffer


# ---------------------------------------------------------------------------
# 9. Risk sizing helpers
# ---------------------------------------------------------------------------


class RiskSizer:
    @staticmethod
    def compute_stakes(equity: float, unit_risk: float, price: float) -> List[float]:
        base_qty = Computations.base_stake(equity, unit_risk)
        stakes = [base_qty]
        qty = base_qty
        for _ in range(Config.max_adds):
            qty *= Config.add_size_decay
            stakes.append(round(qty, 6))
        cap_notional = Computations.exposure_cap_notional(equity, price)
        # Clip stakes if they exceed exposure cap
        total_notional = 0.0
        clipped: List[float] = []
        for q in stakes:
            notional = q * price
            if total_notional + notional > cap_notional:
                break
            clipped.append(q)
            total_notional += notional
        return clipped


# ---------------------------------------------------------------------------
# 10. Order lifecycle (stubs)
# ---------------------------------------------------------------------------


class OrderLifecycle:
    @staticmethod
    def reconcile_orders(desired_set: List[Dict], open_orders: List[Dict], precision: int, min_notional: float) -> None:
        """Cancel stale orders and place missing ones."""

        exchange = Data.exchange

        def key(o: Dict) -> Tuple:
            price = round(o.get("price", 0.0), precision)
            return (o.get("side"), price, round(o.get("qty", o.get("amount", 0.0)), precision))

        desired_map = {key(o): o for o in desired_set}
        open_map = {key(o): o for o in open_orders}

        # Cancel orders not desired anymore
        for k, order in open_map.items():
            if k not in desired_map:
                try:
                    exchange.cancel_order(order["id"], Config.pair)
                except Exception:
                    pass

        # Place new desired orders
        for k, order in desired_map.items():
            if k not in open_map:
                price = round(order.get("price", 0.0), precision) if "price" in order else None
                qty = round(order.get("qty", 0.0), precision)
                if price is None or price * qty >= min_notional:
                    params = {}
                    if order.get("post_only"):
                        params["postOnly"] = True
                    order_type = order.get("type", "limit" if price is not None else "market")
                    try:
                        exchange.create_order(Config.pair, order_type, order["side"], qty, price, params)
                    except Exception:
                        pass

    @staticmethod
    def handle_timeouts(open_orders: List[Dict]) -> None:
        now = Data.exchange.milliseconds()
        for o in open_orders:
            ts = o.get("timestamp")
            if ts and (now - ts) / 1000 > Config.unfilled_timeout_sec:
                try:
                    Data.exchange.cancel_order(o["id"], Config.pair)
                except Exception:
                    pass

    @staticmethod
    def handle_partials(fills: List[Dict], precision: int, min_notional: float) -> None:
        exchange = Data.exchange
        for f in fills:
            remaining = f.get("remaining")
            price = f.get("price")
            if remaining and price and remaining * price >= min_notional:
                qty = round(remaining, precision)
                try:
                    exchange.create_order(Config.pair, f.get("type", "limit"), f.get("side"), qty, price)
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# 11. Strategy loop (simplified)
# ---------------------------------------------------------------------------


class Strategy:
    def __init__(self) -> None:
        self.state = StateStore.load()

    def on_tick(self) -> None:
        c5 = Data.load_candles(Config.pair, "5m")
        c1 = Data.load_candles(Config.pair, "1h")
        best_bid, best_ask, spread = Data.load_orderbook_top(Config.pair)
        balances = Data.load_balances()
        open_orders = Data.load_open_orders(Config.pair)
        meta = Data.load_exchange_meta(Config.pair)
        srv_time = Data.server_time()

        if not Guards.data_fresh(c5, srv_time):
            return
        if not Guards.spread_ok(spread * 10000):
            return

        reg = Computations.regime(c1)
        atr14, atr_pct, px = Computations.atr_block(c1)
        u_risk = Computations.unit_risk(atr14, px)
        equity = px * (balances.get("eth_free", 0) + balances.get("eth_locked", 0)) + balances.get("usdt_free", 0) + balances.get("usdt_locked", 0)

        if self.state.bootstrap_state != "DONE":
            desired = InventoryBootstrap.desired_inventory_orders(c1, balances, px, atr14)
            OrderLifecycle.reconcile_orders(desired, open_orders, meta["price_precision"], meta["min_notional"])
            alloc = Computations.allocation_pct(balances, px)
            if Config.target_alloc_pct - Config.target_band <= alloc <= Config.target_alloc_pct + Config.target_band:
                self.state.bootstrap_state = "DONE"
                self.state.save()
            return

        desired: List[Dict] = []
        stakes = RiskSizer.compute_stakes(equity, u_risk, px)
        sig = EntryExit.entry_signals(c1, c5, reg)
        if reg == "TREND" and sig.get("long_breakout"):
            qty = stakes[0] if stakes else 0
            desired.append({"side": "buy", "type": "market", "qty": qty})
            self.state.entry_price = px
            self.state.last_add_price = px
            self.state.add_count = 0
        elif reg == "RANGE" and "grid_step" in sig:
            # Example of a grid order around VWAP
            anchor = Indicators.vwap(c1)
            step = sig["grid_step"]
            desired.append({"side": "buy", "price": anchor - step, "qty": stakes[0], "post_only": True})
            desired.append({"side": "sell", "price": anchor + step, "qty": stakes[0], "post_only": True})

        OrderLifecycle.reconcile_orders(desired, open_orders, meta["price_precision"], meta["min_notional"])
        OrderLifecycle.handle_timeouts(open_orders)
        self.monitor_position(reg, atr14, px, stakes, balances, meta, open_orders)
        self.state.save()

    def monitor_position(self, reg: str, atr14: float, price: float, stakes: List[float], balances: Dict[str, float], meta: Dict[str, float], open_orders: List[Dict]) -> None:
        """Manage exits, trailing stops and adds for an open position."""

        exchange = Data.exchange
        pos_qty = balances.get("eth_free", 0) + balances.get("eth_locked", 0)
        if pos_qty <= 0:
            self.state.entry_price = None
            self.state.trail_active = False
            return

        if self.state.entry_price is None:
            self.state.entry_price = price
            self.state.last_add_price = price

        tp_dist, trail_arm, trail_dist, _ = EntryExit.exit_rules(reg, atr14, self.state.entry_price, self.state.last_exit_price)

        # Take profit
        if price >= self.state.entry_price + tp_dist:
            try:
                exchange.create_order(Config.pair, "market", "sell", round(pos_qty, meta["qty_precision"]))
                self.state.last_exit_price = price
            except Exception:
                pass
            self.state.entry_price = None
            self.state.add_count = 0
            self.state.trail_active = False
            return

        # Trailing stop
        if not self.state.trail_active and price - self.state.entry_price >= trail_arm:
            self.state.trail_active = True
            self.state.trail_anchor_price = price
            self.state.trail_dist_atr = trail_dist
        elif self.state.trail_active:
            if price > (self.state.trail_anchor_price or 0):
                self.state.trail_anchor_price = price
            stop_price = (self.state.trail_anchor_price or 0) - (self.state.trail_dist_atr or trail_dist)
            if price <= stop_price:
                try:
                    exchange.create_order(Config.pair, "market", "sell", round(pos_qty, meta["qty_precision"]))
                    self.state.last_exit_price = price
                except Exception:
                    pass
                self.state.entry_price = None
                self.state.add_count = 0
                self.state.trail_active = False
                return

        # Adds on adverse moves
        if self.state.add_count < len(stakes) - 1:
            last_price = self.state.last_add_price or self.state.entry_price
            if last_price and (last_price - price) >= Config.add_spacing_atr * atr14:
                add_qty = stakes[self.state.add_count + 1]
                add_price = round(price, meta["price_precision"])
                try:
                    exchange.create_order(
                        Config.pair,
                        "limit",
                        "buy",
                        round(add_qty, meta["qty_precision"]),
                        add_price,
                        {"postOnly": True},
                    )
                    self.state.add_count += 1
                    self.state.last_add_price = price
                except Exception:
                    pass


if __name__ == "__main__":
    strat = Strategy()
    strat.on_tick()
