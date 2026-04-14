from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict
import json

PEPPER_SYMBOL = 'INTARIAN_PEPPER_ROOT'
POS_LIMIT = 80

class Trader:
    def __init__(self):
        self.ema = None
        # Alpha 0.2 means the EMA focuses on roughly the last 9-10 ticks
        self.alpha = 0.2 

    def run(self, state: TradingState):
        result = {}
        
        # 1. Recover EMA from Persistent Data
        if state.traderData:
            try:
                self.ema = json.loads(state.traderData).get("ema")
            except:
                self.ema = None
        
        if PEPPER_SYMBOL not in state.order_depths:
            return result, 0, json.dumps({"ema": self.ema})

        order_depth = state.order_depths[PEPPER_SYMBOL]
        current_pos = state.position.get(PEPPER_SYMBOL, 0)
        
        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        mid_price = (best_bid + best_ask) / 2

        # 2. Update EMA
        if self.ema is None:
            self.ema = mid_price
        else:
            self.ema = (self.alpha * mid_price) + (1 - self.alpha) * self.ema

        orders: List[Order] = []

        # 3. CORE & SATELLITE EXECUTION
        # Rule: If Mid > EMA, we are in a 'Strength' zone. We hold 80.
        if mid_price > self.ema:
            target = 80
        # Rule: If Mid < EMA, we are in a 'Weakness' zone. We drop to 0 to safeguard.
        # We discard the 'Core 40' here to prevent another -40k loss.
        elif mid_price < self.ema:
            target = 0
        else:
            target = current_pos

        # Execution Scrutiny
        if current_pos < target:
            orders.append(Order(PEPPER_SYMBOL, best_ask, target - current_pos))
        elif current_pos > target:
            orders.append(Order(PEPPER_SYMBOL, best_bid, target - current_pos))

        result[PEPPER_SYMBOL] = orders
        return result, 0, json.dumps({"ema": self.ema})