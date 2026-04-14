Python
from datamodel import OrderDepth, TradingState, Order
import collections

class Trader:
    def __init__(self):
        # Tracking the trend for the Pepper Root
        self.ema_pepper = None
        self.ema_alpha = 0.2  # Smoothing factor for the trend

    def run(self, state: TradingState):
        result = {}

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: list[Order] = []
            
            # 1. Retrieve current state
            current_pos = state.position.get(product, 0)
            limit = 80
            
            # Calculate basic market info
            best_ask = min(order_depth.sell_orders.keys())
            best_bid = max(order_depth.buy_orders.keys())
            mid_price = (best_ask + best_bid) / 2

            # --- STRATEGY A: ASH_COATED_OSMIUM (The 10k Anchor) ---
            if product == "ASH_COATED_OSMIUM":
                fair_value = 10000 # Our "Divine Anchor"
                
                # Sniping: Take any mispriced bot orders immediately
                for ask, vol in order_depth.sell_orders.items():
                    if ask < fair_value:
                        buy_amount = min(-vol, limit - current_pos)
                        if buy_amount > 0:
                            orders.append(Order(product, ask, buy_amount))
                            current_pos += buy_amount

                for bid, vol in order_depth.buy_orders.items():
                    if bid > fair_value:
                        sell_amount = max(-vol, -limit - current_pos)
                        if sell_amount < 0:
                            orders.append(Order(product, bid, sell_amount))
                            current_pos += sell_amount

                # Layered Market Making: Overbid/Underbid to capture the spread
                # We place orders 1-2 ticks away from fair value to capture volatility
                bid_price = min(best_bid + 1, fair_value - 1)
                ask_price = max(best_ask - 1, fair_value + 1)
                
                # Skewing: If we are too Long, we stop buying and sell more aggressively
                if current_pos < limit:
                    orders.append(Order(product, int(bid_price), limit - current_pos))
                if current_pos > -limit:
                    orders.append(Order(product, int(ask_price), -limit - current_pos))

            # --- STRATEGY B: INTARIAN_PEPPER_ROOT (The Trend) ---
            elif product == "INTARIAN_PEPPER_ROOT":
                # Initialize or update EMA
                if self.ema_pepper is None:
                    self.ema_pepper = mid_price
                else:
                    self.ema_pepper = (mid_price * self.ema_alpha) + (self.ema_pepper * (1 - self.ema_alpha))
                
                # Momentum Logic: If price is above trend, we want to be MAX LONG
                if mid_price > self.ema_pepper + 2: # +2 is our "Edge" to avoid noise
                    buy_vol = limit - current_pos
                    if buy_vol > 0:
                        orders.append(Order(product, best_ask, buy_vol))
                
                # If price is below trend, we want to be MAX SHORT
                elif mid_price < self.ema_pepper - 2:
                    sell_vol = -limit - current_pos
                    if sell_vol < 0:
                        orders.append(Order(product, best_bid, sell_vol))

            result[product] = orders

        return result
