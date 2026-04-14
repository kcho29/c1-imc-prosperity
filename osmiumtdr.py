from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import json

class Trader:

    def run(self, state: TradingState):
        """
        Calculates a rolling average to determine the 'fair' price of 
        Ash Coated Osmium, then executes with absolute precision.
        """
        result = {}
        # Decode state from previous iterations or initialize
        if state.traderData == "":
            history = []
        else:
            history = json.loads(state.traderData)

        for product in state.order_depths:
            # We filter exclusively for the Osmium product
            # Replace "OSMIUM" with the specific symbol name in your environment
            if product != "AMETHYST": 
                continue

            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            # 1. Calculate the Mid-Price to determine the current market "truth"
            best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
            best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
            
            if best_ask and best_bid:
                mid_price = (best_ask + best_bid) / 2
                history.append(mid_price)
            
            # Keep only the last 20 ticks for a responsive moving average
            if len(history) > 20:
                history.pop(0)

            # 2. Define the Acceptable Price (The Fair Value)
            if len(history) > 0:
                acceptable_price = sum(history) / len(history)
            else:
                acceptable_price = 10000  # Default high-value starting point

            # 3. Execution Logic with Scrutiny
            # Buy if the market is selling below our calculated fair value
            if order_depth.sell_orders:
                for ask, amount in sorted(order_depth.sell_orders.items()):
                    if ask < acceptable_price:
                        # We take the full depth available (amount is negative for asks)
                        orders.append(Order(product, ask, -amount))
            
            # Sell if the market is buying above our calculated fair value
            if order_depth.buy_orders:
                for bid, amount in sorted(order_depth.buy_orders.items(), reverse=True):
                    if bid > acceptable_price:
                        # We sell into their bid (amount is positive for bids)
                        orders.append(Order(product, bid, -amount))
            
            result[product] = orders

        # Serialize history back to traderData to preserve context for the next tick
        new_traderData = json.dumps(history)
        conversions = 0
        return result, conversions, new_traderData