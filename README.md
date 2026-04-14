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
│   ├── backtest.py          # Backtesting engine
│   └── log_analyzer.py      # Parse & plot submission run logs
├── data/                    # Competition data (by round)
│   └── round1/
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

The backtest module replays historical trade flow against your quotes:

```python
from shared.backtest import backtest_emeralds_v2, backtest_tomatoes_v2
from shared.data_loader import load_trades, load_prices

trades = load_trades(1, -1)
prices = load_prices(1, -1)

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

### 5. Analyze submission logs

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

### 6. Submit

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
