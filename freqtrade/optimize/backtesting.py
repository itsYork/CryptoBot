import importlib
import sys
from pathlib import Path
from typing import Any, Dict


class Backtesting:
    def __init__(self, config: Dict[str, Any], exchange: Any = None) -> None:
        self.config = config
        self.exchange = exchange
        self.results: Dict[str, Any] = {}

    def start(self) -> None:
        strategy_path = Path(self.config.get("strategy_path", ""))
        if strategy_path and str(strategy_path) not in sys.path:
            sys.path.insert(0, str(strategy_path))
        mod = importlib.import_module(self.config["strategy"])
        strat_cls = getattr(mod, self.config["strategy"])
        self.results["strategy"] = strat_cls.__name__
