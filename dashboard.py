import streamlit as st
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import time
from config import *
from trading_logic import TradingBot
from database import get_connection
from ai_engine import AIEngine

st.set_page_config(page_title="AI PRO", layout="wide", page_icon="⚡")
st.markdown("""<style>.stApp {background:#0b0e11;} .metric-box {background:#1e2329;border:1px solid #2b3139;padding:15px;border-radius:4px;text-align:center;} .metric-val {font-size:22px;font-weight:bold;color:#eaecef;} .lbl {color:#848e9c;font-size:12px;}</style>""", unsafe_allow_html=True)

st.sidebar.title("⚙️ CONFIG")
auto_refresh = st.sidebar.checkbox("Auto-Refresh (3s)", value=True)
symbol_select = st.sidebar.selectbox("Symbol", SYMBOLS)
if auto_refresh: time.sleep(3); st.rerun()

@st.cache_data(ttl=5)
def get_data(sym):
    try:
        res = requests.get("https://testnet.binancefuture.com/fapi/v1/klines", params={'symbol':sym.replace('/',''),'interval':TIMEFRAME,'limit':200}).json()
        df = pd.DataFrame(res, columns=['timestamp','open','high','low','close','v','x','x','x','x','x','x'])
        df = df[['timestamp','open','high','low','close','v']].astype(float)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except: return pd.DataFrame()

def get_history():
    conn = get_connection(); df = pd.read_sql_query("SELECT * FROM trades ORDER BY id DESC", conn); conn.close(); return df

bot = TradingBot(symbol_select)
ai = AIEngine()
df = get_data(symbol_select)
hist = get_history()
bal = bot.get_balance_manual()
side, amt, entry = bot.get_position()
curr = df['close'].iloc[-1] if not df.empty else 0

pnl_val = 0; color = "#848e9c"
if side != 'NONE':
    pnl_val = (curr-entry)*amt if side=='LONG' else (entry-curr)*amt
    color = "#0ecb81" if pnl_val > 0 else "#f6465d"

st.markdown(f"## ⚡ {symbol_select}")
c1,c2,c3,c4 = st.columns(4)
with c1: st.markdown(f'<div class="metric-box"><div class="lbl">WALLET</div><div class="metric-val">{bal:,.2f} $</div></div>', unsafe_allow_html=True)
with c2: st.markdown(f'<div class="metric-box"><div class="lbl">PRICE</div><div class="metric-val" style="color:#f0b90b">{curr}</div></div>', unsafe_allow_html=True)
with c3: st.markdown(f'<div class="metric-box" style="border-color:{color}"><div class="lbl">POSITION</div><div class="metric-val" style="color:{color}">{side} {pnl_val:+.2f}$</div></div>', unsafe_allow_html=True)

slope = 0
if not df.empty:
    df['slope'] = ai.calculate_slope(df['close'], 7)
    slope = df['slope'].iloc[-1]
with c4: st.markdown(f'<div class="metric-box"><div class="lbl">SLOPE</div><div class="metric-val">{slope:.2f}</div></div>', unsafe_allow_html=True)

st.write("---")
c_chart, c_log = st.columns([3,1])
with c_chart:
    if not df.empty:
        df['vwap'] = ta.vwap(df['high'], df['low'], df['close'], df['v'])
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7,0.3])
        fig.add_trace(go.Candlestick(x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Price'), row=1, col=1)
        if 'vwap' in df.columns: fig.add_trace(go.Scatter(x=df['timestamp'], y=df['vwap'], line=dict(color='orange'), name='VWAP'), row=1, col=1)
        fig.add_trace(go.Bar(x=df['timestamp'], y=df['v'], marker_color='teal', name='Vol'), row=2, col=1)
        fig.update_layout(height=500, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)

with c_log:
    st.subheader("📜 History")
    if not hist.empty:
        def calc_pnl(row):
            if row['status']=='CLOSED':
                xp = row['exit_price'] if row['exit_price']>0 else curr
                return (xp-row['entry_price'])*row['amount'] if row['type']=='LONG' else (row['entry_price']-xp)*row['amount']
            return row['pnl_usdt']
        hist['real_pnl'] = hist.apply(calc_pnl, axis=1)
        
        html = '<table style="width:100%;font-size:13px;border-collapse:collapse;">'
        for _,r in hist.head(10).iterrows():
            c = "#0ecb81" if r['real_pnl']>0 else ("#f6465d" if r['real_pnl']<0 else "#eaecef")
            html += f'<tr style="border-bottom:1px solid #333;"><td style="padding:5px">{r["symbol"]}</td><td style="color:{c};font-weight:bold;text-align:right">{r["real_pnl"]:+.2f}$</td></tr>'
        html += '</table>'
        st.markdown(html, unsafe_allow_html=True)