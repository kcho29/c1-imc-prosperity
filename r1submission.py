from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict

# Constants
OSMIUM_SYMBOL = 'ASH_COATED_OSMIUM'
PEPPER_SYMBOL = 'INTARIAN_PEPPER_ROOT'
POS_LIMIT = 80

class Trader:
    def run(self, state: TradingState):
        result = {}
        
        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            pos = state.position.get(product, 0)
            
            # Sort order books
            buy_orders = sorted(order_depth.buy_orders.items(), key=lambda x: x[0], reverse=True)
            sell_orders = sorted(order_depth.sell_orders.items(), key=lambda x: x[0])
            
            if not buy_orders and not sell_orders:
                continue

            # =========================================================
            # 1. PEPPER ROOT: AGGRESSIVE MARKET TAKING
            # =========================================================
            if product == PEPPER_SYMBOL:
                max_buy = POS_LIMIT - pos
                if max_buy > 0 and sell_orders:
                    # Take the best available ask immediately to fill position
                    best_ask, best_ask_vol = sell_orders[0]
                    # Ensure we don't buy more than available in that tick
                    volume_to_take = min(max_buy, abs(best_ask_vol))
                    orders.append(Order(product, best_ask, volume_to_take))
            
            # =========================================================
            # 2. OSMIUM: SKEWED MARKET MAKING
            # =========================================================
            elif product == OSMIUM_SYMBOL:
                best_bid = buy_orders[0][0] if buy_orders else None
                best_ask = sell_orders[0][0] if sell_orders else None
                
                if best_bid is None or best_ask is None:
                    continue
                    
                mid_price = (best_bid + best_ask) / 2.0
                
                # Parameters
                target_pos = 0          
                max_skew = 3.0          
                edge = 1                
                
                # Fair Value calculation via Inventory Skew
                pos_error = pos - target_pos
                skew = (pos_error / POS_LIMIT) * max_skew
                fv = mid_price - skew

                buy_vol_allowed = POS_LIMIT - pos
                sell_vol_allowed = -POS_LIMIT - pos

                # Market Taking Phase
                for sp, sv in sell_orders:
                    if sp <= fv - 0.5 and buy_vol_allowed > 0:
                        vol = min(abs(sv), buy_vol_allowed)
                        orders.append(Order(product, sp, vol))
                        buy_vol_allowed -= vol

                for bp, bv in buy_orders:
                    if bp >= fv + 0.5 and sell_vol_allowed < 0:
                        vol = min(abs(bv), abs(sell_vol_allowed))
                        orders.append(Order(product, bp, -vol))
                        sell_vol_allowed += vol

                # Market Making Phase
                my_bid = int(round(fv - edge))
                my_ask = int(round(fv + edge))

                # Safeguards
                my_bid = min(my_bid, best_bid + 1)
                my_ask = max(my_ask, best_ask - 1)
                my_bid = min(my_bid, best_ask - 1)
                my_ask = max(my_ask, best_bid + 1)

                if buy_vol_allowed > 0:
                    orders.append(Order(product, my_bid, buy_vol_allowed))
                if sell_vol_allowed < 0:
                    orders.append(Order(product, my_ask, sell_vol_allowed))

            result[product] = orders

        return result, 0, ""