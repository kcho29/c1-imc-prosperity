Python
from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict
import math

# Constants from original 175025
OSMIUM_SYMBOL = 'ASH_COATED_OSMIUM'
PEPPER_SYMBOL = 'INTARIAN_PEPPER_ROOT'

class Trader:
    def run(self, state: TradingState):
        result = {}
        
        # --- MARKET ACCESS BID (The "Seat on the Train") ---
        # Per instructions: This targets the median to avoid waste.
        # This value represents our bid for the +25% volume access.
        bid_amount = 5150 
        # --------------------------------------------------

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            pos = state.position.get(product, 0)
            
            # Updated Limit for Round 2 (+25% access)
            pos_limit = 100 
            
            # Exact 175025 Dictionary Discovery logic
            buy_orders = order_depth.buy_orders
            sell_orders = order_depth.sell_orders
            
            if not buy_orders or not sell_orders:
                continue

            best_bid = max(buy_orders.keys())
            best_ask = min(sell_orders.keys())
            mid_price = (best_bid + best_ask) / 2.0

            # Exact 175025 Parameters
            target_pos = 0          
            max_skew = 3.0 if product == OSMIUM_SYMBOL else 15.0
            edge = 1 if product == OSMIUM_SYMBOL else 5 # Preserving Pepper edge
            
            # Inventory-Skew Calculation
            pos_error = pos - target_pos
            skew = (pos_error / pos_limit) * max_skew
            fv = mid_price - skew

            buy_vol_allowed = pos_limit - pos
            sell_vol_allowed = -pos_limit - pos

            # Phase A: Market Taking (Directly from 175025)
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

            # Phase B: Market Making (Pennying)
            my_bid = int(round(fv - edge))
            my_ask = int(round(fv + edge))

            # Original 175025 Safeguards
            my_bid = min(my_bid, best_bid + 1)
            my_ask = max(my_ask, best_ask - 1)
            
            if my_bid >= my_ask:
                my_bid = int(math.floor(mid_price - 1))
                my_ask = int(math.ceil(mid_price + 1))

            if buy_vol_allowed > 0:
                orders.append(Order(product, my_bid, buy_vol_allowed))
            if sell_vol_allowed < 0:
                orders.append(Order(product, my_ask, sell_vol_allowed))

            result[product] = orders

        # The 'bid_amount' is returned as the second element per Round 2 rules.
        return result, bid_amount, ""