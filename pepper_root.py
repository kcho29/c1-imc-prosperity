from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict
import json

PEPPER_SYMBOL = 'INTARIAN_PEPPER_ROOT'
POS_LIMIT = 80

class Trader:
    def __init__(self):
        self.price_history = []

    def run(self, state: TradingState):
        result = {}
        
        # 1. Restore History for Momentum Calculation
        if state.traderData:
            self.price_history = json.loads(state.traderData)

        if PEPPER_SYMBOL not in state.order_depths:
            return result, 0, json.dumps(self.price_history)

        order_depth: OrderDepth = state.order_depths[PEPPER_SYMBOL]
        current_pos = state.position.get(PEPPER_SYMBOL, 0)
        
        # 2. Calculate Current Mid-Price
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        
        if best_bid and best_ask:
            mid_price = (best_bid + best_ask) / 2
            self.price_history.append(mid_price)
            if len(self.price_history) > 5:
                self.price_history.pop(0)

        # 3. Momentum Prediction Engine
        orders: List[Order] = []
        if len(self.price_history) == 5:
            # Predict next price based on current trend
            prediction = self.price_history[-1] + (self.price_history[-1] - self.price_history[0]) / 4
            
            # AGGRESSIVE EXECUTION
            # Buy if we predict an upward move
            if prediction > mid_price + 1 and current_pos < POS_LIMIT:
                qty = POS_LIMIT - current_pos
                orders.append(Order(PEPPER_SYMBOL, best_ask, qty))
            
            # Sell/Short if we predict a downward move
            elif prediction < mid_price - 1 and current_pos > -POS_LIMIT:
                qty = current_pos + POS_LIMIT
                orders.append(Order(PEPPER_SYMBOL, best_bid, -qty))

        result[PEPPER_SYMBOL] = orders
        return result, 0, json.dumps(self.price_history)