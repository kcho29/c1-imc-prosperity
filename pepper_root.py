from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict

PEPPER_SYMBOL = 'INTARIAN_PEPPER_ROOT'
POS_LIMIT = 80
# The Prosperity round usually lasts for 1,000,000 ticks or a specific limit
# Adjust the END_TIME to match the specific day's limit (e.g., 999000)
END_TIME = 999000 

class Trader:
    def run(self, state: TradingState):
        result = {}
        orders: List[Order] = []
        
        # 1. Position Tracking
        current_pos = state.position.get(PEPPER_SYMBOL, 0)
        
        if PEPPER_SYMBOL not in state.order_depths:
            return result, 0, ""

        order_depth = state.order_depths[PEPPER_SYMBOL]
        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())

        # 2. THE SOVEREIGN MANDATE
        # If we are not at the end of the day, we maintain MAX LONG (+80)
        if state.timestamp < END_TIME:
            if current_pos < POS_LIMIT:
                qty = POS_LIMIT - current_pos
                # We pay the spread (best_ask) to ensure immediate 'Hold'
                orders.append(Order(PEPPER_SYMBOL, best_ask, qty))
        
        # 3. THE FINAL LIQUIDATION
        # At the end of the simulation, we dump everything to realize PnL
        else:
            if current_pos > 0:
                orders.append(Order(PEPPER_SYMBOL, best_bid, -current_pos))

        result[PEPPER_SYMBOL] = orders
        return result, 0, ""