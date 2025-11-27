import ccxt
import pandas as pd
import time
import requests
import hmac
import hashlib
import math 
import threading 
from urllib.parse import urlencode
from datetime import datetime
from config import *
from ai_engine import AIEngine
from database import get_connection

# KHÓA AN TOÀN (Để các bot không tranh nhau đặt lệnh cùng lúc)
order_lock = threading.Lock()

class TradingBot:
    def __init__(self, symbol):
        self.symbol = symbol 
        print(f"🚀 Worker: {self.symbol} | Init...")
        self.ai = AIEngine()
        self.base_url = "https://testnet.binancefuture.com"
        
        # Kết nối CCXT (Chỉ để check vị thế nhanh)
        self.exchange = ccxt.binance({
            'apiKey': API_KEY, 'secret': SECRET_KEY, 
            'enableRateLimit': True, 'options': {'defaultType': 'future'}
        })
        
        # Hack URL để tránh lỗi thư viện
        self.exchange.urls['api'] = {
            'fapiPublic': self.base_url + '/fapi/v1', 'fapiPrivate': self.base_url + '/fapi/v1',
            'fapiPrivateV2': self.base_url + '/fapi/v2', 'public': self.base_url + '/fapi/v1',
            'private': self.base_url + '/fapi/v1', 'sapi': self.base_url + '/fapi/v1', 'spot': self.base_url + '/api/v3',
        }
        
        # Tự động lấy thông tin làm tròn số (Precision)
        self.qty_precision = 0
        self.price_precision = 2
        self.get_symbol_precision()

    # --- GIAO TIẾP API (DIRECT REQUESTS) ---
    def send_signed_request(self, method, endpoint, params=None):
        if params is None: params = {}
        params['timestamp'] = int(time.time() * 1000)
        params['recvWindow'] = 10000 
        query_string = urlencode(params)
        signature = hmac.new(SECRET_KEY.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        headers = {'X-MBX-APIKEY': API_KEY}
        try:
            url = f"{self.base_url}{endpoint}?{query_string}&signature={signature}"
            if method == 'GET': return requests.get(url, headers=headers).json()
            else: return requests.post(url, headers=headers).json()
        except: return {}

    def get_symbol_precision(self):
        try:
            res = requests.get(f"{self.base_url}/fapi/v1/exchangeInfo").json()
            target = self.symbol.replace('/', '')
            for s in res['symbols']:
                if s['symbol'] == target:
                    self.qty_precision = int(s['quantityPrecision'])
                    self.price_precision = int(s['pricePrecision'])
                    break
        except: self.qty_precision = 3

    def fetch_market_data(self, tf=TIMEFRAME, limit=LIMIT):
        try:
            res = requests.get(f"{self.base_url}/fapi/v1/klines", params={'symbol': self.symbol.replace('/', ''), 'interval': tf, 'limit': limit}).json()
            if isinstance(res, dict): return pd.DataFrame()
            df = pd.DataFrame(res, columns=['timestamp','open','high','low','close','v','x','x','x','x','x','x'])
            df = df[['timestamp','open','high','low','close','v']].astype(float)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except: return pd.DataFrame()

    def get_balance_manual(self):
        """Lấy số dư KHẢ DỤNG (Available Balance)"""
        try:
            data = self.send_signed_request('GET', '/fapi/v2/balance')
            if isinstance(data, list):
                for item in data:
                    if item['asset'] == 'USDT': return float(item['availableBalance'])
            return 0.0
        except: return 0.0

    def get_position(self):
        try:
            positions = self.exchange.fetch_positions([self.symbol])
            for pos in positions:
                amt = float(pos['contracts'])
                if amt != 0:
                    side = 'LONG' if amt > 0 else 'SHORT'
                    return side, abs(amt), float(pos['entryPrice'])
            return 'NONE', 0, 0
        except: return 'NONE', 0, 0

    # --- TÍNH TOÁN VỐN & AN TOÀN ---
    def calculate_position_size(self, win_prob, current_balance, price):
        b = 2.0; p = win_prob; q = 1 - p
        kelly = (b * p - q) / b
        final_fraction = min(kelly * KELLY_MULTIPLIER, MAX_CAPITAL_PER_TRADE / 100.0)
        
        if final_fraction <= 0: return 0
        
        usdt_amount = current_balance * final_fraction
        
        # Ép Min Order 110$ để tránh lỗi sàn
        if usdt_amount < 110:
            if current_balance > 110: usdt_amount = 110
            else: return 0 

        # Check tiền cọc (Margin)
        required_margin = usdt_amount / LEVERAGE
        if current_balance < required_margin:
            print(f"⚠️ [{self.symbol}] Thiếu tiền cọc (Cần {required_margin:.1f}$)")
            return 0

        raw_qty = usdt_amount / price
        factor = 10 ** self.qty_precision
        # Làm tròn LÊN (Ceil) để đảm bảo đủ giá trị lệnh
        qty = math.ceil(raw_qty * factor) / factor
        
        return int(qty) if self.qty_precision == 0 else qty

    # --- QUẢN LÝ LỆNH (CHỐNG SPAM) ---
    def ensure_sl_tp_integrity(self, side, entry_price):
        """Chỉ giữ đúng 1 SL và 1 TP. Nếu sai -> Reset."""
        try:
            sym = self.symbol.replace('/', '')
            orders = self.send_signed_request('GET', '/fapi/v1/openOrders', {'symbol': sym})
            
            sl_count = len([o for o in orders if o['type'] == 'STOP_MARKET'])
            tp_count = len([o for o in orders if o['type'] == 'TAKE_PROFIT_MARKET'])
            
            # Nếu lệnh rác -> Xóa hết
            if sl_count > 1 or tp_count > 1 or (sl_count + tp_count > 2):
                print(f"🧹 [{self.symbol}] Dọn rác (SL:{sl_count}|TP:{tp_count}) -> RESET.")
                self.send_signed_request('DELETE', '/fapi/v1/allOpenOrders', {'symbol': sym})
                time.sleep(2) 
                sl_count = 0; tp_count = 0

            sl_price = round(entry_price * (1 - STOP_LOSS_PCT) if side == 'LONG' else entry_price * (1 + STOP_LOSS_PCT), self.price_precision)
            tp_price = round(entry_price * (1 + TAKE_PROFIT_PCT) if side == 'LONG' else entry_price * (1 - TAKE_PROFIT_PCT), self.price_precision)
            c_side = 'SELL' if side == 'LONG' else 'BUY'

            if sl_count == 0:
                self.send_signed_request('POST', '/fapi/v1/order', {'symbol': sym, 'side': c_side, 'type': 'STOP_MARKET', 'stopPrice': sl_price, 'closePosition': 'true'})
                time.sleep(0.3)
            if tp_count == 0:
                self.send_signed_request('POST', '/fapi/v1/order', {'symbol': sym, 'side': c_side, 'type': 'TAKE_PROFIT_MARKET', 'stopPrice': tp_price, 'closePosition': 'true'})
        except: pass

    def manage_trailing_stop(self, current_price, pos_side, pos_amt, entry_price):
        try:
            sym = self.symbol.replace('/', '')
            pnl_pct = (current_price - entry_price)/entry_price if pos_side == 'LONG' else (entry_price - current_price)/entry_price
            
            if pnl_pct > TRAILING_ACTIVATION:
                new_sl = current_price * (1 - TRAILING_CALLBACK) if pos_side == 'LONG' else current_price * (1 + TRAILING_CALLBACK)
                new_sl = round(new_sl, self.price_precision)
                
                orders = self.send_signed_request('GET', '/fapi/v1/openOrders', {'symbol': sym})
                curr_sl_order = next((o for o in orders if o['type'] == 'STOP_MARKET'), None)
                
                update = False
                if curr_sl_order:
                    old_sl = float(curr_sl_order['stopPrice'])
                    # Chỉ dời nếu giá thay đổi > 0.2%
                    if abs(new_sl - old_sl)/old_sl > 0.002: 
                        if (pos_side == 'LONG' and new_sl > old_sl) or (pos_side == 'SHORT' and new_sl < old_sl): update = True
                else: update = True

                if update:
                    print(f"⚡ [{self.symbol}] Trailing SL -> {new_sl}")
                    self.send_signed_request('DELETE', '/fapi/v1/allOpenOrders', {'symbol': sym})
                    c_side = 'SELL' if pos_side == 'LONG' else 'BUY'
                    self.send_signed_request('POST', '/fapi/v1/order', {'symbol': sym, 'side': c_side, 'type': 'STOP_MARKET', 'stopPrice': new_sl, 'closePosition': 'true'})
        except: pass

    # --- THỰC THI LỆNH ---
    def execute_trade(self, side, quantity, price, sl, tp, conf, bal):
        # Dùng khóa Lock để tránh tranh tiền
        with order_lock:
            real_bal = self.get_balance_manual()
            if real_bal < (quantity * price / LEVERAGE):
                print(f"⚠️ [{self.symbol}] Hủy lệnh: Tiền đã bị bot khác dùng.")
                return

            sym = self.symbol.replace('/', ''); s_side = side.upper()
            print(f"⚡ [{self.symbol}] Executing {s_side} {quantity}...")
            
            res = self.send_signed_request('POST', '/fapi/v1/order', {'symbol': sym, 'side': s_side, 'type': 'MARKET', 'quantity': quantity})
            
            if 'orderId' in res:
                print(f"✅ [{self.symbol}] FILLED!")
                try:
                    conn = get_connection(); cur = conn.cursor()
                    cur.execute("INSERT INTO trades (timestamp, symbol, type, entry_price, amount, capital_snapshot, ai_confidence, sl_price, tp_price, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                                (datetime.now(), self.symbol, s_side, price, quantity, bal, conf, sl, tp, 'OPEN'))
                    conn.commit(); conn.close()
                except: pass
                time.sleep(1)
                self.ensure_sl_tp_integrity(side, price)
            else: print(f"❌ Error: {res}")

    def sync_pnl(self):
        try:
            conn = get_connection(); cur = conn.cursor()
            cur.execute("SELECT id, amount FROM trades WHERE status='OPEN' AND symbol=? LIMIT 1", (self.symbol,))
            row = cur.fetchone()
            if row:
                tid, _ = row
                _, pos_amt, _ = self.get_position()
                if pos_amt == 0:
                    trades = self.send_signed_request('GET', '/fapi/v1/userTrades', {'symbol': self.symbol.replace('/',''), 'limit': 5})
                    pnl = 0
                    if isinstance(trades, list):
                        for t in trades: pnl += float(t.get('realizedPnl', 0))
                    cur.execute("UPDATE trades SET status='CLOSED', exit_time=?, pnl_usdt=? WHERE id=?", (datetime.now(), pnl, tid))
                    conn.commit()
                    print(f"💰 [{self.symbol}] Closed PnL: {pnl}$")
                    # Dọn dẹp ngay sau khi đóng
                    self.send_signed_request('DELETE', '/fapi/v1/allOpenOrders', {'symbol': self.symbol.replace('/','')})
            conn.close()
        except: pass

    # --- MAIN LOOP ---
    def run_once(self):
        self.sync_pnl()
        df = self.fetch_market_data()
        if df.empty: return
        price = df['close'].iloc[-1]
        
        try: prob = self.ai.predict_probability(df)
        except: prob = 0.5
        
        # In heartbeat
        # print(f"👀 [{self.symbol}] Price: {price} | AI: {prob*100:.1f}%")

        side, amt, entry = self.get_position()
        
        # --- 1. LOGIC ĐẢO CHIỀU (STOP & REVERSE) ---
        if side != 'NONE':
            should_reverse = False
            if side == 'LONG' and prob < (1 - AI_CONFIDENCE_THRESHOLD): # Đang Long mà AI báo Sập mạnh
                print(f"🚨 [{self.symbol}] Cảnh báo ĐẢO CHIỀU (AI Short {100-prob*100:.1f}%) -> CẮT LONG!")
                should_reverse = True
            elif side == 'SHORT' and prob > AI_CONFIDENCE_THRESHOLD: # Đang Short mà AI báo Bay mạnh
                print(f"🚨 [{self.symbol}] Cảnh báo ĐẢO CHIỀU (AI Long {prob*100:.1f}%) -> CẮT SHORT!")
                should_reverse = True
            
            if should_reverse:
                # Hủy hết lệnh chờ
                self.send_signed_request('DELETE', '/fapi/v1/allOpenOrders', {'symbol': self.symbol.replace('/','')})
                # Đóng vị thế Market
                c_side = 'SELL' if side == 'LONG' else 'BUY'
                self.send_signed_request('POST', '/fapi/v1/order', {'symbol': self.symbol.replace('/',''), 'side': c_side, 'type': 'MARKET', 'quantity': amt, 'reduceOnly': 'true'})
                return # Thoát vòng lặp để cập nhật số dư

        # --- 2. QUẢN LÝ VỊ THẾ ---
        if side != 'NONE':
            self.ensure_sl_tp_integrity(side, entry) 
            self.manage_trailing_stop(price, side, amt, entry)
            return

        # --- 3. DỌN DẸP NẾU KHÔNG CÓ LỆNH ---
        try:
            orders = self.send_signed_request('GET', '/fapi/v1/openOrders', {'symbol': self.symbol.replace('/','')})
            if len(orders) > 0: self.send_signed_request('DELETE', '/fapi/v1/allOpenOrders', {'symbol': self.symbol.replace('/','')})
        except: pass

        # --- 4. VÀO LỆNH MỚI ---
        bal = self.get_balance_manual()
        sl_l = price*(1-STOP_LOSS_PCT); tp_l = price*(1+TAKE_PROFIT_PCT)
        sl_s = price*(1+STOP_LOSS_PCT); tp_s = price*(1-TAKE_PROFIT_PCT)
        qty = self.calculate_position_size(prob, bal, price)

        if qty > 0:
            if prob > AI_CONFIDENCE_THRESHOLD:
                print(f"🚀 [{self.symbol}] LONG SIGNAL ({prob*100:.1f}%)")
                self.execute_trade('BUY', qty, price, sl_l, tp_l, prob, bal)
            elif prob < (1-AI_CONFIDENCE_THRESHOLD):
                print(f"🚀 [{self.symbol}] SHORT SIGNAL ({(1-prob)*100:.1f}%)")
                self.execute_trade('SELL', qty, price, sl_s, tp_s, prob, bal)
            else:
                # print(f"zzz [{self.symbol}] Sideway")
                pass