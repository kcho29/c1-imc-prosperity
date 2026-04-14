from datamodel import OrderDepth, TradingState, Order
from typing import List
import json


class Trader:
    def __init__(self):
        self.limits = {"EMERALDS": 20, "TOMATOES": 20}
        self.emerald_fair_value = 10000

    def bid(self):
        """Required for Round 2, ignored for others."""
        return 15

    def run(self, state: TradingState):
        """
        Core logic called each tick by the Prosperity exchange.
        Returns (result, conversions, traderData).
        """
        result = {}
        conversions = 0

        # ── Persistent state recovery ──
        # We store TOMATO EMA values across ticks since the environment
        # is stateless (AWS Lambda) and __init__ re-runs each iteration.
        try:
            stored = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            stored = {}

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []

            current_pos = state.position.get(product, 0)
            limit = self.limits.get(product, 20)
            buy_room = limit - current_pos       # positive: units we can still buy
            sell_room = -limit - current_pos      # negative: units we can still sell

            if product == "EMERALDS":
                orders = self._trade_emeralds(order_depth, buy_room, sell_room, current_pos, product)

            elif product == "TOMATOES":
                orders = self._trade_tomatoes(order_depth, buy_room, sell_room, current_pos, product, stored)

            result[product] = orders

        return result, conversions, json.dumps(stored)

    # ──────────────────────────────────────────────────────────────
    # EMERALDS — market-make around the known fair value of 10 000
    #
    # The book is almost always 9992 / 10008 (spread = 16).
    # Nobody quotes inside, so we step in front of the bots.
    #
    # Phase 1 (snipe): take any order priced at or through fair value.
    # Phase 2 (post):  bid at 9999, ask at 10001, skewed by position.
    # ──────────────────────────────────────────────────────────────
    def _trade_emeralds(self, depth: OrderDepth, buy_room: int, sell_room: int,
                        position: int, product: str) -> List[Order]:
        FV = self.emerald_fair_value
        orders: List[Order] = []

        # ── Phase 1: snipe mispriced levels ──
        # Buy from anyone selling at or below fair value
        for price in sorted(depth.sell_orders):
            if price <= FV and buy_room > 0:
                vol = min(-depth.sell_orders[price], buy_room)
                orders.append(Order(product, price, vol))
                buy_room -= vol

        # Sell to anyone buying at or above fair value
        for price in sorted(depth.buy_orders, reverse=True):
            if price >= FV and sell_room < 0:
                vol = max(-depth.buy_orders[price], sell_room)
                orders.append(Order(product, price, vol))
                sell_room -= vol

        # ── Phase 2: post inside the spread ──
        # Lean quotes against inventory to flatten position naturally.
        pos_adj = round(position * 0.15)
        mm_bid = FV - 1 - pos_adj
        mm_ask = FV + 1 - pos_adj

        if buy_room > 0:
            orders.append(Order(product, mm_bid, buy_room))
        if sell_room < 0:
            orders.append(Order(product, mm_ask, sell_room))

        return orders

    # ──────────────────────────────────────────────────────────────
    # TOMATOES — EMA market-making with trend adaptation
    #
    # Fair value is NOT fixed; it drifts (Day -2: +14, Day -1: -40).
    # We track it with EMA(20) and market-make around it at +/- 5.
    #
    # Phase 1 (snipe): take orders > 1 away from FV.
    # Phase 2 (post):  bid FV-5, ask FV+5, skewed by position + trend.
    # ──────────────────────────────────────────────────────────────
    def _trade_tomatoes(self, depth: OrderDepth, buy_room: int, sell_room: int,
                        position: int, product: str, stored: dict) -> List[Order]:
        orders: List[Order] = []

        best_bid = max(depth.buy_orders) if depth.buy_orders else None
        best_ask = min(depth.sell_orders) if depth.sell_orders else None
        if best_bid is None or best_ask is None:
            return orders

        mid = (best_bid + best_ask) / 2

        # ── Update EMAs ──
        ALPHA_FAST = 2 / 21    # EMA(20)
        ALPHA_SLOW = 2 / 101   # EMA(100)

        ema_fast = stored.get("tom_ema_f", mid)
        ema_slow = stored.get("tom_ema_s", mid)

        ema_fast = ALPHA_FAST * mid + (1 - ALPHA_FAST) * ema_fast
        ema_slow = ALPHA_SLOW * mid + (1 - ALPHA_SLOW) * ema_slow

        stored["tom_ema_f"] = ema_fast
        stored["tom_ema_s"] = ema_slow

        fair = round(ema_fast)

        # ── Phase 1: snipe mispriced levels ──
        for price in sorted(depth.sell_orders):
            if price < fair - 1 and buy_room > 0:
                vol = min(-depth.sell_orders[price], buy_room)
                orders.append(Order(product, price, vol))
                buy_room -= vol

        for price in sorted(depth.buy_orders, reverse=True):
            if price > fair + 1 and sell_room < 0:
                vol = max(-depth.buy_orders[price], sell_room)
                orders.append(Order(product, price, vol))
                sell_room -= vol

        # ── Phase 2: post around fair value ──
        pos_adj = round(position * 0.2)
        trend_adj = round((ema_fast - ema_slow) * 0.3)

        HALF_SPREAD = 5
        mm_bid = fair - HALF_SPREAD - pos_adj + trend_adj
        mm_ask = fair + HALF_SPREAD - pos_adj + trend_adj

        if buy_room > 0:
            orders.append(Order(product, mm_bid, buy_room))
        if sell_room < 0:
            orders.append(Order(product, mm_ask, sell_room))

        return orders

    def get_mid_price(self, order_depth: OrderDepth):
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return None
        return (max(order_depth.buy_orders) + min(order_depth.sell_orders)) / 2