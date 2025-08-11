from pathlib import Path
from typing import Any

class JsonDataHandler:
    def __init__(self, datadir: Path) -> None:
        self.datadir = Path(datadir)

    def ohlcv_store(self, pair: str, timeframe: str, df: Any, data_type: str) -> None:
        pair_dir = self.datadir / pair.replace('/', '_')
        pair_dir.mkdir(parents=True, exist_ok=True)
        file_path = pair_dir / f"{timeframe}-{data_type}.json"
        df.to_json(file_path, orient="records", date_format="iso")
