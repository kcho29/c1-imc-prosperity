"""
Trader for Round 1:
  - ASH_COATED_OSMIUM  → Mean-reversion around 10,000
  - INTARIAN_PEPPER_ROOT → Trend-following (continually increasing)
"""
 
from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import statistics
 
 
# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────
OSMIUM = "ASH_COATED_OSMIUM"
ROOT   = "INTARIAN_PEPPER_ROOT"
 
POSITION_LIMIT = {OSMIUM: 50, ROOT: 50}
 
# Osmium mean-reversion parameters
OSMIUM_FAIR_VALUE   = 10_000   # long-run mean (from historical data)
OSMIUM_ENTRY_THRESH = 4        # enter when price deviates ≥ this from fair value
OSMIUM_EXIT_THRESH  = 1        # exit position when within this of fair value
OSMIUM_MAX_ORDER    = 10       # max units per order
 
# Root trend-following parameters
ROOT_LOOKBACK      = 10        # number of recent mid-prices to estimate trend slope
ROOT_MIN_SLOPE     = 0.5       # only trade if price is trending up by at least this per step
ROOT_MAX_ORDER     = 8         # max units per order
ROOT_SPREAD_BUFFER = 3         # how many ticks inside best ask/bid we're willing to pay
 
 
class Trader:
 
    def __init__(self):
        # Running price history for each product (persisted via traderData string in live env)
        self.osmium_prices: List[float] = []
        self.root_prices:   List[float] = []
 
    # ──────────────────────────────────────────
    # Main entry point called each iteration
    # ──────────────────────────────────────────
    def run(self, state: TradingState) -> tuple[Dict[str, List[Order]], int, str]:
        orders: Dict[str, List[Order]] = {}
 
        # Restore price history from serialised state
        self._load_state(state.traderData)
 
        # Current positions (default 0 if product not yet traded)
        pos = state.position
 
        # ── OSMIUM: mean reversion ──────────────────────────────────
        if OSMIUM in state.order_depths:
            osmium_orders = self._trade_osmium(
                state.order_depths[OSMIUM],
                pos.get(OSMIUM, 0)
            )
            if osmium_orders:
                orders[OSMIUM] = osmium_orders
 
        # ── ROOT: trend following ───────────────────────────────────
        if ROOT in state.order_depths:
            root_orders = self._trade_root(
                state.order_depths[ROOT],
                pos.get(ROOT, 0)
            )
            if root_orders:
                orders[ROOT] = root_orders
 
        # Serialise updated price history for next iteration
        trader_data = self._save_state()
 
        return orders, 0, trader_data
 
    # ──────────────────────────────────────────
    # Osmium: mean-reversion strategy
    # ──────────────────────────────────────────
    def _trade_osmium(self, depth: OrderDepth, position: int) -> List[Order]:
        orders: List[Order]= []
        limit = POSITION_LIMIT[OSMIUM]
 
        best_bid = max(depth.buy_orders.keys())  if depth.buy_orders  else None
        best_ask = min(depth.sell_orders.keys()) if depth.sell_orders else None
 
        if best_bid is None or best_ask is None:
            return orders
 
        mid = (best_bid + best_ask) / 2
        self.osmium_prices.append(mid)
 
        # Use rolling mean if we have enough data, otherwise use the prior
        if len(self.osmium_prices) >= 20:
            fair = statistics.mean(self.osmium_prices[-100:])
        else:
            fair = OSMIUM_FAIR_VALUE
 
        deviation = mid - fair
 
        # ── BUY when price is significantly below mean ──────────────
        if deviation <= -OSMIUM_ENTRY_THRESH:
            room = limit - position                    # how many more we can buy
            qty  = min(OSMIUM_MAX_ORDER, room)
            if qty > 0:
                # Hit the best ask (market-taking) for guaranteed fill
                orders.append(Order(OSMIUM, best_ask, qty))
 
        # ── SELL when price is significantly above mean ─────────────
        elif deviation >= OSMIUM_ENTRY_THRESH:
            room = limit + position                    # how many more we can short
            qty  = min(OSMIUM_MAX_ORDER, room)
            if qty > 0:
                orders.append(Order(OSMIUM, best_bid, -qty))
 
        # ── UNWIND when close to fair value ─────────────────────────
        else:
            if position > 0 and deviation >= -OSMIUM_EXIT_THRESH:
                # Long position nearly at fair — sell it off
                qty = min(position, OSMIUM_MAX_ORDER)
                orders.append(Order(OSMIUM, best_bid, -qty))
            elif position < 0 and deviation <= OSMIUM_EXIT_THRESH:
                # Short position nearly at fair — buy it back
                qty = min(-position, OSMIUM_MAX_ORDER)
                orders.append(Order(OSMIUM, best_ask, qty))
 
        return orders
 
    # ──────────────────────────────────────────
    # Root: trend-following strategy
    # ──────────────────────────────────────────
    def _trade_root(self, depth: OrderDepth, position: int) -> List[Order]:
        orders: List[Order] = []
        limit = POSITION_LIMIT[ROOT]
 
        best_bid = max(depth.buy_orders.keys())  if depth.buy_orders  else None
        best_ask = min(depth.sell_orders.keys()) if depth.sell_orders else None
 
        if best_bid is None or best_ask is None:
            return orders
 
        mid = (best_bid + best_ask) / 2
        self.root_prices.append(mid)
 
        # ── Estimate trend slope via simple linear regression ───────
        n = len(self.root_prices)
        if n < ROOT_LOOKBACK:
            # Not enough history yet — just buy a small starter position
            if position < ROOT_MAX_ORDER and best_ask is not None:
                orders.append(Order(ROOT, best_ask, min(ROOT_MAX_ORDER, limit - position)))
            return orders
 
        recent = self.root_prices[-ROOT_LOOKBACK:]
        slope  = self._linear_slope(recent)
 
        # ── Trend is up: stay long, buying on dips ──────────────────
        if slope >= ROOT_MIN_SLOPE:
            room = limit - position
            if room > 0:
                # Buy aggressively — pay up to ROOT_SPREAD_BUFFER above best ask
                buy_price = best_ask + ROOT_SPREAD_BUFFER
                qty = min(ROOT_MAX_ORDER, room)
                orders.append(Order(ROOT, buy_price, qty))
 
        # ── Trend has stalled or reversed: start unwinding longs ────
        elif slope < 0 and position > 0:
            qty = min(position, ROOT_MAX_ORDER)
            orders.append(Order(ROOT, best_bid, -qty))
 
        return orders
 
    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────
    @staticmethod
    def _linear_slope(prices: List[float]) -> float:
        """Least-squares slope of a price series."""
        n  = len(prices)
        xs = list(range(n))
        x_mean = (n - 1) / 2
        y_mean = sum(prices) / n
        num = sum((xs[i] - x_mean) * (prices[i] - y_mean) for i in range(n))
        den = sum((x - x_mean) ** 2 for x in xs)
        return num / den if den else 0.0
 
    def _load_state(self, trader_data: str) -> None:
        """Deserialise price histories from the traderData string."""
        if not trader_data:
            return
        try:
            import json
            data = json.loads(trader_data)
            self.osmium_prices = data.get("osmium_prices", [])
            self.root_prices   = data.get("root_prices",   [])
        except Exception:
            pass
 
    def _save_state(self) -> str:
        """Serialise price histories into the traderData string."""
        import json
        # Keep only the last 200 prices to avoid bloating the string
        return json.dumps({
            "osmium_prices": self.osmium_prices[-200:],
            "root_prices":   self.root_prices[-200:],
        })
 