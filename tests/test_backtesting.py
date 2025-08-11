import json
import tempfile
from pathlib import Path

import pandas as pd

from freqtrade.configuration import Configuration
from freqtrade.data.history.datahandlers.jsondatahandler import JsonDataHandler
from freqtrade.enums import RunMode
from freqtrade.optimize.backtesting import Backtesting
from freqtrade.resolvers.exchange_resolver import ExchangeResolver


class PathStr(str):
    """String path with joinpath for freqtrade config."""

    def joinpath(self, *paths):
        return Path(self).joinpath(*paths)


def test_backtesting_runs():
    """Run a minimal backtest to ensure strategy and data load correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        data_dir = tmp / "data"
        data_dir.mkdir()

        start = pd.Timestamp("2021-01-01", tz="UTC")
        df = pd.DataFrame(
            {
                "date": pd.date_range(start, periods=300, freq="H"),
                "open": 100 + 0.1 * pd.Series(range(300)),
                "high": 100.5 + 0.1 * pd.Series(range(300)),
                "low": 99.5 + 0.1 * pd.Series(range(300)),
                "close": 100 + 0.1 * pd.Series(range(300)),
                "volume": 1000,
            }
        )
        JsonDataHandler(data_dir).ohlcv_store("ETH/USDT", "1h", df, "spot")

        repo = Path(__file__).resolve().parents[1]
        config = {
            "dry_run": True,
            "stake_currency": "USDT",
            "stake_amount": 100,
            "trading_mode": "spot",
            "margin_mode": "isolated",
            "timeframe": "1h",
            "max_open_trades": 1,
            "minimal_roi": {"0": 0.1},
            "fee": 0.001,
            "pairlists": [{"method": "StaticPairList"}],
            "exchange": {
                "name": "kraken",
                "pair_whitelist": ["ETH/USDT"],
                "ccxt_config": {"enableRateLimit": False},
                "skip_pair_validation": True,
                "skip_update": True,
            },
            "dataformat_ohlcv": "json",
            "datadir": str(data_dir),
            "strategy": "VolatilityAdaptiveSpotV3",
            "strategy_path": str(repo / "user_data" / "strategies"),
            "exportfilename": str(tmp / "results.json"),
            "user_data_dir": str(repo / "user_data"),
        }
        cfg_path = tmp / "config.json"
        cfg_path.write_text(json.dumps(config))

        args = {"config": [str(cfg_path)]}
        configuration = Configuration(args, RunMode.BACKTEST)
        cfg = configuration.get_config()
        cfg["datadir"] = PathStr(str(data_dir))
        cfg["user_data_dir"] = PathStr(str(repo / "user_data"))

        exchange = ExchangeResolver.load_exchange(cfg, validate=False)
        exchange._markets = {
            "ETH/USDT": {
                "symbol": "ETH/USDT",
                "base": "ETH",
                "quote": "USDT",
                "limits": {"amount": {"min": 0.0001}, "price": {"min": 0.0001}},
                "precision": {"price": 8, "amount": 8},
                "active": True,
                "spot": True,
                "info": {},
            }
        }

        bt = Backtesting(cfg, exchange=exchange)
        bt.start()
        assert "strategy" in bt.results
