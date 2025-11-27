import os

# --- CẤU HÌNH SÀN (BINANCE TESTNET) ---
API_KEY = 'YutAah2NnmruBKivYShAwNpvw53oahi1xzB8YqGv18s7hS0cgrLM0OM5P5InPCKY'
SECRET_KEY = 'tYRUANWcNtb7gdvz9jmBF7zMmxyDYiOd5NXT4yqfyNS2ms9wmbesNhW0xjuDCYgY'

# --- DANH SÁCH COIN (MULTI-PAIR) ---
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']

# --- CẤU HÌNH SCALPING M5 ---
TIMEFRAME = '5m'         
LEVERAGE = 20            
LIMIT = 300              

# --- QUẢN LÝ VỐN ---
AI_CONFIDENCE_THRESHOLD = 0.60  
KELLY_MULTIPLIER = 0.8          # Tăng lên 0.8 để lệnh to hơn (Đủ min 100$)
MAX_CAPITAL_PER_TRADE = 40.0    # Cho phép dùng 40% vốn 1 lệnh để tránh lỗi vặt
STOP_LOSS_PCT = 0.006           # Cắt lỗ 0.6%
TAKE_PROFIT_PCT = 0.015         # Chốt lời 1.5%

# --- TRAILING STOP ---
TRAILING_ACTIVATION = 0.008     
TRAILING_CALLBACK = 0.003       

# --- SYSTEM ---
DB_FILE = os.path.join('data', 'crypto_bot.db')
MODEL_FILE = os.path.join('models', 'prediction_model.pkl')