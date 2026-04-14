from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json
 
 
class Trader:
 
    def bid(self):
        return 15
 
    # ── tuneable knobs ──────────────────────────────────────────────────────
    POSITION_LIMITS: Dict[str, int] = {}   # filled dynamically; override per product if known
 
    # Fair value estimation
    EMA_ALPHA = 0.6          # INCREASED: respond faster to price moves (was 0.3)
 
    # Market-making
    SPREAD    = 3            # INCREASED: wider spread = less adverse selection (was 2)
    MM_QTY    = 8            # INCREASED: post more size to earn more spread (was 5)
 
    # Market-taking: only take if edge exceeds this threshold (filters noise)
    TAKE_EDGE = 1.5          # NEW: only take if ask < fv - TAKE_EDGE (or bid > fv + TAKE_EDGE)
 
    # Inventory management
    SKEW_PER_UNIT = 0.08     # NEW: shift quotes by this many ticks per unit of position
    MAX_SKEW      = 3        # NEW: cap the skew shift at this many ticks
    # ───────────────────────────────────────────────────────────────────────
 
    # ── helpers ─────────────────────────────────────────────────────────────
 
    def _vwap_mid(self, order_depth: OrderDepth):
        """Volume-weighted mid price from the best few levels of the book."""
        buys  = order_depth.buy_orders   # {price: +qty}
        sells = order_depth.sell_orders  # {price: -qty}
        if not buys or not sells:
            return None
 
        best_bid = max(buys)
        best_ask = min(sells)
 
        bid_vol = buys[best_bid]
        ask_vol = abs(sells[best_ask])
        vwap = (best_bid * ask_vol + best_ask * bid_vol) / (bid_vol + ask_vol)
        return vwap
 
    def _capacity(self, position: int, limit: int, side: str) -> int:
        """How many more units can we buy (side='buy') or sell (side='sell')?"""
        if side == "buy":
            return limit - position
        else:
            return position + limit
 
    def _inventory_skew(self, position: int, limit: int) -> float:
        """
        Returns a price skew (in ticks) based on current inventory.
        Positive position -> skew prices DOWN to encourage selling.
        Negative position -> skew prices UP to encourage buying.
        """
        skew = -self.SKEW_PER_UNIT * position
        return max(-self.MAX_SKEW, min(self.MAX_SKEW, skew))
 
    # ── main logic ──────────────────────────────────────────────────────────
 
    def run(self, state: TradingState):
        # ── restore persisted state ─────────────────────────────────────────
        try:
            trader_state = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            trader_state = {}
 
        fair_values: Dict[str, float] = trader_state.get("fair_values", {})
 
        result: Dict[str, List[Order]] = {}
 
        for product, order_depth in state.order_depths.items():
 
            orders: List[Order] = []
            position = state.position.get(product, 0)
 
            # Infer position limit (default 20 if not explicitly set)
            limit = self.POSITION_LIMITS.get(product, 20)
 
            # ── 1. fair-value estimate ──────────────────────────────────────
            mid = self._vwap_mid(order_depth)
            if mid is None:
                result[product] = []
                continue
 
            # EMA smoothing: blend new mid into running estimate
            prev_fv = fair_values.get(product, mid)
            fv = self.EMA_ALPHA * mid + (1 - self.EMA_ALPHA) * prev_fv
            fair_values[product] = fv
 
            # Inventory skew: adjust the "center" of our quotes
            skew = self._inventory_skew(position, limit)
            adjusted_fv = fv + skew
 
            print(f"[{product}] pos={position} fv={fv:.2f} mid={mid:.2f} skew={skew:.2f} adj_fv={adjusted_fv:.2f}")
 
            # ── 2. take profitable fills (market-taking) ───────────────────
            # Only take if edge > TAKE_EDGE to avoid trading on noise / stale fv
            for ask_price in sorted(order_depth.sell_orders.keys()):
                if ask_price >= fv - self.TAKE_EDGE:
                    break                                   # not cheap enough
                available = abs(order_depth.sell_orders[ask_price])
                cap = self._capacity(position, limit, "buy")
                if cap <= 0:
                    break
                qty = min(available, cap)
                print(f"  TAKE BUY {qty}x{ask_price} (edge={(fv - ask_price):.2f})")
                orders.append(Order(product, ask_price, qty))
                position += qty
 
            for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
                if bid_price <= fv + self.TAKE_EDGE:
                    break
                available = order_depth.buy_orders[bid_price]
                cap = self._capacity(position, limit, "sell")
                if cap <= 0:
                    break
                qty = min(available, cap)
                print(f"  TAKE SELL {qty}x{bid_price} (edge={(bid_price - fv):.2f})")
                orders.append(Order(product, bid_price, -qty))
                position -= qty
 
            # ── 3. market-making (passive quotes) ─────────────────────────
            # Use inventory-adjusted fair value so quotes lean against our position.
            # When long: adjusted_fv is lower -> ask price is lower -> easier to sell.
            # When short: adjusted_fv is higher -> bid price is higher -> easier to buy.
            mm_bid = round(adjusted_fv) - self.SPREAD
            mm_ask = round(adjusted_fv) + self.SPREAD
 
            # Ensure bid < ask (sanity check)
            if mm_bid >= mm_ask:
                mm_bid = round(adjusted_fv) - 1
                mm_ask = round(adjusted_fv) + 1
 
            buy_cap  = self._capacity(position, limit, "buy")
            sell_cap = self._capacity(position, limit, "sell")
 
            mm_buy_qty  = min(self.MM_QTY, buy_cap)
            mm_sell_qty = min(self.MM_QTY, sell_cap)
 
            if mm_buy_qty > 0:
                print(f"  MM BID {mm_buy_qty}x{mm_bid}")
                orders.append(Order(product, mm_bid, mm_buy_qty))
 
            if mm_sell_qty > 0:
                print(f"  MM ASK {mm_sell_qty}x{mm_ask}")
                orders.append(Order(product, mm_ask, -mm_sell_qty))
 
            result[product] = orders
 
        # ── persist state for next iteration ────────────────────────────────
        trader_data = json.dumps({"fair_values": fair_values})
        conversions = 0
        return result, conversions, trader_data