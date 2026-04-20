from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict

# Constants
OSMIUM_SYMBOL = 'ASH_COATED_OSMIUM'
PEPPER_SYMBOL = 'INTARIAN_PEPPER_ROOT'

class Trader:
    def run(self, state: TradingState):
        result = {}
        
        # Round 2 Access Fee logic: This value should be submitted in the 
        # separate auction interface, not the code, but we track it here.
        # Target: ~5,150 XIRECs (The "Median Seat on the Train")
        
        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            pos = state.position.get(product, 0)
            
            # Use higher limits if access was granted (Adjustable)
            pos_limit = 100 if product == OSMIUM_SYMBOL else 80 
            
            buy_orders = sorted(order_depth.buy_orders.items(), key=lambda x: x[0], reverse=True)
            sell_orders = sorted(order_depth.sell_orders.items(), key=lambda x: x[0])
            
            if not buy_orders or not sell_orders:
                continue

            best_bid, _ = buy_orders[0]
            best_ask, _ = sell_orders[0]
            mid_price = (best_bid + best_ask) / 2.0

            # OSMIUM: Inventory-Skewed Scalper
            if product == OSMIUM_SYMBOL:
                # FV adjusted for the "Seat on the Train" (Median logic)
                fv = mid_price - ((pos / pos_limit) * 3.0) 
                
                # Market Taking
                for sp, sv in sell_orders:
                    if sp <= fv - 0.6: # Slightly wider to cover the Access Fee
                        orders.append(Order(product, sp, min(abs(sv), pos_limit - pos)))
                
                # Market Making (Pennying)
                bid_pr = min(int(round(fv - 1)), best_bid + 1)
                ask_pr = max(int(round(fv + 1)), best_ask - 1)
                orders.append(Order(product, bid_pr, pos_limit - pos))
                orders.append(Order(product, ask_pr, -pos_limit - pos))

            # PEPPER ROOT: Directional Accel
            elif product == PEPPER_SYMBOL:
                if pos < pos_limit:
                    # Take volume to fill the new capacity immediately
                    orders.append(Order(product, best_ask, pos_limit - pos))

            result[product] = orders

        return result, 0, ""