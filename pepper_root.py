Python
from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict
import json
import numpy as np

PEPPER_SYMBOL = 'INTARIAN_PEPPER_ROOT'
POS_LIMIT = 80

class Trader:
    def __init__(self):
        self.history = []
        self.window = 20

    def run(self, state: TradingState):
        result = {}
        if state.traderData:
            self.history = json.loads(state.traderData)
        
        if PEPPER_SYMBOL not in state.order_depths:
            return result, 0, json.dumps(self.history)

        order_depth = state.order_depths[PEPPER_SYMBOL]
        current_pos = state.position.get(PEPPER_SYMBOL, 0)
        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid_price = (best_bid + best_ask) / 2
        
        self.history.append(mid_price)
        if len(self.history) > self.window:
            self.history.pop(0)

        orders = []
        if len(self.history) == self.window:
            # Calculate Slope (m) using Linear Regression
            x = np.arange(len(self.history))
            y = np.array(self.history)
            m, b = np.polyfit(x, y, 1)
            predicted_now = m * (self.window - 1) + b

            # THE SOVEREIGN LOGIC
            if m > 0:
                # Upward Trend: Maintain at least Core 40
                if mid_price < predicted_now:
                    target = 80 # Buy the 'dip' below the slope
                else:
                    target = 40 # Sell the 'rip' above the slope
            else:
                # BEAR SAFEGUARD: Slope is negative, exit to cash
                target = 0

            # Execution Scrutiny
            if current_pos < target:
                orders.append(Order(PEPPER_SYMBOL, best_ask, target - current_pos))
            elif current_pos > target:
                orders.append(Order(PEPPER_SYMBOL, best_bid, target - current_pos))

        result[PEPPER_SYMBOL] = orders
        return result, 0, json.dumps(self.history)