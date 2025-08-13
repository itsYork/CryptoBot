#!/usr/bin/env bash
set -euo pipefail
freqtrade trade \
  --config config/config.json \
  --strategy ETHInventoryAware
