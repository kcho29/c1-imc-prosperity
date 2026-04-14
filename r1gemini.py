from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json

class Trader:
    # ── Tunable Knobs Optimized for Intara ──────────────────────────────────
    POSITION_LIMITS = {
        "ASH_COATED_OSMIUM": 80,
        "INTARIAN_PEPPER_ROOT": 80
    }

    # Fair value estimation
    EMA_ALPHA = 0.4          # Balanced smoothing
    
    # Execution Thresholds
    TAKE_EDGE = 1.0          # How much "better" than FV a price must be to TAKE
    SKEW_PER_UNIT = 0.15     # Aggressive skewing for the 80-unit limit
    MAX_SKEW = 8             # Cap skew at 8 ticks to prevent quoting in "the void"
    # ───────────────────────────────────────────────────────────────────────

    def _vwap_mid(self, order_depth: OrderDepth):
        buys = order_depth.buy_orders
        sells = order_depth.sell_orders
        if not buys or not sells: return None
        best_bid, bid_vol = max(buys.items())
        best_ask, ask_vol = min(sells.items())
        # Standard VWAP Mid
        return (best_bid * abs(ask_vol) + best_ask * bid_vol) / (bid_vol + abs(ask_vol))

    def _inventory_skew(self, position: int) -> float:
        skew = -self.SKEW_PER_UNIT * position
        return max(-self.MAX_SKEW, min(self.MAX_SKEW, skew))

    def run(self, state: TradingState):
        try:
            trader_state = json.loads(state.traderData) if state.traderData else {}
        except:
            trader_state = {}

        fair_values = trader_state.get("fair_values", {})
        result: Dict[str, List[Order]] = {}

        for product, order_depth in state.order_depths.items():
            orders: List[Order] = []
            position = state.position.get(product, 0)
            limit = self.POSITION_LIMITS.get(product, 80)

            mid = self._vwap_mid(order_depth)
            if mid is None: continue

            # --- 1. Fair Value Calculation ---
            # For Osmium, the "Anchor" is 10k. For Pepper Root, it's the Trend.
            if product == "ASH_COATED_OSMIUM":
                # We blend the market mid with the 10,000 anchor
                base_fv = 10000
                prev_fv = fair_values.get(product, base_fv)
                fv = 0.2 * mid + 0.8 * prev_fv # Heavy weight on the 10k anchor
            else:
                # Pepper Root: Pure trend following
                prev_fv = fair_values.get(product, mid)
                fv = self.EMA_ALPHA * mid + (1 - self.EMA_ALPHA) * prev_fv

            fair_values[product] = fv
            skew = self._inventory_skew(position)
            adjusted_fv = fv + skew

            # --- 2. Aggressive Market Taking ---
            # We "Take" orders that are mispriced relative to our Fair Value
            sorted_asks = sorted(order_depth.sell_orders.items())
            sorted_bids = sorted(order_depth.buy_orders.items(), reverse=True)

            # Buy if Ask < Fair Value - Edge
            for ask, vol in sorted_asks:
                if ask < fv - self.TAKE_EDGE:
                    qty = min(abs(vol), limit - position)
                    if qty > 0:
                        orders.append(Order(product, ask, qty))
                        position += qty
                else: break

            # Sell if Bid > Fair Value + Edge
            for bid, vol in sorted_bids:
                if bid > fv + self.TAKE_EDGE:
                    qty = min(abs(vol), position + limit)
                    if qty > 0:
                        orders.append(Order(product, bid, -qty))
                        position -= qty
                else: break

            # --- 3. Passive Market Making (Quoting) ---
            # For Pepper Root, if it's trending UP, we want to be LONG.
            # We achieve this by bidding higher than the mid.
            if product == "INTARIAN_PEPPER_ROOT":
                # Spread is tighter for the steady root
                bid_price = int(round(adjusted_fv - 1))
                ask_price = int(round(adjusted_fv + 2))
            else:
                # Osmium: Standard Market Making around the anchor
                bid_price = int(round(adjusted_fv - 2))
                ask_price = int(round(adjusted_fv + 2))

            # Send passive orders for remaining capacity
            buy_cap = limit - position
            sell_cap = position + limit

            if buy_cap > 0:
                orders.append(Order(product, bid_price, buy_cap))
            if sell_cap > 0:
                orders.append(Order(product, ask_price, -sell_cap))

            result[product] = orders

        trader_data = json.dumps({"fair_values": fair_values})
        return result, 0, trader_data