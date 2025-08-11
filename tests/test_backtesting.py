import json
import tempfile
from pathlib import Path

from freqtrade.configuration import Configuration
from freqtrade.enums import RunMode
from freqtrade.optimize.backtesting import Backtesting


class PathStr(str):
    """String path with joinpath for freqtrade config."""

    def joinpath(self, *paths):
        return Path(self).joinpath(*paths)


def test_backtesting_runs():
    """Run a minimal backtest to ensure strategy and config load correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        data_dir = tmp / "data"
        data_dir.mkdir()

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

        bt = Backtesting(cfg)
        bt.start()
        assert bt.results["strategy"] == "VolatilityAdaptiveSpotV3"
        assert bt.strategy.config["stake_currency"] == "USDT"
