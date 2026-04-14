from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json

class Trader:
    def __init__(self):
        # The sacred limits defined by the exchange
        self.limits = {
            "EMERALDS": 20,
            "TOMATOES": 20
        }
        
        # Emeralds are structurally anchored at 10k
        self.emerald_fv = 10000

    def bid(self):
        """Required for Round 2; returns a default value."""
        return 15

    def get_true_mid(self, order_depth: OrderDepth):
        """Calculates the Volume-Weighted Mid-Price to detect book imbalance."""
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return None
        
        best_bid = max(order_depth.buy_orders.keys())
        best_ask = min(order_depth.sell_orders.keys())
        
        bid_vol = order_depth.buy_orders[best_bid]
        ask_vol = abs(order_depth.sell_orders[best_ask])
        
        # True Mid weighted by opposite side volume
        return (best_bid * ask_vol + best_ask * bid_vol) / (bid_vol + ask_vol)

    def run(self, state: TradingState):
        """
        The main execution loop. 
        Returns (orders_dict, conversions, trader_data_string)
        """
        result = {}
        conversions = 0
        
        # Restore state across AWS Lambda calls
        try:
            trader_data = json.loads(state.traderData) if state.traderData else {}
        except:
            trader_data = {}

        for product in state.order_depths.keys():
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            # 1. Current State
            position = state.position.get(product, 0)
            limit = self.limits.get(product, 20)
            
            # 2. Determine Fair Value
            true_mid = self.get_true_mid(order_depth)
            if true_mid is None:
                continue
                
            if product == "EMERALDS":
                # Fundamental value is 10k; ignore market noise
                fair_value = self.emerald_fv
            else:
                # For Tomatoes, follow the Volume Imbalance
                fair_value = true_mid

            # 3. Inventory Skew (The "Leaning" Logic)
            # We shift our prices to encourage trades that bring position back to 0.
            # If we are Long (+), we lower prices to sell. If Short (-), we raise to buy.
            inventory_factor = position / limit  # Range: -1.0 to 1.0
            skew = -inventory_factor * 1.0       # Adjust 1.0 to tune aggressiveness
            
            # 4. Market Taking (Aggressive Sniping)
            # Take any ask below our skewed fair value
            sorted_asks = sorted(order_depth.sell_orders.items())
            for price, vol in sorted_asks:
                if price <= (fair_value + skew - 1) and position < limit:
                    buy_qty = min(abs(vol), limit - position)
                    orders.append(Order(product, price, buy_qty))
                    position += buy_qty
            
            # Take any bid above our skewed fair value
            sorted_bids = sorted(order_depth.buy_orders.items(), reverse=True)
            for price, vol in sorted_bids:
                if price >= (fair_value + skew + 1) and position > -limit:
                    sell_qty = min(vol, limit + position)
                    orders.append(Order(product, price, -sell_qty))
                    position -= sell_qty

            # 5. Market Making (Passive Quoting)
            # Place limit orders to capture the spread, adjusted by skew
            bid_price = int(round(fair_value + skew - 1))
            ask_price = int(round(fair_value + skew + 1))
            
            # Prevent spread crossing
            if bid_price >= ask_price:
                bid_price = ask_price - 1

            if position < limit:
                orders.append(Order(product, bid_price, limit - position))
            if position > -limit:
                orders.append(Order(product, ask_price, -(limit + position)))

            result[product] = orders

        # Serialize state for next iteration
        new_trader_data = json.dumps(trader_data)
        
        return result, conversions, new_trader_data
