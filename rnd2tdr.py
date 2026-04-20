from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict

# Constants
OSMIUM_SYMBOL = 'ASH_COATED_OSMIUM'
PEPPER_SYMBOL = 'INTARIAN_PEPPER_ROOT'
POS_LIMIT = 80

class Trader:
    def bid(self):
        return 5150
    
    def run(self, state: TradingState):
        result = {}
        
        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            pos = state.position.get(product, 0)
            
            # Sort order books
            buy_orders = {bp: abs(bv) for bp, bv in sorted(order_depth.buy_orders.items(), key=lambda x: x[0], reverse=True)}
            sell_orders = {sp: abs(sv) for sp, sv in sorted(order_depth.sell_orders.items(), key=lambda x: x[0])}
            
            if not buy_orders or not sell_orders:
                continue
                
            best_bid = max(buy_orders.keys())
            best_ask = min(sell_orders.keys())
            mid_price = (best_bid + best_ask) / 2.0

            # =========================================================
            # 1. ASYMMETRIC TARGET ASSIGNMENTS (The God View Strategy)
            # =========================================================
            if product == OSMIUM_SYMBOL:
                target_pos = 0          # Always revert to flat
                max_skew = 3.0          # Tight skew for mean-reversion
                edge = 1                # Penny the market to get maximum fills
                
            elif product == PEPPER_SYMBOL:
                target_pos = POS_LIMIT  # Hardcoded Macro Uptrend
                max_skew = 15.0         # Massive skew to force accumulation
                edge = 5                # Wide edge to capture 10 ticks per scalp
                
            else:
                continue

            # =========================================================
            # 2. FAIR VALUE MATHEMATICS
            # =========================================================
            pos_error = pos - target_pos
            # If pos=0 and target=80, skew = (-80/80) * 15 = -15
            skew = (pos_error / POS_LIMIT) * max_skew
            
            # Adjusted FV shifts radically to correct inventory errors
            fv = mid_price - skew

            buy_vol_allowed = POS_LIMIT - pos
            sell_vol_allowed = -POS_LIMIT - pos

            # =========================================================
            # 3. HYBRID EXECUTION ENGINE
            # =========================================================
            
            # Phase A: MARKET TAKING (Snipe Mispriced Liquidity)
            # If the market is offering prices cheaper than our FV, take them instantly!
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

            # Phase B: MARKET MAKING (Provide Liquidity with remaining volume)
            my_bid = int(round(fv - edge))
            my_ask = int(round(fv + edge))

            # Smart Guardrails (Never quote worse than best market passively)
            my_bid = min(my_bid, best_bid + 1)
            my_ask = max(my_ask, best_ask - 1)

            # Ironclad Safety (Never self-cross)
            my_bid = min(my_bid, best_ask - 1)
            my_ask = max(my_ask, best_bid + 1)

            if my_bid >= my_ask:
                my_bid = int(mid_price) - 1
                my_ask = int(mid_price) + 1
                my_bid = min(my_bid, best_ask - 1)
                my_ask = max(my_ask, best_bid + 1)

            if buy_vol_allowed > 0:
                orders.append(Order(product, my_bid, buy_vol_allowed))
            if sell_vol_allowed < 0:
                orders.append(Order(product, my_ask, sell_vol_allowed))

            result[product] = orders

        return result, 0, ""