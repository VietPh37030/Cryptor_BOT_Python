import os

# --- CẤU HÌNH SÀN (BINANCE TESTNET) ---
API_KEY = 'YutAah2NnmruBKivYShAwNpvw53oahi1xzB8YqGv18s7hS0cgrLM0OM5P5InPCKY'
SECRET_KEY = 'tYRUANWcNtb7gdvz9jmBF7zMmxyDYiOd5NXT4yqfyNS2ms9wmbesNhW0xjuDCYgY'

# --- DANH SÁCH COIN (MULTI-PAIR) ---
# Bạn đang chạy 4 con, nên chia vốn cẩn thận
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT']

# --- CẤU HÌNH SCALPING M5 ---
TIMEFRAME = '5m'         
LEVERAGE = 20            # Đòn bẩy 20x
LIMIT = 300              

# --- QUẢN LÝ VỐN (FIX LỖI Ở ĐÂY) ---
AI_CONFIDENCE_THRESHOLD = 0.60  
KELLY_MULTIPLIER = 0.8          

# QUAN TRỌNG: Giảm từ 40% xuống 20%. 
# Vì 4 con x 20% = 80% tổng tài khoản (Vẫn còn dư 20% để gồng lỗ hoặc phí).
MAX_CAPITAL_PER_TRADE = 20.0    

# --- CHIẾN THUẬT SCALPING (Ăn ngắn - Rút nhanh) ---
# Với M5 + x20, đừng tham ăn 1.5%. Hãy ăn mỏng thôi.
STOP_LOSS_PCT = 0.004           # Cắt lỗ 0.4% giá (Thực tế mất 8% lệnh)
TAKE_PROFIT_PCT = 0.008         # Chốt lời 0.8% giá (Thực tế lãi 16% lệnh)

# --- TRAILING STOP (GỒNG LÃI SỚM) ---
TRAILING_ACTIVATION = 0.005     # Lãi 0.5% là bắt đầu dời SL rồi
TRAILING_CALLBACK = 0.002       # Dời sát 0.2%
# --- QUẢN LÝ VỐN ---
AI_CONFIDENCE_THRESHOLD = 0.60  
KELLY_MULTIPLIER = 0.8          

# GIẢM XUỐNG 12-15% THÔI
# 12% x 4 coin = 48% tổng tài khoản (Còn dư 52% để gồng lỗ -> Rất an toàn)
MAX_CAPITAL_PER_TRADE = 12.0
# --- SYSTEM ---
DB_FILE = os.path.join('data', 'crypto_bot.db')
MODEL_FILE = os.path.join('models', 'prediction_model.pkl')