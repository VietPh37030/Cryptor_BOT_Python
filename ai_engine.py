# ai_engine.py (BẢN FIX LỖI ATR)
import pandas as pd
import pandas_ta as ta
import numpy as np
import os
import joblib 
import lightgbm as lgb 
from scipy.stats import linregress
from scipy.signal import argrelextrema
from config import MODEL_FILE

class AIEngine:
    def __init__(self):
        self.model = None
        self.model_path = MODEL_FILE.replace('.pkl', '.txt')
        
        if os.path.exists(self.model_path):
            try:
                self.model = lgb.Booster(model_file=self.model_path)
                print("🧠 AI Engine (LightGBM): Loaded.")
            except: self.train_initial_model()
        else:
            self.train_initial_model()

    def calculate_slope(self, series, period=5):
        slopes = [0.0] * len(series)
        if len(series) < period: return pd.Series(slopes, index=series.index)
        y = series.values
        x = np.arange(period)
        for i in range(period, len(y)):
            try:
                y_chunk = y[i-period:i]
                if np.isnan(y_chunk).any() or np.isinf(y_chunk).any(): slopes[i] = 0.0
                else:
                    slope, _, _, _, _ = linregress(x, y_chunk)
                    slopes[i] = 0.0 if np.isnan(slope) else slope
            except: slopes[i] = 0.0
        return pd.Series(slopes, index=series.index)

    def add_indicators(self, df):
        data = df.copy()
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in data.columns: data[col] = data[col].astype(float)

        # 1. Slope
        data['slope'] = self.calculate_slope(data['close'], period=5)
        
        # 2. RSI & MACD
        try: data['rsi'] = ta.rsi(data['close'], length=14)
        except: data['rsi'] = 50

        try:
            macd = ta.macd(data['close'])
            if macd is not None:
                data = pd.concat([data, macd], axis=1)
                for col in data.columns:
                    if col.startswith('MACD_'): data.rename(columns={col: 'macd'}, inplace=True)
                    elif col.startswith('MACDs_'): data.rename(columns={col: 'macd_signal'}, inplace=True)
                    elif col.startswith('MACDh_'): data.rename(columns={col: 'macd_hist'}, inplace=True)
        except: pass

        # 3. Bollinger Bands
        try:
            bb = ta.bbands(data['close'], length=20, std=2)
            if bb is not None:
                data = pd.concat([data, bb], axis=1)
                if len(bb.columns) >= 3:
                    cols = bb.columns
                    data.rename(columns={cols[0]: 'bb_lower', cols[1]: 'bb_mid', cols[2]: 'bb_upper'}, inplace=True)
                data['bb_pct'] = bb.iloc[:, -1]
        except: data['bb_pct'] = 0.5

        # 4. VWAP
        try:
            vwap = ta.vwap(data['high'], data['low'], data['close'], data['volume'])
            if vwap is not None:
                data['vwap'] = vwap 
                data['dist_vwap'] = (data['close'] - vwap) / vwap * 100
            else: data['dist_vwap'] = 0
        except: data['dist_vwap'] = 0

        # 5. ADX
        try:
            adx = ta.adx(data['high'], data['low'], data['close'], length=14)
            if adx is not None:
                data = pd.concat([data, adx], axis=1)
                found = False
                for c in data.columns:
                    if c.startswith('ADX'):
                        data.rename(columns={c: 'adx'}, inplace=True)
                        found = True; break
                if not found: data['adx'] = 25
            else: data['adx'] = 25
        except: data['adx'] = 25

        # 6. SuperTrend
        try:
            sti = ta.supertrend(data['high'], data['low'], data['close'], length=10, multiplier=3)
            if sti is not None:
                data = pd.concat([data, sti], axis=1)
                data.rename(columns={data.columns[-2]: 'supertrend', data.columns[-1]: 'supertrend_dir'}, inplace=True)
        except: pass

        # 7. ATR (Average True Range) <--- ĐÃ THÊM VÀO ĐÂY
        try:
            atr = ta.atr(data['high'], data['low'], data['close'], length=14)
            if atr is not None: data['atr'] = atr
            else: data['atr'] = 0
        except: data['atr'] = 0

        data['sentiment'] = np.random.uniform(-1, 1, size=len(data))
        data = data.fillna(0)
        return data

    def get_support_resistance(self, df, order=20):
        try:
            min_idx = argrelextrema(df['low'].values, np.less_equal, order=order)[0]
            supports = df.iloc[min_idx]['low'].values
            max_idx = argrelextrema(df['high'].values, np.greater_equal, order=order)[0]
            resistances = df.iloc[max_idx]['high'].values
            current_price = df['close'].iloc[-1]
            supports = sorted([x for x in supports if x < current_price], reverse=True)[:2]
            resistances = sorted([x for x in resistances if x > current_price])[:2]
            return supports, resistances
        except: return [], []

    def train_initial_model(self):
        print("⚠️ Training LightGBM Model...")
        X = np.random.rand(1000, 6) 
        y = np.random.randint(0, 2, 1000) 
        params = {'objective': 'binary', 'metric': 'binary_logloss', 'boosting_type': 'gbdt', 'num_leaves': 31, 'learning_rate': 0.05, 'feature_fraction': 0.9, 'verbose': -1}
        train_data = lgb.Dataset(X, label=y)
        self.model = lgb.train(params, train_data, num_boost_round=100)
        os.makedirs(os.path.dirname(MODEL_FILE), exist_ok=True)
        self.model.save_model(self.model_path)
        print("✅ LightGBM Model Ready!")

    def predict_probability(self, df):
        if self.model is None: return 0.5
        processed = self.add_indicators(df)
        if processed.empty: return 0.5
        last = processed.iloc[-1]
        slope = last.get('slope', 0)
        
        # Lấy features an toàn
        features = np.array([[
            last.get('slope', 0), 
            last.get('rsi', 50), 
            last.get('macd', 0), 
            last.get('bb_pct', 0.5), 
            last.get('dist_vwap', 0), 
            last.get('atr', 0) # <--- Giờ cột này đã có dữ liệu
        ]])
        
        try:
            prob = self.model.predict(features)[0]
            if slope > 0.6: prob += 0.15
            if slope < -0.6: prob -= 0.15
            return max(0.0, min(1.0, prob))
        except: return 0.5