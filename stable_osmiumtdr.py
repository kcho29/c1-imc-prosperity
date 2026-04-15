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
        # We establish the Constant
        FAIR_VALUE = 10000 
        
        # 1. MEAN REVERSION SNIPING (The 'Deal' Hunter)
        # We only 'Take' if the deal is better than our 10k anchor
        for sp, sv in self.mkt_sell_orders.items():
            if sp <= FAIR_VALUE - 1: # Buying below 10k is a 'Deal'
                self.bid(sp, sv)

        for bp, bv in self.mkt_buy_orders.items():
            if bp >= FAIR_VALUE + 1: # Selling above 10k is a 'Deal'
                self.ask(bp, bv)

        # 2. MARKET MAKING (The 'Spread' Engine)
        # We place orders to capture the spread, but we SKEW them towards 10k
        
        # If we are below 10k, we want to be heavy on Bids
        # If we are above 10k, we want to be heavy on Asks
        bid_price = min(self.best_bid + 1, FAIR_VALUE - 1)
        ask_price = max(self.best_ask - 1, FAIR_VALUE + 1)

        # 3. INVENTORY SKEW (The Safeguard)
        # If Your Majesty is long (+40), we drop our bid to avoid more risk
        skew = -int(self.initial_position / 10) # Aggressive skew
        
        self.bid(bid_price + skew, self.max_allowed_buy_volume)
        self.ask(ask_price + skew, self.max_allowed_sell_volume)

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