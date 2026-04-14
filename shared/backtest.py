"""Backtesting engine for IMC Prosperity strategies.

Replays historical trade flow against a strategy's posted quotes.
When an aggressive order arrives, if our quote would be hit, we get filled.

Caveat: this is a lower bound — in the real exchange our orders also sit in the
book and attract new flow we cannot see in the historical data.
"""

from shared.data_loader import load_prices, load_trades, filter_product


def backtest_market_maker(trades, fair_value_fn, quote_fn, pos_limit=20, product=None):
    """Generic backtest for a market-making strategy.

    Args:
        trades: List of trade dicts (must have 'timestamp', 'price', 'quantity',
                and optionally 'product'/'symbol').
        fair_value_fn: Callable(timestamp, state_dict) -> float.
                       Returns the fair value at a given timestamp.
        quote_fn: Callable(fair_value, position, state_dict) -> (bid_price, ask_price).
                  Returns the prices at which we'd quote.
        pos_limit: Max absolute position.
        product: If set, filter trades to this product.

    Returns:
        dict with keys: 'pnl_curve', 'pos_curve', 'final_position', 'final_pnl'.
    """
    if product:
        trades = filter_product(trades, product)
    trades = sorted(trades, key=lambda t: int(t['timestamp']))

    position = 0
    pnl = 0.0
    pnl_curve = []
    pos_curve = []
    state = {}  # strategy can store arbitrary state here

    last_fair = None
    for t in trades:
        ts = int(t['timestamp'])
        price = float(t['price'])
        qty = int(t['quantity'])

        fair = fair_value_fn(ts, state)
        last_fair = fair
        our_bid, our_ask = quote_fn(fair, position, state)

        # Incoming buy -> fills our ask
        if price >= our_ask and position > -pos_limit:
            fill = min(qty, pos_limit + position)
            if fill > 0:
                position -= fill
                pnl += our_ask * fill

        # Incoming sell -> fills our bid
        elif price <= our_bid and position < pos_limit:
            fill = min(qty, pos_limit - position)
            if fill > 0:
                position += fill
                pnl -= our_bid * fill

        mtm = pnl + position * (fair if fair else 0)
        pnl_curve.append(mtm)
        pos_curve.append(position)

    final_mtm = pnl + position * (last_fair if last_fair else 0)
    return {
        'pnl_curve': pnl_curve,
        'pos_curve': pos_curve,
        'final_position': position,
        'final_pnl': final_mtm,
    }


def backtest_emeralds_v2(trades, pos_limit=20):
    """Backtest the v2 EMERALDS market-making strategy."""
    FAIR = 10000
    em = sorted(filter_product(trades, "EMERALDS"), key=lambda t: int(t['timestamp']))

    position, pnl = 0, 0.0
    pnl_curve, pos_curve = [], []

    for t in em:
        price, qty = float(t['price']), int(t['quantity'])

        pos_adj = round(position * 0.25)
        our_bid = min(FAIR - 3 - pos_adj, FAIR - 1)
        our_ask = max(FAIR + 3 - pos_adj, FAIR + 1)

        if price >= our_ask and position > -pos_limit:
            fill = min(qty, pos_limit + position)
            if fill > 0:
                position -= fill
                pnl += our_ask * fill
        elif price <= our_bid and position < pos_limit:
            fill = min(qty, pos_limit - position)
            if fill > 0:
                position += fill
                pnl -= our_bid * fill

        pnl_curve.append(pnl + position * FAIR)
        pos_curve.append(position)

    return {
        'pnl_curve': pnl_curve,
        'pos_curve': pos_curve,
        'final_position': position,
        'final_pnl': pnl + position * FAIR,
    }


def backtest_tomatoes_v2(trades, prices, pos_limit=20):
    """Backtest the v2 TOMATOES EMA market-making strategy."""
    tom_t = sorted(filter_product(trades, "TOMATOES"), key=lambda t: int(t['timestamp']))
    tom_p = filter_product(prices, "TOMATOES")

    alpha_fast, alpha_slow = 2 / 11, 2 / 51
    ema_f = ema_s = float(tom_p[0]['mid_price'])
    ema_at = {}
    for r in tom_p:
        mid = float(r['mid_price'])
        ema_f = alpha_fast * mid + (1 - alpha_fast) * ema_f
        ema_s = alpha_slow * mid + (1 - alpha_slow) * ema_s
        ema_at[int(r['timestamp'])] = (ema_f, ema_s)

    sorted_ts = sorted(ema_at.keys())
    last_mid = float(tom_p[-1]['mid_price'])

    position, pnl = 0, 0.0
    pnl_curve, pos_curve = [], []

    for t in tom_t:
        ts, price, qty = int(t['timestamp']), float(t['price']), int(t['quantity'])
        idx = min(range(len(sorted_ts)), key=lambda i: abs(sorted_ts[i] - ts))
        fv_f, fv_s = ema_at[sorted_ts[idx]]
        fair = round(fv_f)

        pos_adj = round(position * 0.3)
        trend_adj = round((fv_f - fv_s) * 0.4)
        our_bid = fair - 4 - pos_adj + trend_adj
        our_ask = fair + 4 - pos_adj + trend_adj

        if price >= our_ask and position > -pos_limit:
            fill = min(qty, pos_limit + position)
            if fill > 0:
                position -= fill
                pnl += our_ask * fill
        elif price <= our_bid and position < pos_limit:
            fill = min(qty, pos_limit - position)
            if fill > 0:
                position += fill
                pnl -= our_bid * fill

        pnl_curve.append(pnl + position * last_mid)
        pos_curve.append(position)

    return {
        'pnl_curve': pnl_curve,
        'pos_curve': pos_curve,
        'final_position': position,
        'final_pnl': pnl + position * last_mid,
    }
