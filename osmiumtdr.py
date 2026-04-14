from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict
import json
import math

# Constants defined for the Osmium-specific environment
OSMIUM_SYMBOL = 'ASH_COATED_OSMIUM'
POS_LIMIT = 80

class ProductTrader:
    def __init__(self, name, state, product_group=None):
        self.orders = []
        self.name = name
        self.state = state
        self.product_group = name if product_group is None else product_group

        # Position tracking
        self.position_limit = POS_LIMIT
        self.initial_position = self.state.position.get(self.name, 0)
        
        # Order Depth Analysis
        self.mkt_buy_orders, self.mkt_sell_orders = self.get_order_depth()
        self.bid_wall, self.wall_mid, self.ask_wall = self.get_walls()
        self.best_bid, self.best_ask = self.get_best_bid_ask()

        # Volume capacity tracking
        self.max_allowed_buy_volume = self.position_limit - self.initial_position
        self.max_allowed_sell_volume = self.position_limit + self.initial_position

    def get_order_depth(self):
        order_depth = self.state.order_depths.get(self.name, OrderDepth())
        # Sort buy orders descending (highest price first)
        buy_orders = {bp: abs(bv) for bp, bv in sorted(order_depth.buy_orders.items(), key=lambda x: x[0], reverse=True)}
        # Sort sell orders ascending (lowest price first)
        sell_orders = {sp: abs(sv) for sp, sv in sorted(order_depth.sell_orders.items(), key=lambda x: x[0])}
        return buy_orders, sell_orders

    def get_best_bid_ask(self):
        best_bid = max(self.mkt_buy_orders.keys()) if self.mkt_buy_orders else None
        best_ask = min(self.mkt_sell_orders.keys()) if self.mkt_sell_orders else None
        return best_bid, best_ask

    def get_walls(self):
        # Runner-up logic: Walls are the extremes of the visible book
        bid_wall = min(self.mkt_buy_orders.keys()) if self.mkt_buy_orders else None
        ask_wall = max(self.mkt_sell_orders.keys()) if self.mkt_sell_orders else None
        wall_mid = (bid_wall + ask_wall) / 2 if (bid_wall and ask_wall) else None
        return bid_wall, wall_mid, ask_wall

    def bid(self, price, volume):
        abs_volume = min(abs(int(volume)), self.max_allowed_buy_volume)
        if abs_volume > 0:
            self.orders.append(Order(self.name, int(price), abs_volume))
            self.max_allowed_buy_volume -= abs_volume

    def ask(self, price, volume):
        abs_volume = min(abs(int(volume)), self.max_allowed_sell_volume)
        if abs_volume > 0:
            self.orders.append(Order(self.name, int(price), -abs_volume))
            self.max_allowed_sell_volume -= abs_volume

class OsmiumTrader(ProductTrader):
    def get_orders(self):
        # We define a 'Fair Value' based on the mid-point of the walls
        if self.wall_mid is None:
            return self.orders

        fair_value = self.wall_mid

        # 1. MARKET TAKING with 'EDGE' (The Snipe)
        # We only 'take' if the profit is at least 2 ticks to avoid noise
        edge = 2
        for sp, sv in self.mkt_sell_orders.items():
            if sp <= fair_value - edge:
                self.bid(sp, sv)
        
        for bp, bv in self.mkt_buy_orders.items():
            if bp >= fair_value + edge:
                self.ask(bp, bv)

        # 2. SOPHISTICATED MARKET MAKING (The Skew)
        # We shift our target prices based on current inventory
        # If position is +40, we want to sell more than buy, so we lower both prices
        inventory_skew = -int(self.initial_position / 10) # Adjusts by 1 tick for every 10 units held
        
        # Base strategy: place orders 1-2 ticks around the skewed fair value
        bid_price = int(math.floor(fair_value + inventory_skew - 1))
        ask_price = int(math.ceil(fair_value + inventory_skew + 1))

        # Ensure we always have at least a 1-tick spread
        if bid_price >= ask_price:
            bid_price = ask_price - 1

        # Post orders to the book
        self.bid(bid_price, self.max_allowed_buy_volume)
        self.ask(ask_price, self.max_allowed_sell_volume)

        return self.orders

class Trader:
    def run(self, state: TradingState):
        result = {}
        # Only process Ash Coated Osmium as commanded
        if OSMIUM_SYMBOL in state.order_depths:
            trader = OsmiumTrader(OSMIUM_SYMBOL, state)
            result[OSMIUM_SYMBOL] = trader.get_orders()
            
        conversions = 0
        traderData = "" # No persistence needed for the static osmium strategy
        return result, conversions, traderData