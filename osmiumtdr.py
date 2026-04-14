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
        if not self.buy_orders or not self.sell_orders:
            return self.orders

        # 1. VWAP Fair Value
        best_bid, bid_vol = list(self.buy_orders.items())[0]
        best_ask, ask_vol = list(self.sell_orders.items())[0]
        fv = (best_bid * ask_vol + best_ask * bid_vol) / (bid_vol + ask_vol)

        # 2. MARKET TAKING (The Sniper)
        # Snatch immediate mispriced liquidity
        for price, vol in self.sell_orders.items():
            if price <= fv - 1: # Tightened from 2 to 1 for more aggression
                self.bid(price, vol)
        for price, vol in self.buy_orders.items():
            if price >= fv + 1: # Tightened from 2 to 1 for more aggression
                self.ask(price, vol)

        # 3. AGGRESSIVE PASSIVE PENNYING
        # We target 1 tick above/below best market prices
        bid_price = best_bid + 1
        ask_price = best_ask - 1

        # Inventory management: If we are near the 80 limit, we back off
        # Long position -> lower our bid price to buy less aggressively
        # Short position -> raise our ask price to sell less aggressively
        if self.initial_position > 40:
            bid_price = best_bid # Stop jumping the queue to buy
        elif self.initial_position < -40:
            ask_price = best_ask # Stop jumping the queue to sell

        # Final Scrutiny: Ensure we don't cross our own spread
        if bid_price >= ask_price:
            bid_price = int(math.floor(fv - 1))
            ask_price = int(math.ceil(fv + 1))

        # Deploy the full 80-item capacity into the spread
        self.bid(bid_price, self.max_buy)
        self.ask(ask_price, self.max_sell)

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