from datamodel import OrderDepth, TradingState, Order
import json

class Trader:
    def run(self, state: TradingState):
        result = {}
        
        # --- Memory Management ---
        # We decode the EMA from the previous tick's traderData
        ema_pepper = None
        if state.traderData:
            ema_pepper = float(state.traderData)
            
        ema_alpha = 0.2 

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: list[Order] = []
            current_pos = state.position.get(product, 0)
            limit = 80 # Updated to Round 1 Limits
            
            # Basic Price Scrutiny
            sell_prices = sorted(order_depth.sell_orders.keys())
            buy_prices = sorted(order_depth.buy_orders.keys(), reverse=True)
            
            if not sell_prices or not buy_prices:
                continue
                
            best_ask = sell_prices[0]
            best_bid = buy_prices[0]
            mid_price = (best_ask + best_bid) / 2

            # --- OSMIUM: Mean Reversion (The Anchor) ---
            if product == "ASH_COATED_OSMIUM":
                fair_value = 10000 
                
                # Market Making: Overbid/Underbid to capture the 10k gravity
                # We aim to buy at 9999 and sell at 10001
                bid_price = 9999
                ask_price = 10001
                
                if current_pos < limit:
                    orders.append(Order(product, bid_price, limit - current_pos))
                if current_pos > -limit:
                    orders.append(Order(product, ask_price, -limit - current_pos))

            # --- PEPPER_ROOT: Trend Following (The Wave) ---
            elif product == "INTARIAN_PEPPER_ROOT":
                if ema_pepper is None:
                    ema_pepper = mid_price
                else:
                    ema_pepper = (mid_price * ema_alpha) + (ema_pepper * (1 - ema_alpha))
                
                # If price is trending up, we want to be +80
                if mid_price > ema_pepper + 1:
                    buy_vol = limit - current_pos
                    if buy_vol > 0:
                        orders.append(Order(product, best_ask, buy_vol))
                
                # If price is trending down, we want to be -80
                elif mid_price < ema_pepper - 1:
                    sell_vol = -limit - current_pos
                    if sell_vol < 0:
                        orders.append(Order(product, best_bid, sell_vol))

        # --- Save Memory for Next Tick ---
        traderData = str(ema_pepper) if ema_pepper else ""
        
        return result, 0, traderData # Correct return format
