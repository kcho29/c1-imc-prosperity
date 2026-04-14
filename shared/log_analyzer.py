"""Parse and visualize submission logs from the Prosperity platform."""

import json
import os

import matplotlib.pyplot as plt


def load_run(run_id, logs_dir=None):
    """Load a run's JSON data and log file.

    Args:
        run_id: The numeric run ID (e.g. 98277).
        logs_dir: Path to run_logs directory. Defaults to <project>/run_logs/.

    Returns:
        dict with keys 'data' (parsed JSON) and 'log' (raw log text).
    """
    if logs_dir is None:
        logs_dir = os.path.join(os.path.dirname(__file__), '..', 'run_logs')

    run_dir = os.path.join(logs_dir, str(run_id))
    result = {}

    json_path = os.path.join(run_dir, f'{run_id}.json')
    if os.path.exists(json_path):
        with open(json_path) as f:
            result['data'] = json.load(f)

    log_path = os.path.join(run_dir, f'{run_id}.log')
    if os.path.exists(log_path):
        with open(log_path) as f:
            result['log'] = f.read()

    return result


def extract_pnl_series(run_data, product):
    """Extract timestamps and PnL values for a product from run JSON data.

    Args:
        run_data: Parsed JSON from a run file.
        product: Product name (e.g. 'EMERALDS').

    Returns:
        (timestamps, pnl_values) as two lists.
    """
    timestamps = []
    pnl_values = []

    for entry in run_data:
        ts = entry.get('timestamp', 0)
        pnl = entry.get('profit_and_loss', {}).get(product, 0)
        timestamps.append(ts)
        pnl_values.append(pnl)

    return timestamps, pnl_values


def plot_run_summary(run_id, products=None, logs_dir=None):
    """Plot PnL curves for a submission run.

    Args:
        run_id: The numeric run ID.
        products: List of product names to plot. If None, plots all found.
        logs_dir: Path to run_logs directory.
    """
    run = load_run(run_id, logs_dir)
    if 'data' not in run:
        print(f"No JSON data found for run {run_id}")
        return

    data = run['data']

    if products is None:
        # Discover products from the first entry
        products = list(data[0].get('profit_and_loss', {}).keys()) if data else []

    fig, ax = plt.subplots(figsize=(12, 4))
    for product in products:
        ts, pnl = extract_pnl_series(data, product)
        ax.plot(ts, pnl, label=product)

    ax.set_xlabel('Timestamp')
    ax.set_ylabel('PnL')
    ax.set_title(f'Run {run_id} PnL')
    ax.legend()
    plt.tight_layout()
    plt.show()
