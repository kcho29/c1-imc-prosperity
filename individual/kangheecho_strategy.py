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
    # v2 fixes (from run 98277):
    #   - STRICT inequality on snipe: buying AT 10000 has zero edge
    #     but ate 78% of volume and caused 8 position-limit hits.
    #   - Wider MM spread (±3 not ±1): any bid > 9992 captures the
    #     same incoming sell flow, so wider = more profit per fill.
    #   - Stronger position lean (0.25) + caps to never cross FV.
    # ──────────────────────────────────────────────────────────────
    def _trade_emeralds(self, depth: OrderDepth, buy_room: int, sell_room: int,
                        position: int, product: str) -> List[Order]:
        FV = self.emerald_fair_value
        orders: List[Order] = []

        # ── Phase 1: snipe truly mispriced levels ──
        # STRICT inequality: skip price == FV (zero edge, just builds risk)
        for price in sorted(depth.sell_orders):
            if price < FV and buy_room > 0:
                vol = min(-depth.sell_orders[price], buy_room)
                orders.append(Order(product, price, vol))
                buy_room -= vol

        for price in sorted(depth.buy_orders, reverse=True):
            if price > FV and sell_room < 0:
                vol = max(-depth.buy_orders[price], sell_room)
                orders.append(Order(product, price, vol))
                sell_room -= vol

        # ── Phase 2: post inside the spread ──
        # Wider base spread (±3): still better than bot's 9992/10008,
        # but earns 6 per round-trip instead of 2.
        pos_adj = round(position * 0.25)
        mm_bid = min(FV - 3 - pos_adj, FV - 1)   # never bid at or above FV
        mm_ask = max(FV + 3 - pos_adj, FV + 1)   # never ask at or below FV

        if buy_room > 0:
            orders.append(Order(product, mm_bid, buy_room))
        if sell_room < 0:
            orders.append(Order(product, mm_ask, sell_room))

        return orders

    # ──────────────────────────────────────────────────────────────
    # TOMATOES — EMA market-making with trend adaptation
    #
    # Fair value drifts (Day -2: +14, Day -1: -40).
    #
    # v2 fixes (from run 98277):
    #   - Faster EMA(10) for FV: EMA(20) lagged a sharp drop,
    #     causing a -190 drawdown at t=45k from stale long inventory.
    #   - Faster trend signal EMA(50) instead of EMA(100).
    #   - Wider snipe threshold (fair-3 not fair-1): reduces
    #     aggressive position-building when EMA is still catching up.
    #   - Stronger position lean (0.3) to flatten faster.
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
        ALPHA_FAST = 2 / 11    # EMA(10) — faster reaction
        ALPHA_SLOW = 2 / 51    # EMA(50) — faster trend signal

        ema_fast = stored.get("tom_ema_f", mid)
        ema_slow = stored.get("tom_ema_s", mid)

        ema_fast = ALPHA_FAST * mid + (1 - ALPHA_FAST) * ema_fast
        ema_slow = ALPHA_SLOW * mid + (1 - ALPHA_SLOW) * ema_slow

        stored["tom_ema_f"] = ema_fast
        stored["tom_ema_s"] = ema_slow

        fair = round(ema_fast)

        # ── Phase 1: snipe clearly mispriced levels ──
        # Wider threshold (3 not 1) — avoids sniping when EMA lags
        for price in sorted(depth.sell_orders):
            if price < fair - 3 and buy_room > 0:
                vol = min(-depth.sell_orders[price], buy_room)
                orders.append(Order(product, price, vol))
                buy_room -= vol

        for price in sorted(depth.buy_orders, reverse=True):
            if price > fair + 3 and sell_room < 0:
                vol = max(-depth.buy_orders[price], sell_room)
                orders.append(Order(product, price, vol))
                sell_room -= vol

        # ── Phase 2: post around fair value ──
        pos_adj = round(position * 0.3)
        trend_adj = round((ema_fast - ema_slow) * 0.4)

        HALF_SPREAD = 4
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
