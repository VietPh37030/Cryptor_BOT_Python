import time
import sys
import threading
from trading_logic import TradingBot
from config import SYMBOLS, LEVERAGE

def run_bot_for_symbol(symbol):
    print(f"🛠️ Start Worker: {symbol}...")
    try:
        bot = TradingBot(symbol)
        try: bot.send_signed_request('POST', '/fapi/v1/leverage', {'symbol': symbol.replace('/', ''), 'leverage': LEVERAGE})
        except: pass
        while True:
            try:
                bot.run_once()
                time.sleep(5)
            except Exception as e:
                print(f"❌ Error [{symbol}]: {e}")
                time.sleep(10)
    except Exception as e: print(f"❌ Init Error {symbol}: {e}")

def main():
    print(f"🤖 MULTI-PAIR BOT | x{LEVERAGE} | Pairs: {SYMBOLS}")
    threads = []
    for symbol in SYMBOLS:
        t = threading.Thread(target=run_bot_for_symbol, args=(symbol,))
        t.daemon = True
        threads.append(t)
        t.start()
        time.sleep(1)
    
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt: sys.exit()

if __name__ == "__main__":
    main()