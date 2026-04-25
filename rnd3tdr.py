import json
import math
from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict

class Trader:
    def __init__(self):
        # --- Constants determined from Your data ---
        self.LIMITS = {
            'HYDROGEL_PACK': 200,
            'VELVETFRUIT_EXTRACT': 200,
            'VEV_VOUCHER': 20
        }
        # Volatility and Time constants
        self.SIGMA = 0.0000205      
        self.TOTAL_TIME = 3000000 
        self.HEDGE_RATIO = 1.91   
        
    def erf(self, x):
        """Abramowitz and Stegun approximation for Error Function."""
        a1 =  0.254829592
        a2 = -0.284496736
        a3 =  1.421413741
        a4 = -1.453152027
        a5 =  1.061405429
        p  =  0.3275911

        sign = 1 if x >= 0 else -1
        x = abs(x)
        t = 1.0 / (1.0 + p * x)
        y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
        return sign * y

    def norm_cdf(self, x):
        """Standard Normal Cumulative Distribution Function."""
        return 0.5 * (1.0 + self.erf(x / math.sqrt(2.0)))

    def black_scholes_logic(self, S, K, T, sigma):
        """Calculates fair value and Delta without external libraries."""
        if T <= 0:
            return max(0, S - K), (1.0 if S > K else 0.0)
        
        # d1 = [ln(S/K) + (0.5 * sigma^2) * T] / (sigma * sqrt(T))
        d1 = (math.log(S / K) + (0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        
        price = S * self.norm_cdf(d1) - K * self.norm_cdf(d2)
        delta = self.norm_cdf(d1)
        return price, delta

    def get_mid(self, depth: OrderDepth):
        if not depth.buy_orders or not depth.sell_orders:
            return None
        return (max(depth.buy_orders.keys()) + min(depth.sell_orders.keys())) / 2

    def run(self, state: TradingState):
        result = {}
        # Persistent data for spread tracking
        trader_data = json.loads(state.traderData) if state.traderData else {"spread_sum": 0, "count": 0}
        
        hp_depth = state.order_depths.get('HYDROGEL_PACK')
        vfe_depth = state.order_depths.get('VELVETFRUIT_EXTRACT')
        vfe_mid = self.get_mid(vfe_depth) if vfe_depth else None
        hp_mid = self.get_mid(hp_depth) if hp_depth else None
        
        current_ts = state.day * 1000000 + state.timestamp
        T_rem = max(1, self.TOTAL_TIME - current_ts) # Avoid div by zero
        
        total_options_delta = 0.0

        # --- PART 1: OPTIONS (VOUCHERS) ---
        for product, depth in state.order_depths.items():
            if product.startswith('VEV_'):
                if not vfe_mid: continue
                
                strike = float(product.split('_')[1])
                fair_val, delta = self.black_scholes_logic(vfe_mid, strike, T_rem, self.SIGMA)
                
                orders: List[Order] = []
                current_pos = state.position.get(product, 0)
                limit = self.LIMITS['VEV_VOUCHER']
                
                # Scrutinize sell orders (Buying opportunity)
                for price, vol in sorted(depth.sell_orders.items()):
                    if price < fair_val - 0.1 and current_pos < limit:
                        buy_vol = min(-vol, limit - current_pos)
                        orders.append(Order(product, price, buy_vol))
                        current_pos += buy_vol
                        total_options_delta += (buy_vol * delta)
                
                # Scrutinize buy orders (Selling opportunity)
                for price, vol in sorted(depth.buy_orders.items(), reverse=True):
                    if price > fair_val + 0.1 and current_pos > -limit:
                        sell_vol = max(-vol, -limit - current_pos)
                        orders.append(Order(product, price, sell_vol))
                        current_pos += sell_vol
                        total_options_delta += (sell_vol * delta)
                
                result[product] = orders

        # --- PART 2: PAIR TRADING (BASE MATERIALS) ---
        if vfe_mid and hp_mid:
            current_spread = hp_mid - (self.HEDGE_RATIO * vfe_mid)
            trader_data["spread_sum"] += current_spread
            trader_data["count"] += 1
            avg_spread = trader_data["spread_sum"] / trader_data["count"]
            
            hp_orders = []
            vfe_orders = result.get('VELVETFRUIT_EXTRACT', [])
            
            if current_spread > avg_spread + 2: # HP overpriced
                hp_bid = max(hp_depth.buy_orders.keys())
                hp_orders.append(Order('HYDROGEL_PACK', hp_bid, -hp_depth.buy_orders[hp_bid]))
            elif current_spread < avg_spread - 2: # HP underpriced
                hp_ask = min(hp_depth.sell_orders.keys())
                hp_orders.append(Order('HYDROGEL_PACK', hp_ask, -hp_depth.sell_orders[hp_ask]))
            
            result['HYDROGEL_PACK'] = hp_orders
            result['VELVETFRUIT_EXTRACT'] = vfe_orders

        # --- PART 3: DELTA HEDGING ---
        if 'VELVETFRUIT_EXTRACT' in result and abs(total_options_delta) >= 1:
            hedge_amount = int(round(-total_options_delta))
            if hedge_amount > 0:
                result['VELVETFRUIT_EXTRACT'].append(Order('VELVETFRUIT_EXTRACT', min(vfe_depth.sell_orders.keys()), hedge_amount))
            elif hedge_amount < 0:
                result['VELVETFRUIT_EXTRACT'].append(Order('VELVETFRUIT_EXTRACT', max(vfe_depth.buy_orders.keys()), hedge_amount))

        return result, 0, json.dumps(trader_data)