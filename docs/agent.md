Agent Build Instructions for Codex

Purpose

Produce a production grade ETH trading agent for Kraken spot using Freqtrade.

Loop forever with restart safety.

Adapt on the fly to market regime and volatility.

Inventory aware so it works when the wallet begins with ETH or USDT or both.

Harden all order paths and balance flows.

---

What Codex Must Deliver

Files

user_data/strategies/ETHInventoryAware.py strategy implementation.

config/config.json runtime config aligned to this spec.

scripts/run_backtest.sh script to backtest.

scripts/run_dryrun.sh script to paper trade.

scripts/run_hyperopt.sh script to hyperopt on a rolling window.

docs/agent.md this document copied with any local notes.


Outcomes

Strategy compiles and runs in Freqtrade without manual edits.

Backtest and dry run produce logs and metrics with no missing functions.

Strategy survives restarts by reconstructing intent from balances and open orders.

No placeholders and no TODO markers. All parameters have concrete values or are learned by code at runtime.

---

Operating Constraints and Quality Bar

Python three point ten or newer.

Only public Freqtrade hook points. If an API changed in your local version, adapt while preserving behavior.

Respect Kraken precision and minimum notional at order submit.

Use post only in range mode. Allow market or protected limit in trend breakout when slippage is within limit.

Log every decision and order lifecycle event with one line structured messages.

Add unit tests for math helpers and grid builder. Lightweight pytest is fine.

---

Environment Bootstrap

Pip packages

Place all pins in requirements.txt. These are the baseline pins to install. You may add additional runtime libs only if truly required.

numpy==2.3.2
pandas==2.3.1
bottleneck==1.5.0
numexpr==2.11.0
ft-pandas-ta==0.3.15
ta-lib==0.5.5
technical==1.5.2
ccxt==4.4.99
cryptography==45.0.6
aiohttp==3.12.15
SQLAlchemy==2.0.42
python-telegram-bot==22.3
httpx>=0.24.1
humanize==4.12.3
cachetools==6.1.0
requests==2.32.4
urllib3==2.5.0
certifi==2025.8.3
jsonschema==4.25.0
tabulate==0.9.0
pycoingecko==3.2.0
jinja2==3.1.6
joblib==1.5.1
rich==14.1.0
pyarrow

Repo layout

project/
  config/config.json
  user_data/strategies/ETHInventoryAware.py
  scripts/run_backtest.sh
  scripts/run_dryrun.sh
  scripts/run_hyperopt.sh
  docs/agent.md

---

Functional Spec

Universe

Single pair ETH USDT on Kraken spot.


Loop and timeframes

Execution five minutes. Regime and risk one hour.


Regime

Trend when EMA two hundred slope is positive and ADX fourteen is at least eighteen.

Range otherwise.


Volatility features

ATR fourteen on one hour and ATR percent equals ATR divided by close.


Sizing and risk for eight thousand USDT equity

Base risk budget equals zero point sixty percent of equity equals forty eight USDT.

Unit risk equals max of zero point eight times ATR and one point two percent of price.

Base stake equals risk budget divided by unit risk with proper rounding.

Adds up to four. Each add equals eighty percent of prior size. Add spacing equals zero point seven times ATR adverse move from last entry.

Cap total risk at two times base risk and notional at thirty percent of equity.


Inventory aware bootstrap

Target ETH allocation equals fifty percent with band plus or minus eight percent.

If allocation above band place layered limit sells every zero point six times ATR above one hour VWAP until inside band.

If allocation below band place layered limit buys every zero point six times ATR below one hour VWAP until inside band.


Entries and exits

Trend mode entry when close is above Donchian twenty high or above anchored VWAP weekly. Allow taker only when projected slippage is within ten basis points.

Trend take profit equals max of one point three times ATR and one point one percent of entry. Trail arms at plus one times ATR and trails by zero point eight times ATR.

Range mode builds symmetric grid around one hour VWAP. Step equals max of zero point seven five times ATR and zero point seven percent of price. Use post only limits. Take profit per fill equals max of one point one times ATR and zero point eight percent of entry.

Time exit when age exceeds four days and unrealized profit is between minus zero point five percent and plus zero point five percent.

No rebuy rule requires next buy at least zero point four times ATR above last exit price.


Order hardening

Precision and minimum notional checks before submit.

Spread filter skip when instantaneous spread exceeds fifteen basis points.

Slippage guard on entries. Abort if ask is above last close by more than fifteen basis points for buys or bid is below last close by more than fifteen basis points for sells.

Unfilled timeout after ninety seconds then reprice once with ten basis points tolerance.

Partial fills requeue remainder if still above minimum notional.

On regime change cancel all outstanding orders before placing new intent set.

Maintain a small fee buffer in both assets.


Protections

Cooldown of three one hour candles after a stop.

Data freshness check for five minute candles.

Daily loss throttle disables adds for twenty four hours if realized day loss exceeds one point two percent of equity.


Persistence

Save last regime. Last exit price. Last grid anchor. Trail state. Add count and last add price. Daily loss sum. Bootstrap state. Hash of desired order set for reconciliation.


Observability

One line logs for signal and order lifecycle.

Metrics for fills cancels rejects timeouts and PnL.

Tags on orders include regime id ATR at entry grid index and add index.


---

Freqtrade Hook Map

Implement these hooks in the strategy class. Use additional helpers as needed.

populate_indicators compute EMA two hundred ADX fourteen ATR fourteen one hour VWAP anchored VWAP weekly Donchian twenty.

populate_entry_trend trend and range entries by rules above.

populate_exit_trend exits including take profit and time exits. Trailing can be in custom logic.

custom_stake_amount compute dynamic base stake from unit risk and balance. Enforce exposure cap.

confirm_trade_entry enforce slippage and spread guards and no rebuy buffer.

confirm_trade_exit allow time exit and emergency exit rules.

custom_entry_price and custom_exit_price for grid level pricing and protected limits.

position_adjustment_enable return true to allow adds.

adjust_trade_position implement adverse move ladder adds with spacing and decay and throttle.

order_time_in_force and order_types ensure post only in range and market or protected limit in trend.


If any hook name differs in your local Freqtrade version adapt accordingly and preserve behavior.

---

Config Template

Place this at config/config.json. Adapt credentials and folders locally.

{
  "dry_run": true,
  "dry_run_wallet": 8000,
  "max_open_trades": 1,
  "stake_currency": "USDT",
  "stake_amount": "unlimited",
  "timeframe": "5m",
  "trading_mode": "spot",
  "exchange": {
    "name": "kraken",
    "ccxt_config": {"enableRateLimit": true},
    "ccxt_async_config": {"enableRateLimit": true, "rateLimit": 3100},
    "pair_whitelist": ["ETH/USDT"]
  },
  "order_types": {
    "entry": "limit",
    "exit": "limit",
    "emergency_exit": "market"
  },
  "unfilledtimeout": {"buy": 90, "sell": 90, "unit": "seconds"},
  "bid_strategy": {"price_side": "bid", "use_order_book": true},
  "ask_strategy": {"price_side": "ask", "use_order_book": true},
  "position_adjustment_enable": true
}

---

Scripts

Backtest

#!/usr/bin/env bash
set -euo pipefail
freqtrade backtesting \
  --config config/config.json \
  --strategy ETHInventoryAware \
  --timeframe 5m \
  --timerange 20250513-20250811 \
  --export trades

Dry run

#!/usr/bin/env bash
set -euo pipefail
freqtrade trade \
  --config config/config.json \
  --strategy ETHInventoryAware

Hyperopt

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

Guard the strategy so hyperopt cannot push below these floors.

Grid step minimum equals zero point seven percent of price.

Take profit minimum equals zero point eight percent in range and one point one percent in trend.

Trail arm minimum equals one times ATR and trail distance minimum equals zero point eight times ATR in trend.

---

Detailed Build Plan for Codex

Step one. Scaffolding

Create repo layout and empty files listed above.

Add a pyproject or requirements file and install. Verify imports.


Step two. Indicators and features

Implement indicator functions. Close your candles gap with informative pairs if needed for one hour on five minute strategy.

Unit test EMA ADX ATR Donchian and VWAP calculations.


Step three. Sizing and risk

Implement unit risk and dynamic base stake and exposure cap.

Implement add sizing with decay and spacing in adjust_trade_position.


Step four. Signals and orders

Build regime detector and volatility tier features.

Encode trend and range entries.

Implement no rebuy buffer and spread and slippage guards.

Enforce post only in range and protected pricing in trend.


Step five. Inventory bootstrap

Compute allocation percent from live balances and last price.

Generate layered orders to bring allocation into band.

Mark bootstrap done when inside band.


Step six. Exits and trailing

Implement take profit and trailing logic plus time exit.


Step seven. Persistence and restart

Use Freqtrade trade tags or a small JSON sidecar file in user data to persist last regime last exit price grid anchor trail state add count and loss throttle state.

On startup reconcile open orders and balances. If free ETH exists without a tracked trade re enter bootstrap.


Step eight. Observability and tests

Structured logs on every decision and order event.

Unit tests for math and grid and sizers.

Backtest over ninety days on five minute candles. Then dry run for at least one week.


Step nine. Final review

No placeholders. All guards enforced. Strategy restarts without drift.

---

Acceptance Checklist

[ ] Strategy file compiles and all Freqtrade hooks resolve.

[ ] Indicators and features match the spec including ATR percent and anchored VWAP weekly.

[ ] Dynamic stake and exposure cap compute correctly at runtime.

[ ] Adds follow spacing decay and throttle rules and stop at the cap.

[ ] Inventory bootstrap reaches the target band then switches to normal mode.

[ ] Order hardening covers precision minimum notional spread slippage timeouts partials and regime changes.

[ ] Exit logic includes take profit trailing and time exit. No rebuy buffer is respected.

[ ] Daily loss throttle disables adds and re enables after the window.

[ ] Logs and metrics are emitted for all key events and errors.

[ ] Backtest and dry run produce expected order pacing and PnL traces.

---

Notes for Local Differences

If the local Freqtrade version changes any hook signatures adjust function names and parameters while preserving the requirements and outcome here. If Kraken spot does not support a native stop order simulate it with a watchdog that issues a market exit when the trigger hits.

---

Definition of Done

You can run backtest dry run and then live with only credentials added.

The agent adapts between range and trend and does not grind fees during low volatility.

Restart safety is proven by manual kill and resume tests.

All checkboxes above are true.

