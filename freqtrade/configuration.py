import json
from pathlib import Path
from typing import Any, Dict

class Configuration:
    def __init__(self, args: Dict[str, Any], runmode: Any) -> None:
        self.args = args
        self.runmode = runmode
        self._config: Dict[str, Any] = {}
        for path in args.get("config", []):
            cfg_path = Path(path)
            if cfg_path.exists():
                with cfg_path.open() as f:
                    self._config.update(json.load(f))

    def get_config(self) -> Dict[str, Any]:
        return self._config
