"""Run the prosperity4bt full-exchange backtester against a strategy file.

Usage from project root:

    python -m shared.run_backtest individual/kangheecho_strategy.py 0
    python -m shared.run_backtest individual/kangheecho_strategy.py 0-(-1)
    python -m shared.run_backtest claude_v2_prosperity_strategy.py 0 --match-trades worse

This is a thin wrapper that automatically points --data at our data/ directory
and stores output in backtests/. All prosperity4bt flags are passed through.
"""

import subprocess
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


def main():
    if len(sys.argv) < 3:
        print("Usage: python -m shared.run_backtest <strategy.py> <round> [options]")
        print()
        print("Examples:")
        print("  python -m shared.run_backtest individual/kangheecho_strategy.py 0")
        print("  python -m shared.run_backtest individual/kangheecho_strategy.py 0-(-1)")
        print("  python -m shared.run_backtest claude_v2_prosperity_strategy.py 0 --match-trades worse")
        print()
        print("All prosperity4bt flags (--match-trades, --print, --vis, etc.) are passed through.")
        sys.exit(1)

    strategy = sys.argv[1]
    rest = sys.argv[2:]

    # Resolve strategy path relative to project root
    if not os.path.isabs(strategy):
        strategy = os.path.join(PROJECT_ROOT, strategy)

    if not os.path.isfile(strategy):
        print(f"Error: strategy file not found: {strategy}")
        sys.exit(1)

    # Build the command — inject --data if not already provided
    cmd = [sys.executable, "-m", "prosperity4bt", strategy] + rest

    if "--data" not in rest:
        cmd.extend(["--data", DATA_DIR])

    # Create backtests/ dir for output if it doesn't exist
    backtests_dir = os.path.join(PROJECT_ROOT, "backtests")
    os.makedirs(backtests_dir, exist_ok=True)

    # Run
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
