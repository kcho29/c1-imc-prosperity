Python
from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict
import json
import math

PEPPER_SYMBOL = 'INTARIAN_PEPPER_ROOT'
POS_LIMIT = 80

class Trader:
    def __init__(self):
        self.ema = None
        self.alpha = 0.3 # Fast enough to follow the moonshot, slow enough to ignore noise

    def run(self, state: TradingState):
        result = {}
        orders: List[Order] = []
        
        # 1. Recover Persistent Data
        if state.traderData:
            try:
                self.ema = json.loads(state.traderData).get("ema")
            except:
                self.ema = None
        
        if PEPPER_SYMBOL not in state.order_depths:
            return result, 0, json.dumps({"ema": self.ema})

        order_depth = state.order_depths[PEPPER_SYMBOL]
        current_pos = state.position.get(PEPPER_SYMBOL, 0)
        
        # 2. Market Analysis
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        
        if not best_bid or not best_ask:
            return result, 0, json.dumps({"ema": self.ema})
            
        mid_price = (best_bid + best_ask) / 2
        
        # Update EMA
        if self.ema is None:
            self.ema = mid_price
        else:
            self.ema = (self.alpha * mid_price) + (1 - self.alpha) * self.ema

        # 3. ASYMMETRIC MARKET MAKING LOGIC
        # We calculate our 'Lean' based on how close we are to the 80-item limit
        # If pos is 80, lean is 1.0. If pos is -80, lean is -1.0.
        inventory_lean = current_pos / POS_LIMIT
        
        # Adjust our 'Fair Price' to account for inventory risk
        # If we are long, we perceive value as LOWER (encouraging us to sell)
        skewed_fair = self.ema - (inventory_lean * 4.0) 

        # Quote a tight 2-tick spread around our skewed fair value
        bid_price = int(math.floor(skewed_fair - 1))
        ask_price = int(math.ceil(skewed_fair + 1))

        # 4. SCRUTINY EXECUTION (Maker Orders)
        # Max Buy Capacity
        buy_qty = POS_LIMIT - current_pos
        if buy_qty > 0:
            orders.append(Order(PEPPER_SYMBOL, bid_price, buy_qty))
            
        # Max Sell Capacity
        sell_qty = current_pos + POS_LIMIT
        if sell_qty > 0:
            orders.append(Order(PEPPER_SYMBOL, ask_price, -sell_qty))

        result[PEPPER_SYMBOL] = orders
        return result, 0, json.dumps({"ema": self.ema})