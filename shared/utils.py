"""Common helper functions for strategy development and analysis."""


def get_mid_price(order_depth):
    """Calculate mid price from an OrderDepth object or dict with buy/sell orders."""
    if hasattr(order_depth, 'buy_orders'):
        buys, sells = order_depth.buy_orders, order_depth.sell_orders
    else:
        buys, sells = order_depth.get('buy_orders', {}), order_depth.get('sell_orders', {})

    if not buys or not sells:
        return None
    return (max(buys) + min(sells)) / 2


def ema(prev_ema, price, span):
    """Compute one step of an exponential moving average.

    Args:
        prev_ema: Previous EMA value (or price itself on first call).
        price: New observed price.
        span: EMA span (e.g. 10, 20, 50). Alpha = 2 / (span + 1).
    """
    alpha = 2 / (span + 1)
    return alpha * price + (1 - alpha) * prev_ema


def sma(prices):
    """Simple moving average of a list of prices."""
    if not prices:
        return None
    return sum(prices) / len(prices)


def vwap(trades):
    """Volume-weighted average price from a list of (price, quantity) tuples."""
    total_value = sum(p * q for p, q in trades)
    total_qty = sum(q for _, q in trades)
    if total_qty == 0:
        return None
    return total_value / total_qty


def best_bid(order_depth):
    """Highest bid price from an OrderDepth."""
    if hasattr(order_depth, 'buy_orders'):
        buys = order_depth.buy_orders
    else:
        buys = order_depth.get('buy_orders', {})
    return max(buys) if buys else None


def best_ask(order_depth):
    """Lowest ask price from an OrderDepth."""
    if hasattr(order_depth, 'sell_orders'):
        sells = order_depth.sell_orders
    else:
        sells = order_depth.get('sell_orders', {})
    return min(sells) if sells else None


def position_capacity(position, limit):
    """Return (buy_capacity, sell_capacity) given current position and limit.

    buy_capacity is positive (units you can still buy).
    sell_capacity is positive (units you can still sell).
    """
    return limit - position, limit + position
