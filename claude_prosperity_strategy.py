from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json
 
 
class Trader:
 
    def bid(self):
        return 15
 
    # ── tuneable knobs ──────────────────────────────────────────────────────
    POSITION_LIMITS: Dict[str, int] = {}   # filled dynamically; override per product if known
    EMA_ALPHA = 0.3          # smoothing factor for fair-value EMA (0=never update, 1=no memory)
    SPREAD    = 2            # ticks each side when market-making (buy at fv-spread, sell at fv+spread)
    MM_QTY    = 5            # max units to post per side when market-making
    # ───────────────────────────────────────────────────────────────────────
 
    # ── helpers ─────────────────────────────────────────────────────────────
 
    def _vwap_mid(self, order_depth: OrderDepth):
        """Volume-weighted mid price from the best few levels of the book."""
        buys  = order_depth.buy_orders   # {price: +qty}
        sells = order_depth.sell_orders  # {price: -qty}
        if not buys or not sells:
            return None
 
        # Best bid and ask
        best_bid = max(buys)
        best_ask = min(sells)
 
        # Simple VWAP of the top-of-book
        bid_vol = buys[best_bid]
        ask_vol = abs(sells[best_ask])
        # Weight mid by opposite-side volume (tighter side gets more weight)
        vwap = (best_bid * ask_vol + best_ask * bid_vol) / (bid_vol + ask_vol)
        return vwap
 
    def _capacity(self, position: int, limit: int, side: str) -> int:
        """How many more units can we buy (side='buy') or sell (side='sell')?"""
        if side == "buy":
            return limit - position          # how far from long limit
        else:
            return position + limit          # how far from short limit
 
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
 
            print(f"[{product}] pos={position} fv={fv:.2f} mid={mid:.2f}")
 
            # ── 2. take profitable fills (market-taking) ───────────────────
            # Buy anything priced strictly BELOW fair value
            for ask_price in sorted(order_depth.sell_orders.keys()):
                if ask_price >= fv:
                    break                                   # not cheap enough
                available = abs(order_depth.sell_orders[ask_price])
                cap = self._capacity(position, limit, "buy")
                if cap <= 0:
                    break
                qty = min(available, cap)
                print(f"  TAKE BUY {qty}x{ask_price}")
                orders.append(Order(product, ask_price, qty))
                position += qty                             # track for later orders
 
            # Sell anything priced strictly ABOVE fair value
            for bid_price in sorted(order_depth.buy_orders.keys(), reverse=True):
                if bid_price <= fv:
                    break
                available = order_depth.buy_orders[bid_price]
                cap = self._capacity(position, limit, "sell")
                if cap <= 0:
                    break
                qty = min(available, cap)
                print(f"  TAKE SELL {qty}x{bid_price}")
                orders.append(Order(product, bid_price, -qty))
                position -= qty
 
            # ── 3. market-making (passive quotes) ─────────────────────────
            # Post a resting bid below fair value and a resting ask above it.
            # The spread and qty are clipped by remaining position capacity.
            mm_bid = round(fv) - self.SPREAD
            mm_ask = round(fv) + self.SPREAD
 
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