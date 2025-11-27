import pandas as pd
import pandas_ta as ta
import numpy as np
import os
import joblib 
from scipy.stats import linregress
from sklearn.ensemble import RandomForestClassifier
from config import MODEL_FILE

class AIEngine:
    def __init__(self):
        self.model = None
        if os.path.exists(MODEL_FILE):
            try:
                self.model = joblib.load(MODEL_FILE)
                print("🧠 AI Engine: Loaded.")
            except: self.train_initial_model()
        else: self.train_initial_model()

    def calculate_slope(self, series, period=5):
        slopes = [0] * len(series)
        if len(series) < period: return pd.Series(slopes, index=series.index)
        y = series.values
        x = np.arange(period)
        for i in range(period, len(y)):
            slope, _, _, _, _ = linregress(x, y[i-period:i])
            slopes[i] = slope
        return pd.Series(slopes, index=series.index)

    def add_indicators(self, df):
        data = df.copy()
        # 1. Slope (Quan trọng nhất)
        data['slope'] = self.calculate_slope(data['close'], period=7)
        
        # 2. VWAP & Dist
        try:
            vwap = ta.vwap(data['high'], data['low'], data['close'], data['volume'])
            if vwap is not None:
                data['vwap'] = vwap
                data['dist_vwap'] = (data['close'] - data['vwap']) / data['vwap'] * 100
            else: data['dist_vwap'] = 0
        except: data['dist_vwap'] = 0

        # 3. RSI & ADX
        data['rsi'] = ta.rsi(data['close'], length=14)
        try:
            adx = ta.adx(data['high'], data['low'], data['close'], length=14)
            if adx is not None:
                data = pd.concat([data, adx], axis=1)
                data.rename(columns={data.columns[-3]: 'adx'}, inplace=True)
        except: data['adx'] = 20

        data['sentiment'] = np.random.uniform(-1, 1, size=len(data))
        data.dropna(inplace=True)
        return data

    def train_initial_model(self):
        print("⚠️ Training AI (Scalping)...")
        X_mock = np.random.rand(1000, 5) 
        y_mock = np.random.randint(0, 2, 1000) 
        self.model = RandomForestClassifier(n_estimators=100)
        self.model.fit(X_mock, y_mock)
        os.makedirs(os.path.dirname(MODEL_FILE), exist_ok=True)
        joblib.dump(self.model, MODEL_FILE)

    def predict_probability(self, df):
        if self.model is None: return 0.5 
        processed = self.add_indicators(df)
        if processed.empty: return 0.5
        last = processed.iloc[-1]
        
        slope = last.get('slope', 0)
        feats = [[last.get('slope', 0), last.get('dist_vwap', 0), last.get('rsi', 50), last.get('adx', 20), last.get('sentiment', 0)]]
        try:
            prob = self.model.predict_proba(feats)[0][1]
            # Logic Scalping: Slope mạnh thì tăng xác suất
            if slope > 0.5: prob += 0.15
            if slope < -0.5: prob -= 0.15
            return max(0.0, min(1.0, prob))
        except: return 0.5