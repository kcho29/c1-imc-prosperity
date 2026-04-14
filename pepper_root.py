from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict
import json

# Constants
PEPPER_SYMBOL = 'INTARIAN_PEPPER_ROOT'
POS_LIMIT = 80

class Trader:
    def __init__(self):
        self.history = []
        self.window = 20

    def run(self, state: TradingState):
        result = {}
        
        # 1. Persistent Data Recovery
        if state.traderData:
            try:
                self.history = json.loads(state.traderData)
            except:
                self.history = []
        
        if PEPPER_SYMBOL not in state.order_depths:
            return result, 0, json.dumps(self.history)

        order_depth: OrderDepth = state.order_depths[PEPPER_SYMBOL]
        current_pos = state.position.get(PEPPER_SYMBOL, 0)
        
        # 2. Price Discovery
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        
        if not best_bid or not best_ask:
            return result, 0, json.dumps(self.history)
            
        mid_price = (best_bid + best_ask) / 2
        self.history.append(mid_price)
        if len(self.history) > self.window:
            self.history.pop(0)

        orders: List[Order] = []
        
        # 3. Pure Python Linear Regression
        n = len(self.history)
        if n >= 5: # Start trading as soon as we have a small trend
            x = list(range(n))
            y = self.history
            
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xx = sum(xi*xi for xi in x)
            sum_xy = sum(xi*yi for xi, yi in zip(x, y))
            
            # Formula for Slope (m) and Intercept (b)
            denominator = (n * sum_xx - sum_x**2)
            if denominator != 0:
                m = (n * sum_xy - sum_x * sum_y) / denominator
                b = (sum_y - m * sum_x) / n
                predicted_now = m * (n - 1) + b

                # 4. SOVEREIGN SLOPE LOGIC
                if m > 0:
                    # Positive Slope: Bull Market Mode
                    if mid_price < predicted_now:
                        target = 80 # Buy the dip below the trajectory
                    else:
                        target = 40 # Maintain the Core 40 'Hold'
                else:
                    # Negative Slope: Bear Safeguard
                    # If the slope dips below 0, we exit to protect capital
                    target = 0

                # Execution with Scrutiny
                if current_pos < target:
                    qty = target - current_pos
                    orders.append(Order(PEPPER_SYMBOL, best_ask, qty))
                elif current_pos > target:
                    qty = current_pos - target
                    orders.append(Order(PEPPER_SYMBOL, best_bid, -qty))

        result[PEPPER_SYMBOL] = orders
        return result, 0, json.dumps(self.history)