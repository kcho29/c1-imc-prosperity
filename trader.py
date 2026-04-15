from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict
import json
import math

# Constants
OSMIUM_SYMBOL = 'ASH_COATED_OSMIUM'
PEPPER_SYMBOL = 'INTARIAN_PEPPER_ROOT'
POS_LIMIT = 80
END_TIME = 999000  # Adjust based on specific day length

class ProductTrader:
    def __init__(self, name, state):
        self.orders = []
        self.name = name
        self.state = state
        self.position_limit = POS_LIMIT
        self.initial_position = self.state.position.get(self.name, 0)
        
        # Order Depth Analysis
        order_depth = self.state.order_depths.get(self.name, OrderDepth())
        # Sort buy orders descending (highest price first)
        self.mkt_buy_orders = {bp: abs(bv) for bp, bv in sorted(order_depth.buy_orders.items(), key=lambda x: x[0], reverse=True)}
        # Sort sell orders ascending (lowest price first)
        self.mkt_sell_orders = {sp: abs(sv) for sp, sv in sorted(order_depth.sell_orders.items(), key=lambda x: x[0])}

        # Volume capacity tracking
        self.max_allowed_buy_volume = self.position_limit - self.initial_position
        self.max_allowed_sell_volume = self.position_limit + self.initial_position

        # Mid-price and Wall discovery
        self.best_bid = max(self.mkt_buy_orders.keys()) if self.mkt_buy_orders else None
        self.best_ask = min(self.mkt_sell_orders.keys()) if self.mkt_sell_orders else None
        
        self.bid_wall = min(self.mkt_buy_orders.keys()) if self.mkt_buy_orders else None
        self.ask_wall = max(self.mkt_sell_orders.items(), key=lambda x: x[0])[0] if self.mkt_sell_orders else None
        self.wall_mid = (self.bid_wall + self.ask_wall) / 2 if (self.bid_wall and self.ask_wall) else None

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
            # 1. MARKET TAKING
            for sp, sv in self.mkt_sell_orders.items():
                if sp <= self.wall_mid - 2:
                    self.bid(sp, sv)
                elif sp <= self.wall_mid and self.initial_position < 0:
                    volume = min(sv, abs(self.initial_position))
                    self.bid(sp, volume)

            for bp, bv in self.mkt_buy_orders.items():
                if bp >= self.wall_mid + 2:
                    self.ask(bp, bv)
                elif bp >= self.wall_mid and self.initial_position > 0:
                    volume = min(bv, self.initial_position)
                    self.ask(bp, volume)

            # 2. MARKET MAKING
            bid_price = int(self.bid_wall + 1)
            ask_price = int(self.ask_wall - 1)

            for bp, bv in self.mkt_buy_orders.items():
                overbidding_price = bp + 1
                if bv > 1 and overbidding_price < self.wall_mid:
                    bid_price = max(bid_price, overbidding_price)
                    break
                elif bp < self.wall_mid:
                    bid_price = max(bid_price, bp)
                    break

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

class PepperTrader(ProductTrader):
    def get_orders(self):
        # SOVEREIGN MANDATE: Buy and Hold until the end
        if self.state.timestamp < END_TIME:
            if self.initial_position < POS_LIMIT:
                # We use the best_ask to ensure immediate fill for the moonshot
                if self.best_ask:
                    self.bid(self.best_ask, self.max_allowed_buy_volume)
        else:
            # Final Liquidation at the closing bell
            if self.initial_position > 0:
                if self.best_bid:
                    self.ask(self.best_bid, self.initial_position)
        
        return self.orders

class Trader:
    def run(self, state: TradingState):
        result = {}
        
        # Process Osmium (Scalping)
        if OSMIUM_SYMBOL in state.order_depths:
            o_trader = OsmiumTrader(OSMIUM_SYMBOL, state)
            result[OSMIUM_SYMBOL] = o_trader.get_orders()
            
        # Process Pepper Root (Buy and Hold)
        if PEPPER_SYMBOL in state.order_depths:
            p_trader = PepperTrader(PEPPER_SYMBOL, state)
            result[PEPPER_SYMBOL] = p_trader.get_orders()
            
        return result, 0, ""