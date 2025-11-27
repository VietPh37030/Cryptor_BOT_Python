import streamlit as st
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import numpy as np
from datetime import datetime
from config import *
from trading_logic import TradingBot
from database import get_connection
from ai_engine import AIEngine

# --- PAGE CONFIG ---
st.set_page_config(page_title="AI CRYPTO BOT", layout="wide", page_icon="⚡")

# --- CUSTOM CSS (Glassmorphism & Modern UI) ---
st.markdown("""
<style>
    /* Main Background */
    .stApp {
        background: radial-gradient(circle at 10% 20%, rgb(15, 23, 42) 0%, rgb(0, 0, 0) 90%);
        color: #e2e8f0;
        font-family: 'Inter', sans-serif;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: rgba(15, 23, 42, 0.8);
        backdrop-filter: blur(12px);
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    /* Metric Cards (Glassmorphism) */
    .glass-card {
        background: rgba(30, 41, 59, 0.4);
        border-radius: 16px;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(8.5px);
        -webkit-backdrop-filter: blur(8.5px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        padding: 20px;
        margin-bottom: 20px;
        transition: transform 0.2s;
    }
    .glass-card:hover {
        transform: translateY(-2px);
        border-color: rgba(255, 255, 255, 0.1);
    }
    
    /* Typography */
    .metric-label {
        color: #94a3b8;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 8px;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #f8fafc;
    }
    .metric-sub {
        font-size: 0.8rem;
        margin-top: 5px;
    }
    .text-green { color: #10b981; }
    .text-red { color: #ef4444; }
    .text-yellow { color: #f59e0b; }
    .text-blue { color: #3b82f6; }
    
    /* Tables */
    div[data-testid="stDataFrame"] {
        background: rgba(30, 41, 59, 0.2);
        border-radius: 10px;
        padding: 10px;
    }
    
    /* Custom Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: #0f172a; 
    }
    ::-webkit-scrollbar-thumb {
        background: #334155; 
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #475569; 
    }
</style>
""", unsafe_allow_html=True)

# --- INITIALIZATION ---
if 'bot' not in st.session_state:
    st.session_state.bot = TradingBot(SYMBOLS[0]) # Default init
if 'ai' not in st.session_state:
    st.session_state.ai = AIEngine()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("## ⚡ CONTROL PANEL")
    symbol_select = st.selectbox("Select Symbol", SYMBOLS, index=0)
    
    # Update bot instance if symbol changes
    if symbol_select != st.session_state.bot.symbol:
        st.session_state.bot = TradingBot(symbol_select)
    
    st.markdown("---")
    auto_refresh = st.checkbox("🔄 Auto-Refresh (5s)", value=True)
    show_trends = st.checkbox("📈 Show Trend Lines", value=True)
    
    st.markdown("---")
    st.markdown("### 🤖 AI Status")
    st.info("AI Engine Running\nModel: Random Forest\nInterval: " + TIMEFRAME)

# --- DATA FETCHING FUNCTIONS ---
@st.cache_data(ttl=5)
def get_market_data(sym):
    try:
        # Reuse bot's fetch method but we need to ensure it returns what we want
        df = st.session_state.bot.fetch_market_data(limit=300)
        return df
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame()

def get_trade_history():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM trades ORDER BY id DESC", conn)
    conn.close()
    return df

def get_open_orders(bot):
    try:
        sym = bot.symbol.replace('/', '')
        orders = bot.send_signed_request('GET', '/fapi/v1/openOrders', {'symbol': sym})
        return orders
    except:
        return []

# --- CALCULATIONS ---
def calculate_stats(hist_df):
    if hist_df.empty:
        return 0, 0, 0, 0
    
    closed_trades = hist_df[hist_df['status'] == 'CLOSED']
    total_trades = len(closed_trades)
    if total_trades == 0:
        return 0, 0, 0, 0
        
    wins = len(closed_trades[closed_trades['pnl_usdt'] > 0])
    win_rate = (wins / total_trades) * 100
    total_pnl = closed_trades['pnl_usdt'].sum()
    
    # Daily PnL
    today = datetime.now().strftime('%Y-%m-%d')
    daily_trades = closed_trades[closed_trades['exit_time'].str.startswith(today, na=False)]
    daily_pnl = daily_trades['pnl_usdt'].sum()
    
    return total_pnl, win_rate, total_trades, daily_pnl

def identify_trend_lines(df, pivot=10):
    # Simple pivot high/low logic
    df['pivot_high'] = df['high'].rolling(pivot*2+1, center=True).max()
    df['pivot_low'] = df['low'].rolling(pivot*2+1, center=True).min()
    
    highs = df[df['high'] == df['pivot_high']]
    lows = df[df['low'] == df['pivot_low']]
    
    return highs, lows

# --- MAIN LAYOUT ---
bot = st.session_state.bot
ai = st.session_state.ai

# 1. Fetch Data
df = get_market_data(symbol_select)
hist = get_trade_history()
open_orders = get_open_orders(bot)
bal = bot.get_balance_manual()
side, amt, entry = bot.get_position()
curr_price = df['close'].iloc[-1] if not df.empty else 0

# 2. Calculate Stats
total_pnl, win_rate, total_trades, daily_pnl = calculate_stats(hist)
pnl_color = "text-green" if total_pnl >= 0 else "text-red"
daily_color = "text-green" if daily_pnl >= 0 else "text-red"

# --- HEADER STATS ---
st.markdown(f"## 📊 Dashboard: {symbol_select}")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-label">💰 Wallet Balance</div>
        <div class="metric-value">{bal:,.2f} <span style="font-size:1rem">USDT</span></div>
        <div class="metric-sub text-blue">Available for trade</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-label">📈 Total PnL</div>
        <div class="metric-value {pnl_color}">{total_pnl:+.2f} <span style="font-size:1rem">USDT</span></div>
        <div class="metric-sub">All time performance</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-label">🎯 Win Rate</div>
        <div class="metric-value text-yellow">{win_rate:.1f}%</div>
        <div class="metric-sub">{total_trades} Total Trades</div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-label">📅 Daily PnL</div>
        <div class="metric-value {daily_color}">{daily_pnl:+.2f} <span style="font-size:1rem">USDT</span></div>
        <div class="metric-sub">Today's performance</div>
    </div>
    """, unsafe_allow_html=True)

# --- MAIN CONTENT ---
col_chart, col_side = st.columns([3, 1])

with col_chart:
    st.markdown("### 🕯️ Market Overview")
    if not df.empty:
        # Indicators
        df['ema_50'] = ta.ema(df['close'], length=50)
        df['ema_200'] = ta.ema(df['close'], length=200)
        
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
        
        # Candlestick
        fig.add_trace(go.Candlestick(
            x=df['timestamp'], open=df['open'], high=df['high'], low=df['low'], close=df['close'],
            name='Price',
            increasing_line_color='#10b981', decreasing_line_color='#ef4444'
        ), row=1, col=1)
        
        # EMAs
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ema_50'], line=dict(color='#3b82f6', width=1), name='EMA 50'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df['timestamp'], y=df['ema_200'], line=dict(color='#8b5cf6', width=1), name='EMA 200'), row=1, col=1)
        
        # Trend Lines
        if show_trends:
            highs, lows = identify_trend_lines(df)
            # Draw last 2 pivot highs connection if possible
            if len(highs) >= 2:
                fig.add_trace(go.Scatter(
                    x=highs['timestamp'][-2:], y=highs['high'][-2:], 
                    mode='lines', line=dict(color='rgba(255, 255, 255, 0.5)', width=1, dash='dot'), 
                    name='Resist Trend'
                ), row=1, col=1)
            if len(lows) >= 2:
                fig.add_trace(go.Scatter(
                    x=lows['timestamp'][-2:], y=lows['low'][-2:], 
                    mode='lines', line=dict(color='rgba(255, 255, 255, 0.5)', width=1, dash='dot'), 
                    name='Support Trend'
                ), row=1, col=1)

        # Volume
        colors = ['#10b981' if c >= o else '#ef4444' for c, o in zip(df['close'], df['open'])]
        fig.add_trace(go.Bar(x=df['timestamp'], y=df['v'], marker_color=colors, name='Volume'), row=2, col=1)
        
        # Layout Styling
        fig.update_layout(
            height=600,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#94a3b8'),
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, t=10, b=10),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        fig.update_xaxes(showgrid=False, zeroline=False)
        fig.update_yaxes(showgrid=True, gridcolor='rgba(255,255,255,0.05)', zeroline=False)
        
        st.plotly_chart(fig, use_container_width=True)

with col_side:
    # --- CURRENT POSITION ---
    st.markdown("### ⚡ Position")
    if side != 'NONE':
        pnl_val = (curr_price - entry) * amt if side == 'LONG' else (entry - curr_price) * amt
        pos_color = "#10b981" if pnl_val > 0 else "#ef4444"
        
        st.markdown(f"""
        <div class="glass-card" style="border-left: 4px solid {pos_color}">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <span style="font-weight:bold;font-size:1.2rem;color:{pos_color}">{side}</span>
                <span style="font-size:0.9rem;color:#94a3b8">x{LEVERAGE}</span>
            </div>
            <div style="margin-top:10px">
                <div style="display:flex;justify-content:space-between">
                    <span class="metric-label">Entry</span>
                    <span style="color:#f8fafc">{entry}</span>
                </div>
                <div style="display:flex;justify-content:space-between">
                    <span class="metric-label">Size</span>
                    <span style="color:#f8fafc">{amt}</span>
                </div>
                <div style="margin-top:10px;padding-top:10px;border-top:1px solid rgba(255,255,255,0.1);display:flex;justify-content:space-between;align-items:center">
                    <span class="metric-label">PnL</span>
                    <span style="font-weight:bold;font-size:1.1rem;color:{pos_color}">{pnl_val:+.2f} $</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("No active position")

    # --- PENDING ORDERS ---
    st.markdown("### ⏳ Pending Orders")
    if open_orders:
        for o in open_orders:
            o_type = o['type']
            o_side = o['side']
            o_price = float(o['stopPrice']) if float(o['stopPrice']) > 0 else float(o['price'])
            o_color = "#3b82f6" if o_side == 'BUY' else "#f59e0b"
            
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.03);padding:10px;border-radius:8px;margin-bottom:8px;border-left:3px solid {o_color}">
                <div style="display:flex;justify-content:space-between;font-size:0.9rem">
                    <span style="font-weight:bold;color:#e2e8f0">{o_type}</span>
                    <span style="color:{o_color}">{o_side}</span>
                </div>
                <div style="display:flex;justify-content:space-between;font-size:0.85rem;margin-top:4px;color:#94a3b8">
                    <span>Price: {o_price}</span>
                    <span>Qty: {o['origQty']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("<div style='color:#64748b;font-style:italic;text-align:center'>No pending orders</div>", unsafe_allow_html=True)

# --- RECENT HISTORY ---
st.markdown("### 📜 Recent Trades")
if not hist.empty:
    # Stylized Table
    hist_display = hist[['timestamp', 'symbol', 'type', 'entry_price', 'exit_price', 'pnl_usdt', 'status']].head(10).copy()
    hist_display['pnl_usdt'] = hist_display['pnl_usdt'].apply(lambda x: f"{x:+.2f} $" if pd.notnull(x) else "-")
    
    st.dataframe(
        hist_display, 
        use_container_width=True,
        hide_index=True,
        column_config={
            "timestamp": "Time",
            "symbol": "Pair",
            "type": "Side",
            "entry_price": "Entry",
            "exit_price": "Exit",
            "pnl_usdt": "PnL",
            "status": "Status"
        }
    )

if auto_refresh:
    time.sleep(5)
    st.rerun()

if __name__ == "__main__":
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if not get_script_run_ctx():
            print("\\n⚠️  CẢNH BÁO: Bạn đang chạy bằng lệnh 'python'. Vui lòng dùng lệnh:\\n    streamlit run dashboard.py\\n")
    except ImportError:
        pass
    except Exception:
        pass