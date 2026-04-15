from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict

PEPPER_SYMBOL = 'INTARIAN_PEPPER_ROOT'
POS_LIMIT = 80
# The Prosperity round usually lasts for 1,000,000 ticks or a specific limit
END_TIME = 999000 

class Trader:
    def run(self, state: TradingState):
        result = {}
        orders: List[Order] = []
        
        # 1. Position Tracking
        current_pos = state.position.get(PEPPER_SYMBOL, 0)
        
        # Guard clause: Ensure the symbol exists in the current state
        if PEPPER_SYMBOL not in state.order_depths:
            return result, 0, ""

        order_depth = state.order_depths[PEPPER_SYMBOL]

        # 2. Existence Check (Fixes the ValueError) ✅
        # We only calculate best_bid/best_ask if there are actual orders
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None

        # 3. THE SOVEREIGN MANDATE
        # If we can't see the price (empty book), we do nothing this tick to avoid errors
        if state.timestamp < END_TIME:
            if best_ask is not None: # Only trade if there is someone to buy from
                if current_pos < POS_LIMIT:
                    qty = POS_LIMIT - current_pos
                    orders.append(Order(PEPPER_SYMBOL, best_ask, qty))
        
        # 4. THE FINAL LIQUIDATION
        else:
            if best_bid is not None: # Only sell if there is someone to sell to
                if current_pos > 0:
                    orders.append(Order(PEPPER_SYMBOL, best_bid, -current_pos))

        result[PEPPER_SYMBOL] = orders
        return result, 0, ""