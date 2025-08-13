#!/usr/bin/env bash
set -euo pipefail
freqtrade hyperopt \
  --config config/config.json \
  --strategy ETHInventoryAware \
  --timeframe 5m \
  --timerange 20250513-20250811 \
  --spaces buy sell roi stoploss trailing \
  --hyperopt-loss SharpeHyperOptLossDaily \
  --epochs 200 --print-all
