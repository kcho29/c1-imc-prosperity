from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict
import math

# Constants - Updated for 25% Market Access (+20 units)
OSMIUM_SYMBOL = 'ASH_COATED_OSMIUM'
PEPPER_SYMBOL = 'INTARIAN_PEPPER_ROOT'
# If access is secured, the new limit is 100.
POS_LIMIT = 100 

class Trader:
    def run(self, state: TradingState):
        result = {}
        
        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            pos = state.position.get(product, 0)
            
            # Using 175025's original dictionary-based discovery
            buy_orders = order_depth.buy_orders
            sell_orders = order_depth.sell_orders
            
            if not buy_orders or not sell_orders:
                continue

            best_bid = max(buy_orders.keys())
            best_ask = min(sell_orders.keys())
            mid_price = (best_bid + best_ask) / 2.0

            # 175025's Core Skew Logic
            target_pos = 0          
            max_skew = 3.0          
            edge = 1                
            
            # Inventory error now scales to the new 100-unit limit
            pos_error = pos - target_pos
            skew = (pos_error / POS_LIMIT) * max_skew
            fv = mid_price - skew

            buy_vol_allowed = POS_LIMIT - pos
            sell_vol_allowed = -POS_LIMIT - pos

            # Phase A: Market Taking (175025 logic)
            for sp, sv in sorted(sell_orders.items()):
                if sp <= fv - 0.5 and buy_vol_allowed > 0:
                    vol = min(abs(sv), buy_vol_allowed)
                    orders.append(Order(product, sp, vol))
                    buy_vol_allowed -= vol

            for bp, bv in sorted(buy_orders.items(), reverse=True):
                if bp >= fv + 0.5 and sell_vol_allowed < 0:
                    vol = min(abs(bv), abs(sell_vol_allowed))
                    orders.append(Order(product, bp, -vol))
                    sell_vol_allowed += vol

            # Phase B: Market Making (175025 pennying)
            my_bid = int(round(fv - edge))
            my_ask = int(round(fv + edge))

            # Original Safeguards from 175025
            my_bid = min(my_bid, best_bid + 1)
            my_ask = max(my_ask, best_ask - 1)
            
            # Prevent self-cross
            if my_bid >= my_ask:
                my_bid = int(math.floor(mid_price - 1))
                my_ask = int(math.ceil(mid_price + 1))

            if buy_vol_allowed > 0:
                orders.append(Order(product, my_bid, buy_vol_allowed))
            if sell_vol_allowed < 0:
                orders.append(Order(product, my_ask, sell_vol_allowed))

            result[product] = orders

        return result, 0, ""