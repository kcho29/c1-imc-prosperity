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
        if self.wall_mid is not None:
            # 1. MARKET TAKING (Immediate execution on mispriced depth)
            for sp, sv in self.mkt_sell_orders.items():
                if sp <= self.wall_mid - 1:
                    self.bid(sp, sv)
                elif sp <= self.wall_mid and self.initial_position < 0:
                    volume = min(sv, abs(self.initial_position))
                    self.bid(sp, volume)

            for bp, bv in self.mkt_buy_orders.items():
                if bp >= self.wall_mid + 1:
                    self.ask(bp, bv)
                elif bp >= self.wall_mid and self.initial_position > 0:
                    volume = min(bv, self.initial_position)
                    self.ask(bp, volume)

            # 2. MARKET MAKING (High Aggression Pennying)
            # We penny the best current market prices to ensure we are first in line
            if self.best_bid is not None and self.best_ask is not None:
                # Bid exactly 1 tick above the current best bid to jump the queue
                bid_price = min(self.best_bid + 1, int(math.floor(self.wall_mid - 1)))
                # Ask exactly 1 tick below the current best ask
                ask_price = max(self.best_ask - 1, int(math.ceil(self.wall_mid + 1)))

                self.bid(bid_price, self.max_allowed_buy_volume)
                self.ask(ask_price, self.max_allowed_sell_volume)

            # Overbidding: Find the best bid still under the mid-point to capture spread
            for bp, bv in self.mkt_buy_orders.items():
                overbidding_price = bp + 1
                if bv > 1 and overbidding_price < self.wall_mid:
                    bid_price = max(bid_price, overbidding_price)
                    break
                elif bp < self.wall_mid:
                    bid_price = max(bid_price, bp)
                    break

            # Underbidding: Find the best ask still over the mid-point
            for sp, sv in self.mkt_sell_orders.items():
                underbidding_price = sp - 1
                if sv > 1 and underbidding_price > self.wall_mid:
                    ask_price = min(ask_price, underbidding_price)
                    break
                elif sp > self.wall_mid:
                    ask_price = min(ask_price, sp)
                    break

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