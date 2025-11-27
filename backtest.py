import vectorbt as vbt
import pandas as pd
import ccxt
import datetime
import numpy as np
from ai_engine import AIEngine

def run_backtest(symbol='BTC/USDT', timeframe='5m', days=7):
    print(f"\n🔬 --- BACKTEST CHIẾN THUẬT MOMENTUM (ĐUA SÓNG) ---")
    print(f"🔥 Coin: {symbol} | Timeframe: {timeframe}")
    
    # 1. Tải dữ liệu
    try:
        exchange = ccxt.binance()
        since = exchange.parse8601((datetime.datetime.now() - datetime.timedelta(days=days+1)).isoformat())
        bars = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df = df.astype(float)
    except: return

    # 2. Tính toán
    ai = AIEngine()
    df = ai.add_indicators(df)
    
    # 3. LOGIC MOMENTUM (GIỐNG CON BOT ĐANG CHẠY)
    # Dựa trên thống kê thực tế: Slope biến động từ -400 đến +500
    # -> Ta chỉ vào lệnh khi Slope > 25 (Bắt đầu có lực đẩy mạnh)
    
    slope_trigger = 25.0  # Độ dốc đủ lớn để xác nhận trend
    adx_min = 20          # Trend phải rõ ràng (không sideway)
    
    print(f"⚙️ Config: Vào lệnh khi Slope > {slope_trigger} và ADX > {adx_min}")

    # LONG: Giá lao lên dốc đứng + Trend mạnh
    entries = (df['slope'] > slope_trigger) & (df['adx'] > adx_min)
    
    # SHORT: Giá cắm đầu xuống dốc đứng
    exits = (df['slope'] < -slope_trigger) & (df['adx'] > adx_min)
    
    print(f"   👉 Tìm thấy: {entries.sum()} điểm vào LONG.")
    print(f"   👉 Tìm thấy: {exits.sum()} điểm vào SHORT.")

    if entries.sum() == 0:
        print("❌ Chưa bắt được lệnh. Thử giảm Slope xuống 15 xem.")
        return

    # 4. Chạy Backtest
    try:
        # Init Cash 1000$, Phí 0.04%, Trượt giá 0.05%
        pf = vbt.Portfolio.from_signals(df['close'], entries, exits, init_cash=1000, fees=0.0004, slippage=0.0005)
        
        ret = pf.total_return() * 100
        print("\n" + "="*40)
        print(f"🏆 KẾT QUẢ: {'LÃI ✅' if ret > 0 else 'LỖ ❌'}")
        print("="*40)
        print(f"💰 Lợi nhuận tổng: {ret:.2f}%")
        print(f"💵 Lãi ròng:       {pf.total_profit():.2f} $")
        print(f"🎯 Win Rate:       {pf.trades.win_rate()*100:.2f}%")
        print(f"🔢 Số lệnh:        {pf.trades.count()}")
        print("="*40 + "\n")
        
    except Exception as e: print(f"Lỗi: {e}")

if __name__ == "__main__":
    # Test thử với ETH hoặc BNB (những con đang lãi thực tế) để thấy nó chuẩn hơn
    run_backtest('ETH/USDT')