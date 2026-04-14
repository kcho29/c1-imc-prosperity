from datamodel import OrderDepth, TradingState, Order
import json

class Trader:
    def run(self, state: TradingState):
        result = {}
        ema_pepper = None
        
        # Decode memory
        if state.traderData:
            try: ema_pepper = float(state.traderData)
            except: ema_pepper = None
            
        ema_alpha = 0.3 # Faster reaction to catch the trend

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: list[Order] = []
            current_pos = state.position.get(product, 0)
            limit = 80 
            
            # Get current market prices
            buy_orders = sorted(order_depth.buy_orders.items(), reverse=True)
            sell_orders = sorted(order_depth.sell_orders.items())
            
            if not buy_orders or not sell_orders: continue
            
            best_bid, bit_vol = buy_orders[0]
            best_ask, ask_vol = sell_orders[0]
            mid_price = (best_bid + best_ask) / 2

            # --- OSMIUM: Active Market Making ---
            if product == "ASH_COATED_OSMIUM":
                # Strategy: Always try to be 1 tick better than the best bot
                # but stay within the "Gravity" of 10k
                
                # If we have room to buy, overbid the current best buyer
                if current_pos < limit:
                    # We bid 1 tick higher than the best bid, but not above 10,001
                    bid_price = min(best_bid + 1, 10001)
                    orders.append(Order(product, int(bid_price), limit - current_pos))
                
                # If we have room to sell, undercut the current best seller
                if current_pos > -limit:
                    # We ask 1 tick lower than the best ask, but not below 9,999
                    ask_price = max(best_ask - 1, 9999)
                    orders.append(Order(product, int(ask_price), -limit - current_pos))

            # --- PEPPER_ROOT: Aggressive Trend Following ---
            elif product == "INTARIAN_PEPPER_ROOT":
                if ema_pepper is None: ema_pepper = mid_price
                ema_pepper = (mid_price * ema_alpha) + (ema_pepper * (1 - ema_alpha))
                
                # If price is moving up AT ALL, buy immediately (Market Take)
                if mid_price > ema_pepper:
                    buy_vol = limit - current_pos
                    if buy_vol > 0:
                        # We hit the 'best_ask' to guarantee the trade happens NOW
                        orders.append(Order(product, best_ask, buy_vol))
                
                # If price is moving down, sell immediately
                elif mid_price < ema_pepper:
                    sell_vol = -limit - current_pos
                    if sell_vol < 0:
                        orders.append(Order(product, best_bid, sell_vol))

            result[product] = orders

        traderData = str(ema_pepper) if ema_pepper else ""
        return result, 0, traderData 