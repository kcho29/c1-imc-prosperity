from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict
import json
import numpy as np

PEPPER_SYMBOL = 'INTARIAN_PEPPER_ROOT'
POS_LIMIT = 80

class Trader:
    def __init__(self):
        self.history = []
        self.window = 20 # Lookback for trend and volatility

    def run(self, state: TradingState):
        result = {}
        
        # 1. Persistent Data Recovery
        if state.traderData:
            self.history = json.loads(state.traderData)
        
        if PEPPER_SYMBOL not in state.order_depths:
            return result, 0, json.dumps(self.history)

        order_depth: OrderDepth = state.order_depths[PEPPER_SYMBOL]
        current_pos = state.position.get(PEPPER_SYMBOL, 0)
        
        # 2. Price & Volatility Analysis
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        
        if not best_bid or not best_ask:
            return result, 0, json.dumps(self.history)
            
        mid_price = (best_bid + best_ask) / 2
        self.history.append(mid_price)
        if len(self.history) > self.window:
            self.history.pop(0)

        # 3. Safeguard Logic (Bollinger-style)
        orders: List[Order] = []
        
        if len(self.history) == self.window:
            ma = np.mean(self.history)
            std = np.std(self.history)
            upper_band = ma + (1.0 * std) # Aggressive entry threshold
            lower_band = ma - (1.5 * std) # Defensive exit threshold

            # EXPLOIT: If we break above the upper band, we are in a 'Moonshot'
            if mid_price > upper_band:
                if current_pos < POS_LIMIT:
                    # Scale in aggressively to catch the move
                    qty = POS_LIMIT - current_pos
                    orders.append(Order(PEPPER_SYMBOL, best_ask, qty))
            
            # SAFEGUARD: If we break below the lower band, the trend is DEAD
            elif mid_price < lower_band:
                if current_pos > 0:
                    # Liquidate everything to protect PnL
                    orders.append(Order(PEPPER_SYMBOL, best_bid, -current_pos))
            
            # NEUTRAL: If we are between bands, we 'Hold' our current winner
            # This prevents over-trading and 'getting destroyed' by noise

        result[PEPPER_SYMBOL] = orders
        return result, 0, json.dumps(self.history)