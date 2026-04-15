"""Evaluate a strategy against the theoretical maximum PnL.

Runs prosperity4bt, parses the results, computes the trade-flow oracle
(perfect-foresight DP), and prints a comparison table.

Usage:
    python -m shared.evaluate individual/kangheecho_strategy.py 0
    python -m shared.evaluate run_logs/173489/173489.py 1
    python -m shared.evaluate my_strat.py 0 --match-trades worse
    python -m shared.evaluate my_strat.py 1 --pos-limit 50
"""

import os
import re
import subprocess
import sys
import time

from shared.data_loader import load_prices, load_trades, filter_product, available_days

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# Default position limit per product. prosperity4bt hardcodes 80 for
# EMERALDS/TOMATOES; we use the same default for unknown products.
DEFAULT_POS_LIMIT = 80


# ─── Theoretical maximum (trade-flow oracle) ────────────────────────────

def max_pnl_trade_flow(trades_list, final_mid, pos_limit):
    """DP: max PnL from selectively filling against incoming orders.

    At each trade, we choose how many units to buy or sell at the trade
    price. Position is constrained to [-pos_limit, +pos_limit]. Final
    value is cash + position * final_mid.
    """
    size = 2 * pos_limit + 1
    NEG_INF = float('-inf')
    dp = [NEG_INF] * size
    dp[pos_limit] = 0  # start flat

    for row in trades_list:
        price = float(row['price'])
        qty = int(row['quantity'])
        new_dp = dp[:]

        for pos_idx in range(size):
            if dp[pos_idx] == NEG_INF:
                continue
            pos = pos_idx - pos_limit
            cash = dp[pos_idx]

            # Buy up to qty units
            for fill in range(1, qty + 1):
                new_pos = pos + fill
                if new_pos > pos_limit:
                    break
                new_idx = new_pos + pos_limit
                val = cash - price * fill
                if new_dp[new_idx] < val:
                    new_dp[new_idx] = val

            # Sell up to qty units
            for fill in range(1, qty + 1):
                new_pos = pos - fill
                if new_pos < -pos_limit:
                    break
                new_idx = new_pos + pos_limit
                val = cash + price * fill
                if new_dp[new_idx] < val:
                    new_dp[new_idx] = val

        dp = new_dp

    best = NEG_INF
    for pos_idx in range(size):
        if dp[pos_idx] == NEG_INF:
            continue
        pos = pos_idx - pos_limit
        total = dp[pos_idx] + pos * final_mid
        if total > best:
            best = total
    return best


# ─── Patch prosperity4bt LIMITS for unknown products ─────────────────────

def patch_limits(products, pos_limit):
    """Add any missing products to prosperity4bt's LIMITS dict."""
    import prosperity4bt.data as p4_data
    for product in products:
        if product not in p4_data.LIMITS:
            p4_data.LIMITS[product] = pos_limit


# ─── Run prosperity4bt and parse output ──────────────────────────────────

def run_backtest(strategy_path, round_num, products, pos_limit, extra_args=None):
    """Run prosperity4bt and return the raw log output as a string.

    Patches prosperity4bt's LIMITS dict before running so that unknown
    products (e.g. round 1+) don't cause KeyErrors.
    """
    if not os.path.isabs(strategy_path):
        strategy_path = os.path.join(PROJECT_ROOT, strategy_path)

    # Build a small wrapper script that patches LIMITS then runs prosperity4bt.
    # This is necessary because prosperity4bt runs as a subprocess, so we
    # can't monkey-patch from the parent process.
    patch_script = os.path.join(PROJECT_ROOT, ".eval_runner.py")
    limits_dict = {p: pos_limit for p in products}
    with open(patch_script, 'w') as f:
        f.write(f"""import prosperity4bt.data
# Patch limits for products not in the default dict
for product, limit in {limits_dict!r}.items():
    if product not in prosperity4bt.data.LIMITS:
        prosperity4bt.data.LIMITS[product] = limit

from prosperity4bt.__main__ import app
app()
""")

    cmd = [
        sys.executable, patch_script,
        strategy_path, str(round_num),
        "--data", DATA_DIR,
        "--no-out",
    ]
    if extra_args:
        cmd.extend(extra_args)

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)

    # Clean up
    try:
        os.remove(patch_script)
    except OSError:
        pass

    if result.returncode != 0:
        print("prosperity4bt failed:")
        print(result.stderr)
        sys.exit(1)
    return result.stdout + result.stderr


def parse_backtest_output(log_text):
    """Extract PnL per product per day from prosperity4bt output.

    Parses the printed summary lines like:
        Backtesting ... on round 0 day -2
        EMERALDS: 2,609
        TOMATOES: 4,862

    Returns: {(day, product): pnl}
    """
    results = {}
    current_day = None

    for line in log_text.splitlines():
        line = line.strip()

        # Match "Backtesting ... on round X day Y"
        day_match = re.search(r'round \d+ day (-?\d+)', line)
        if day_match:
            current_day = int(day_match.group(1))
            continue

        # Match "PRODUCT_NAME: N,NNN" or "PRODUCT_NAME: -N,NNN.N"
        pnl_match = re.match(r'^([A-Z][A-Z_]+):\s+([-\d,]+(?:\.\d+)?)', line)
        if pnl_match and current_day is not None:
            product = pnl_match.group(1)
            pnl_str = pnl_match.group(2).replace(',', '')
            results[(current_day, product)] = float(pnl_str)

    return results


# ─── Main evaluation ─────────────────────────────────────────────────────

def evaluate(strategy_path, round_num, pos_limit=DEFAULT_POS_LIMIT, extra_args=None):
    """Run full evaluation: backtest + theoretical max + comparison."""
    days = available_days(round_num)

    # Discover products
    sample = load_prices(round_num, days[0])
    products = sorted(set(
        r.get('product', r.get('symbol', '')).strip()
        for r in sample
    ))
    products = [p for p in products if p]

    strat_name = os.path.basename(strategy_path)

    print("=" * 78)
    print(f"STRATEGY EVALUATION: {strat_name}")
    print(f"Round {round_num} | Days {days} | Position limit +/- {pos_limit}")
    print(f"Products: {', '.join(products)}")
    print("=" * 78)

    # ── Step 1: Compute theoretical max (trade-flow oracle) ──
    print()
    print("Computing theoretical maximum (trade-flow oracle)...")
    theoretical = {}
    for product in products:
        for day in days:
            prices = filter_product(load_prices(round_num, day), product)
            trades = filter_product(load_trades(round_num, day), product)
            trades = sorted(trades, key=lambda t: int(t['timestamp']))
            final_mid = float(prices[-1]['mid_price'])
            t0 = time.time()
            pnl = max_pnl_trade_flow(trades, final_mid, pos_limit)
            elapsed = time.time() - t0
            theoretical[(day, product)] = pnl
            print(f"  {product} Day {day}: {pnl:>10,.0f}  ({elapsed:.1f}s)")

    # ── Step 2: Run backtest ──
    print()
    print(f"Running prosperity4bt on {strat_name}...")
    log_output = run_backtest(strategy_path, round_num, products, pos_limit, extra_args)
    actual = parse_backtest_output(log_output)

    if not actual:
        print("  WARNING: Could not parse PnL from backtest output.")
        print("  Raw output (last 20 lines):")
        for line in log_output.strip().splitlines()[-20:]:
            print(f"    {line}")
        return

    # ── Step 3: Print comparison table ──
    print()
    col_w = max(len(p) for p in products) + 2
    day_w = 14

    # Header
    print(f"{'':>{col_w}}", end="")
    for day in days:
        print(f"{'Day ' + str(day):>{day_w * 3}}", end="")
    print()

    print(f"{'Product':>{col_w}}", end="")
    for day in days:
        print(f"{'Actual':>{day_w}}{'Max':>{day_w}}{'Capture':>{day_w}}", end="")
    print()
    print("-" * (col_w + day_w * 3 * len(days)))

    day_totals_actual = {d: 0 for d in days}
    day_totals_max = {d: 0 for d in days}

    for product in products:
        print(f"{product:>{col_w}}", end="")
        for day in days:
            act = actual.get((day, product), 0)
            mx = theoretical.get((day, product), 0)
            pct = (act / mx * 100) if mx > 0 else 0
            print(f"{act:>{day_w},.0f}{mx:>{day_w},.0f}{pct:>{day_w - 1}.1f}%", end="")
            day_totals_actual[day] += act
            day_totals_max[day] += mx
        print()

    # Totals row
    print("-" * (col_w + day_w * 3 * len(days)))
    print(f"{'TOTAL':>{col_w}}", end="")
    for day in days:
        act = day_totals_actual[day]
        mx = day_totals_max[day]
        pct = (act / mx * 100) if mx > 0 else 0
        print(f"{act:>{day_w},.0f}{mx:>{day_w},.0f}{pct:>{day_w - 1}.1f}%", end="")
    print()

    # Overall summary
    total_actual = sum(day_totals_actual.values())
    total_max = sum(day_totals_max.values())
    overall_pct = (total_actual / total_max * 100) if total_max > 0 else 0

    print()
    print(f"Overall: {total_actual:,.0f} / {total_max:,.0f} ({overall_pct:.1f}% of theoretical max)")


def main():
    if len(sys.argv) < 3:
        print("Usage: python -m shared.evaluate <strategy.py> <round> [options]")
        print()
        print("Options:")
        print("  --pos-limit N       Position limit per product (default: 80)")
        print("  --match-trades X    Passed to prosperity4bt (all/worse/none)")
        print("  (any other prosperity4bt flags are passed through)")
        print()
        print("Examples:")
        print("  python -m shared.evaluate individual/kangheecho_strategy.py 0")
        print("  python -m shared.evaluate run_logs/173489/173489.py 1")
        print("  python -m shared.evaluate my_strat.py 0 --match-trades worse")
        print("  python -m shared.evaluate my_strat.py 1 --pos-limit 50")
        sys.exit(1)

    strategy = sys.argv[1]
    round_num = int(sys.argv[2])
    remaining = sys.argv[3:]

    # Extract --pos-limit from args (not a prosperity4bt flag)
    pos_limit = DEFAULT_POS_LIMIT
    extra_args = []
    i = 0
    while i < len(remaining):
        if remaining[i] == '--pos-limit' and i + 1 < len(remaining):
            pos_limit = int(remaining[i + 1])
            i += 2
        else:
            extra_args.append(remaining[i])
            i += 1

    evaluate(strategy, round_num, pos_limit=pos_limit,
             extra_args=extra_args if extra_args else None)


if __name__ == "__main__":
    main()
