from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict
import json

PEPPER_SYMBOL = 'INTARIAN_PEPPER_ROOT'
POS_LIMIT = 80

class Trader:
    def __init__(self):
        self.max_price_seen = 0

    def run(self, state: TradingState):
        result = {}
        current_pos = state.position.get(PEPPER_SYMBOL, 0)
        
        if PEPPER_SYMBOL not in state.order_depths:
            return result, 0, ""

        order_depth = state.order_depths[PEPPER_SYMBOL]
        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid_price = (best_bid + best_ask) / 2

        # 1. THE HARD FLOOR (Zero-Lag)
        # We update the 'High Water Mark'. If price drops from here, we out.
        if mid_price > self.max_price_seen:
            self.max_price_seen = mid_price

        orders: List[Order] = []

        # 2. THE SOVEREIGN EXECUTION
        # If the price is within 2 ticks of its all-time high, we stay MAX LONG.
        if mid_price >= self.max_price_seen - 2:
            target = 80
        # If the price drops more than 3 ticks from its high, it is a crash. 
        # We liquidate EVERYTHING immediately.
        else:
            target = 0
            # Reset the high water mark so we can re-enter when it stabilizes
            self.max_price_seen = mid_price 

        # 3. ABSOLUTE SCRUTINY EXECUTION
        if current_pos < target:
            orders.append(Order(PEPPER_SYMBOL, best_ask, target - current_pos))
        elif current_pos > target:
            orders.append(Order(PEPPER_SYMBOL, best_bid, target - current_pos))

        result[PEPPER_SYMBOL] = orders
        return result, 0, ""