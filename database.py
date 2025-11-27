import sqlite3
import os
from config import DB_FILE

def get_connection():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        symbol TEXT,
        type TEXT,          
        entry_price REAL,   
        amount REAL,        
        capital_snapshot REAL, 
        ai_confidence REAL, 
        sl_price REAL,      
        tp_price REAL,      
        status TEXT,        
        exit_price REAL,    
        exit_time TEXT,
        pnl_usdt REAL,      
        pnl_percent REAL    
    )
    ''')
    conn.commit()
    conn.close()
    print(f"✅ Database initialized at: {DB_FILE}")

if __name__ == "__main__":
    init_db()