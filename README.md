# IMC Prosperity — Team Repository

## Project Structure

```
├── individual/              # Your personal strategies & analysis
│   ├── <name>_strategy.py   # Your Trader class (submission format)
│   ├── <name>_analysis.ipynb # Your notebooks
│   └── ...
├── shared/                  # Shared utilities (everyone can use)
│   ├── utils.py             # Common helpers (mid_price, EMA, SMA, etc.)
│   ├── data_loader.py       # Load competition CSVs
│   ├── backtest.py          # Trade-flow backtester (fast, for parameter sweeps)
│   ├── run_backtest.py      # Full-exchange backtester wrapper (prosperity4bt)
│   ├── evaluate.py          # Backtest + theoretical max comparison
│   └── log_analyzer.py      # Parse & plot submission run logs
├── datamodel.py             # Shim so strategy files resolve `from datamodel import ...`
├── data/                    # Competition data (by round)
│   └── round0/, round1/
├── run_logs/                # Logs from submitted runs
├── submission/              # Final strategy file for each round
├── .gitignore
├── requirements.txt
└── README.md
```

## Setup

```bash
pip install -r requirements.txt
```

## How to Use

### 1. Create your working files

Add your strategy and analysis files to `individual/`, prefixed with your name:

```
individual/yourname_strategy.py
individual/yourname_analysis.ipynb
```

Your strategy file must follow the IMC submission format — a single file with a `Trader` class:

```python
from datamodel import OrderDepth, TradingState, Order
from typing import List
import json

class Trader:
    def run(self, state: TradingState):
        result = {}
        # your logic here
        return result, 0, json.dumps({})
```

See `individual/kangheecho_strategy.py` for a working example.

### 2. Load data for analysis

Use `shared/data_loader.py` in your notebooks or scripts:

```python
from shared.data_loader import load_prices, load_trades, filter_product

# Load all price ticks for round 1, day -1
prices = load_prices(round_num=1, day=-1)

# Load trades
trades = load_trades(round_num=1, day=-1)

# Filter to a specific product
emerald_prices = filter_product(prices, "EMERALDS")

# See which days are available
from shared.data_loader import available_days
print(available_days(1))  # e.g. [-2, -1]
```

### 3. Use shared helpers

```python
from shared.utils import get_mid_price, ema, position_capacity, best_bid, best_ask

# EMA calculation
prev = 10000
new_ema = ema(prev, current_price, span=10)

# Position room
buy_cap, sell_cap = position_capacity(current_position, limit=20)
```

### 4. Backtest your strategy

There are two backtesters. Use the **full-exchange backtester** to test your actual submission code end-to-end, and the **trade-flow backtester** for fast parameter sweeps.

#### Full-exchange backtester (prosperity4bt)

Runs your actual `Trader.run()` against the simulated order book — tests both sniping and market-making:

```bash
# Run against all days in round 0
python -m shared.run_backtest individual/kangheecho_strategy.py 0

# Run a specific day
python -m shared.run_backtest individual/kangheecho_strategy.py 0-(-1)

# Conservative matching (more realistic)
python -m shared.run_backtest individual/kangheecho_strategy.py 0 --match-trades worse

# See trader print output
python -m shared.run_backtest individual/kangheecho_strategy.py 0 --print
```

Or call `prosperity4bt` directly:

```bash
python -m prosperity4bt individual/kangheecho_strategy.py 0 --data data
```

#### Trade-flow backtester (fast, for parameter sweeps)

Replays historical trades against your quoting logic — doesn't call `Trader.run()`:

```python
from shared.backtest import backtest_emeralds_v2, backtest_tomatoes_v2
from shared.data_loader import load_trades, load_prices

trades = load_trades(0, -1)
prices = load_prices(0, -1)

em_result = backtest_emeralds_v2(trades)
print(f"EMERALDS PnL: {em_result['final_pnl']:.0f}")

tom_result = backtest_tomatoes_v2(trades, prices)
print(f"TOMATOES PnL: {tom_result['final_pnl']:.0f}")
```

For custom strategies, use the generic `backtest_market_maker`:

```python
from shared.backtest import backtest_market_maker

def my_fair_value(timestamp, state):
    return 10000  # your fair value logic

def my_quotes(fair_value, position, state):
    bid = fair_value - 3
    ask = fair_value + 3
    return bid, ask

result = backtest_market_maker(
    trades, my_fair_value, my_quotes,
    pos_limit=20, product="EMERALDS"
)
```

### 5. Evaluate strategy vs theoretical max

Run your strategy through the full backtester and compare against the theoretical maximum PnL (computed via perfect-foresight DP over the trade flow):

```bash
# Evaluate on round 0
python -m shared.evaluate individual/kangheecho_strategy.py 0

# With conservative matching
python -m shared.evaluate individual/kangheecho_strategy.py 0 --match-trades worse
```

Output shows actual PnL, theoretical max, and capture percentage per product per day:

```
                                      Day -2                            Day -1
   Product    Actual       Max   Capture    Actual       Max   Capture
----------------------------------------------------------------------
  EMERALDS     2,609     7,280     35.8%     2,744     7,888     34.8%
  TOMATOES     4,862    10,786     45.1%     4,598    10,666     43.1%
----------------------------------------------------------------------
     TOTAL     7,471    18,066     41.4%     7,342    18,554     39.6%

Overall: 14,813 / 36,620 (40.5% of theoretical max)
```

The theoretical max uses a DP that, with perfect foresight, selectively fills against incoming trades at the optimal times. No real strategy can exceed it.

### 6. Analyze submission logs

After submitting on the Prosperity platform, download your run logs to `run_logs/<run_id>/`:

```python
from shared.log_analyzer import load_run, plot_run_summary

# Quick PnL plot
plot_run_summary(98277)

# Load raw data for custom analysis
run = load_run(98277)
data = run['data']  # parsed JSON
log = run['log']    # raw log output
```

### 7. Submit

When the team picks a strategy for a round, copy it to `submission/`:

```bash
cp individual/yourname_strategy.py submission/round1.py
```

Upload `submission/round1.py` to the Prosperity platform.

## Rules to Avoid Conflicts

1. **Only edit files with your name prefix** in `individual/`
2. **Don't modify other people's files** — discuss changes first
3. **Shared code is additive** — add new functions to `shared/`, avoid changing existing signatures
4. **New data goes in `data/round<N>/`** as each round opens
5. **New run logs go in `run_logs/<run_id>/`**
