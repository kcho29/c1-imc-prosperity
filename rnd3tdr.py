import numpy as np
from scipy.stats import norm
import json
from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict

class Trader:
    def __init__(self):
        # --- Constants determined from Your data ---
        self.LIMITS = {
            'HYDROGEL_PACK': 200,
            'VELVETFRUIT_EXTRACT': 200,
            'VEV_VOUCHER': 20 # Standard limit for vouchers in this round
        }
        self.IV = 0.0000205      # Implied Volatility per timestamp
        self.R = 0.0             # Risk-free rate
        self.TOTAL_TIME = 3000000 # Total timestamps across 3 days
        self.HEDGE_RATIO = 1.91   # HP Price / VFE Price
        self.SPREAD_WINDOW = 100  # Window for mean reversion
        
    def black_scholes(self, S, K, T, r, sigma):
        """Calculates fair value and Delta for a European Call Option."""
        if T <= 0:
            return max(0, S - K), (1.0 if S > K else 0.0)
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        delta = norm.cdf(d1)
        return price, delta

    def get_mid(self, depth: OrderDepth):
        """Returns the mid-price of an asset."""
        if not depth.buy_orders or not depth.sell_orders:
            return None
        return (max(depth.buy_orders.keys()) + min(depth.sell_orders.keys())) / 2

    def run(self, state: TradingState):
        result = {}
        # 1. Parse State Data (Mean Spread)
        trader_data = json.loads(state.traderData) if state.traderData else {"spread_sum": 0, "count": 0}
        
        # 2. Basic Market Info
        hp_depth = state.order_depths.get('HYDROGEL_PACK')
        vfe_depth = state.order_depths.get('VELVETFRUIT_EXTRACT')
        
        vfe_mid = self.get_mid(vfe_depth) if vfe_depth else None
        hp_mid = self.get_mid(hp_depth) if hp_depth else None
        
        current_ts = state.day * 1000000 + state.timestamp
        T_rem = max(0, self.TOTAL_TIME - current_ts)
        
        # Track total delta from options to hedge with Extract later
        total_options_delta = 0.0

        # --- PART 1: VOUCHER TRADING (BLACK-SCHOLES) ---
        for product, depth in state.order_depths.items():
            if product.startswith('VEV_'):
                if not vfe_mid: continue
                
                strike = float(product.split('_')[1])
                fair_val, delta = self.black_scholes(vfe_mid, strike, T_rem, self.R, self.IV)
                
                orders: List[Order] = []
                current_pos = state.position.get(product, 0)
                limit = self.LIMITS['VEV_VOUCHER']
                
                # Buy cheap options
                for price, vol in sorted(depth.sell_orders.items()):
                    if price < fair_val - 0.1 and current_pos < limit:
                        buy_vol = min(-vol, limit - current_pos)
                        orders.append(Order(product, price, buy_vol))
                        current_pos += buy_vol
                        total_options_delta += (buy_vol * delta)
                
                # Sell expensive options
                for price, vol in sorted(depth.buy_orders.items(), reverse=True):
                    if price > fair_val + 0.1 and current_pos > -limit:
                        sell_vol = max(-vol, -limit - current_pos)
                        orders.append(Order(product, price, sell_vol))
                        current_pos += sell_vol
                        total_options_delta += (sell_vol * delta)
                
                result[product] = orders

        # --- PART 2: BASE MATERIAL PAIR TRADING ---
        if vfe_mid and hp_mid:
            current_spread = hp_mid - (self.HEDGE_RATIO * vfe_mid)
            
            # Update rolling mean in traderData
            trader_data["spread_sum"] += current_spread
            trader_data["count"] += 1
            avg_spread = trader_data["spread_sum"] / trader_data["count"]
            
            hp_orders = []
            vfe_orders = result.get('VELVETFRUIT_EXTRACT', [])
            
            # If spread is high, HP is overvalued: Sell HP, Buy VFE
            if current_spread > avg_spread + 2:
                # Sell HP
                hp_bid = max(hp_depth.buy_orders.keys())
                hp_orders.append(Order('HYDROGEL_PACK', hp_bid, -hp_depth.buy_orders[hp_bid]))
                # Buy VFE (Hedge for Pair)
                vfe_ask = min(vfe_depth.sell_orders.keys())
                vfe_orders.append(Order('VELVETFRUIT_EXTRACT', vfe_ask, vfe_depth.sell_orders[vfe_ask]))
                
            # If spread is low, HP is undervalued: Buy HP, Sell VFE
            elif current_spread < avg_spread - 2:
                # Buy HP
                hp_ask = min(hp_depth.sell_orders.keys())
                hp_orders.append(Order('HYDROGEL_PACK', hp_ask, -hp_depth.sell_orders[hp_ask]))
                # Sell VFE (Hedge for Pair)
                vfe_bid = max(vfe_depth.buy_orders.keys())
                vfe_orders.append(Order('VELVETFRUIT_EXTRACT', vfe_bid, -vfe_depth.buy_orders[vfe_bid]))
            
            result['HYDROGEL_PACK'] = hp_orders
            result['VELVETFRUIT_EXTRACT'] = vfe_orders

        # --- PART 3: DELTA HEDGING (Final Scrutiny) ---
        # Adjust Velvetfruit Extract position to offset the delta risk from the vouchers
        if 'VELVETFRUIT_EXTRACT' in result and abs(total_options_delta) > 0.5:
            # If we are long 10 units of an option with 0.5 delta, we need to sell 5 units of VFE
            hedge_amount = int(round(-total_options_delta))
            if hedge_amount > 0: # Buy VFE to hedge
                vfe_ask = min(vfe_depth.sell_orders.keys())
                result['VELVETFRUIT_EXTRACT'].append(Order('VELVETFRUIT_EXTRACT', vfe_ask, hedge_amount))
            elif hedge_amount < 0: # Sell VFE to hedge
                vfe_bid = max(vfe_depth.buy_orders.keys())
                result['VELVETFRUIT_EXTRACT'].append(Order('VELVETFRUIT_EXTRACT', vfe_bid, hedge_amount))

        return result, 0, json.dumps(trader_data)