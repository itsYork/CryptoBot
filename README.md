# CryptoBot Setup

This repository contains a sample Freqtrade strategy and configuration for spot trading
using the **VolatilityAdaptiveSpotV3** strategy.

## Quick start

```bash
# Python 3.12/3.13 environment
python -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install freqtrade==2025.7
```

## Initialize user data

```bash
freqtrade new-config --config user_data/config.json
freqtrade new-strategy --strategy VolatilityAdaptiveSpotV3
```

Replace the generated files with the ones from this repository.

## Download data

```bash
freqtrade download-data -c user_data/config.json --timeframes 1h --days 730
```

Feather files are stored under `user_data/data/<exchange>/spot/1h/`.

## Sanity checks

```bash
freqtrade test-pairlist -c user_data/config.json
freqtrade plot-dataframe -s VolatilityAdaptiveSpotV3 -c user_data/config.json -p ETH/USDT
```

## Backtest

```bash
freqtrade backtesting -s VolatilityAdaptiveSpotV3 -c user_data/config.json --export trades --timerange 2023-01-01-
```

Backtest results are exported into `user_data/backtest_results/`.

## Hyperopt

```bash
freqtrade hyperopt -s VolatilityAdaptiveSpotV3 -c user_data/config.json --spaces buy sell roi stoploss trailing protections --timeframe 1h --epochs 300 --enable-protections
```

## Dry run

```bash
freqtrade trade -s VolatilityAdaptiveSpotV3 -c user_data/config.json
```

## UI / API (optional)

Enable the `api_server` block in `user_data/config.json` and visit
`http://127.0.0.1:8080/` locally. Do not expose the service publicly.

## Troubleshooting

* Ensure `TA-Lib` is installed if Freqtrade complains about missing dependencies.
* Convert legacy data stores with `freqtrade convert-data --data-format-ohlcv feather`.
* Validate exchange pair format using `freqtrade test-pairlist`.
