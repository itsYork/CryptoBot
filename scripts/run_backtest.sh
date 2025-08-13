#!/usr/bin/env bash
set -euo pipefail
freqtrade backtesting \
  --config config/config.json \
  --strategy ETHInventoryAware \
  --timeframe 5m \
  --timerange 20250513-20250811 \
  --export trades
