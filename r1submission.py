Python
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
            
            # Current inventory position
            pos = state.position.get(product, 0)
            
            # Sort order books for analysis
            # buy_orders: highest price first (for selling into)
            buy_orders = {bp: abs(bv) for bp, bv in sorted(order_depth.buy_orders.items(), key=lambda x: x[0], reverse=True)}
            # sell_orders: lowest price first (for buying from)
            sell_orders = {sp: abs(sv) for sp, sv in sorted(order_depth.sell_orders.items(), key=lambda x: x[0])}
            
            if not buy_orders and not sell_orders:
                continue

            # =========================================================
            # 1. INTARIAN PEPPER ROOT: AGGRESSIVE ACCUMULATION
            # Strategy: Cross the spread to hit POS_LIMIT instantly.
            # =========================================================
            if product == PEPPER_SYMBOL:
                max_buy = POS_LIMIT - pos
                if max_buy > 0:
                    best_ask = min(sell_orders.keys()) if sell_orders else None
                    if best_ask is not None:
                        # Direct Market Taking to ensure position capture
                        orders.append(Order(product, best_ask, max_buy))
            
            # =========================================================
            # 2. ASH COATED OSMIUM: CONTINUOUS SKEW MARKET MAKING
            # Strategy: Use inventory-weighted FV to provide liquidity.
            # =========================================================
            elif product == OSMIUM_SYMBOL:
                best_bid = max(buy_orders.keys()) if buy_orders else None
                best_ask = min(sell_orders.keys()) if sell_orders else None
                
                if best_bid is None or best_ask is None:
                    continue
                    
                mid_price = (best_bid + best_ask) / 2.0
                
                # Parameters for Osmium Mean Reversion
                target_pos = 0          
                max_skew = 3.0          
                edge = 1                
                
                # Calculate Fair Value based on Inventory Error
                pos_error = pos - target_pos
                skew = (pos_error / POS_LIMIT) * max_skew
                fv = mid_price - skew

                buy_vol_allowed = POS_LIMIT - pos
                sell_vol_allowed = -POS_LIMIT - pos

                # Phase A: Market Taking (Snipe Mispriced Liquidity)
                for sp, sv in sell_orders.items():
                    if sp <= fv - 0.5 and buy_vol_allowed > 0:
                        vol = min(sv, buy_vol_allowed)
                        orders.append(Order(product, sp, vol))
                        buy_vol_allowed -= vol

                for bp, bv in buy_orders.items():
                    if bp >= fv + 0.5 and sell_vol_allowed < 0:
                        vol = min(bv, abs(sell_vol_allowed))
                        orders.append(Order(product, bp, -vol))
                        sell_vol_allowed += vol

                # Phase B: Market Making (Pennying the Spread)
                my_bid = int(round(fv - edge))
                my_ask = int(round(fv + edge))

                # Guardrails to remain competitive and avoid self-crossing
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