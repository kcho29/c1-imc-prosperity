from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict
import json

PEPPER_SYMBOL = 'INTARIAN_PEPPER_ROOT'
POS_LIMIT = 80

class Trader:
    def __init__(self):
        self.long_ema = None
        self.alpha = 0.1 # Slow EMA to capture the 'big' trend

    def run(self, state: TradingState):
        result = {}
        
        # 1. Persistent State for the Trend
        if state.traderData:
            data = json.loads(state.traderData)
            self.long_ema = data.get("ema")
        
        if PEPPER_SYMBOL not in state.order_depths:
            return result, 0, json.dumps({"ema": self.long_ema})

        order_depth: OrderDepth = state.order_depths[PEPPER_SYMBOL]
        current_pos = state.position.get(PEPPER_SYMBOL, 0)
        
        # 2. Mid-Price & EMA Calculation
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        
        if not best_bid or not best_ask:
            return result, 0, json.dumps({"ema": self.long_ema})
            
        mid_price = (best_bid + best_ask) / 2
        
        if self.long_ema is None:
            self.long_ema = mid_price
        else:
            self.long_ema = (self.alpha * mid_price) + (1 - self.alpha) * self.long_ema

        # 3. Trend-Following Logic (Buy and Hold)
        orders: List[Order] = []
        
        # Rule: If price is above the trend line, MAX LONG (+80)
        if mid_price > self.long_ema + 0.5:
            if current_pos < POS_LIMIT:
                qty = POS_LIMIT - current_pos
                # We cross the spread to ensure we are 'holding'
                orders.append(Order(PEPPER_SYMBOL, best_ask, qty))
        
        # Rule: If price breaks BELOW the trend, exit everything and go neutral
        elif mid_price < self.long_ema - 1.0:
            if current_pos > 0:
                orders.append(Order(PEPPER_SYMBOL, best_bid, -current_pos))

        result[PEPPER_SYMBOL] = orders
        return result, 0, json.dumps({"ema": self.long_ema})