from datamodel import OrderDepth, TradingState, Order
from typing import List
import json
import collections

class Trader:
    def __init__(self):
        # Local state is for the SAME iteration; 
        # Persistence across iterations must use traderData.
        self.limits = {"EMERALDS": 20, "TOMATOES": 20}
        self.emerald_fair_value = 10000

    def bid(self):
        """Required for Round 2, ignored for others."""
        return 15

    def run(self, state: TradingState):
        """
        The core logic called by the Prosperity exchange.
        Compliant with the (result, conversions, traderData) return format.
        """
        result = {}
        conversions = 0
        
        # --- Persistent State Recovery ---
        # We store the tomato price history in a list within traderData
        # to calculate moving averages across iterations in the stateless AWS environment.
        try:
            stored_data = json.loads(state.traderData) if state.traderData else {}
        except:
            stored_data = {}
        
        tomato_history = stored_data.get("tomato_history", [])

        for product in state.order_depths.keys():
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            # 1. Position Management
            current_pos = state.position.get(product, 0)
            limit = self.limits.get(product, 20)
            
            # Helper to calculate available room
            buy_limit = limit - current_pos
            sell_limit = -limit - current_pos # This is a negative number (e.g., -20 - 5 = -25)

            if product == "EMERALDS":
                # --- STRATEGY: PURE MEAN REVERSION ---
                # Based on the data, EMERALDS are anchored at 10,000.
                
                # A. Sniping: Taking profitable bot quotes
                # Buy from bots selling below 10k
                sorted_asks = sorted(order_depth.sell_orders.items())
                for price, vol in sorted_asks:
                    if price < self.emerald_fair_value and buy_limit > 0:
                        quantity = min(-vol, buy_limit)
                        orders.append(Order(product, price, quantity))
                        buy_limit -= quantity
                
                # Sell to bots buying above 10k
                sorted_bids = sorted(order_depth.buy_orders.items(), reverse=True)
                for price, vol in sorted_bids:
                    if price > self.emerald_fair_value and sell_limit < 0:
                        quantity = max(-vol, sell_limit)
                        orders.append(Order(product, price, quantity))
                        sell_limit -= quantity

                # B. Market Making: Providing liquidity at 9999/10001
                # Only if we still have position room
                if buy_limit > 0:
                    orders.append(Order(product, self.emerald_fair_value - 1, buy_limit))
                if sell_limit < 0:
                    orders.append(Order(product, self.emerald_fair_value + 1, sell_limit))

            elif product == "TOMATOES":
                # --- STRATEGY: SMA MOMENTUM ---
                mid_price = self.get_mid_price(order_depth)
                if mid_price:
                    tomato_history.append(mid_price)
                
                # Keep history to last 20 iterations
                if len(tomato_history) > 20:
                    tomato_history.pop(0)
                
                if len(tomato_history) >= 10:
                    avg = sum(tomato_history) / len(tomato_history)
                    
                    # Buy if price is trending up or significantly below average
                    if mid_price < avg - 1.5 and buy_limit > 0:
                        orders.append(Order(product, int(mid_price + 1), buy_limit))
                    # Sell if price is trending down or significantly above average
                    elif mid_price > avg + 1.5 and sell_limit < 0:
                        orders.append(Order(product, int(mid_price - 1), sell_limit))

            result[product] = orders

        # --- Persistent State Saving ---
        # Update traderData for the next iteration
        new_stored_data = {"tomato_history": tomato_history}
        trader_data_str = json.dumps(new_stored_data)

        return result, conversions, trader_data_str

    def get_mid_price(self, order_depth):
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return None
        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        return (best_bid + best_ask) / 2
