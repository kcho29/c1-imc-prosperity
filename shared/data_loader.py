"""Load competition CSV data into usable formats."""

import csv
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')


def _find_round_dir(round_num):
    """Locate the data directory for a given round number (case-insensitive)."""
    target = f'round{round_num}'
    for entry in os.listdir(DATA_DIR):
        if entry.lower() == target.lower() and os.path.isdir(os.path.join(DATA_DIR, entry)):
            return os.path.join(DATA_DIR, entry)
    raise FileNotFoundError(f"No data directory for round {round_num} in {DATA_DIR}")


def _find_file(round_dir, prefix, day):
    """Find a CSV matching prefix and day, handling varying round numbers in filenames."""
    suffix = f'day_{day}.csv'
    for fname in os.listdir(round_dir):
        if fname.startswith(prefix) and fname.endswith(suffix):
            return fname
    raise FileNotFoundError(f"No {prefix} file for day {day} in {round_dir}")


def load_prices(round_num, day):
    """Load price ticks for a given round and day.

    Args:
        round_num: Round number (e.g. 1).
        day: Day number (e.g. -1, -2).

    Returns:
        List of dicts with keys from the CSV header.
    """
    round_dir = _find_round_dir(round_num)
    filename = _find_file(round_dir, 'prices', day)
    path = os.path.join(round_dir, filename)
    with open(path) as f:
        return list(csv.DictReader(f, delimiter=';'))


def load_trades(round_num, day):
    """Load trade data for a given round and day.

    Args:
        round_num: Round number (e.g. 1).
        day: Day number (e.g. -1, -2).

    Returns:
        List of dicts with keys from the CSV header.
    """
    round_dir = _find_round_dir(round_num)
    filename = _find_file(round_dir, 'trades', day)
    path = os.path.join(round_dir, filename)
    with open(path) as f:
        return list(csv.DictReader(f, delimiter=';'))


def filter_product(rows, product):
    """Filter rows to only those matching a specific product."""
    return [r for r in rows if r.get('product', r.get('symbol')) == product]


def available_days(round_num):
    """List available day numbers for a round."""
    round_dir = _find_round_dir(round_num)
    days = set()
    for fname in os.listdir(round_dir):
        if fname.startswith('prices_') and fname.endswith('.csv'):
            # Extract day number from e.g. prices_round_0_day_-2.csv
            parts = fname.replace('.csv', '').split('_')
            days.add(int(parts[-1]))
    return sorted(days)
