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
        if not self.mkt_buy_orders or not self.mkt_sell_orders:
            return self.orders

        # 1. VWAP Fair Value (Superior to simple mid-price)
        best_bid, bid_vol = list(self.mkt_buy_orders.items())[0]
        best_ask, ask_vol = list(self.mkt_sell_orders.items())[0]
        fv = (best_bid * ask_vol + best_ask * bid_vol) / (bid_vol + ask_vol)

        # 2. Market Taking (Aggressive Sniping)
        # We take anything better than fv to ensure no profit escapes
        for price, vol in self.mkt_sell_orders.items():
            if price <= fv - 1:
                self.bid(price, vol)
        for price, vol in self.mkt_buy_orders.items():
            if price >= fv + 1:
                self.ask(price, vol)

        # 3. Layered Market Making with Inventory Skew
        # Position-based skew: -1 tick for every 20 units of inventory
        skew = -int(self.initial_position / 20)
        
        # Layer 1: Aggressive Pennying (The Front Line)
        self.bid(best_bid + 1 + skew, self.max_allowed_buy_volume // 2)
        self.ask(best_ask - 1 + skew, self.max_allowed_sell_volume // 2)
        
        # Layer 2: Deep Liquidity (The Safety Net)
        self.bid(best_bid + skew, self.max_allowed_buy_volume)
        self.ask(best_ask + skew, self.max_allowed_sell_volume)

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