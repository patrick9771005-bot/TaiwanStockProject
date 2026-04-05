import sqlite3
import os

def update_db():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, "data", "stock_system.db")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. 存放個股原始 K 線資料 (OHLCV)
    # 增加 timeframe 欄位以區分日、週、月線
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_raw (
            date TEXT,
            symbol TEXT,
            timeframe TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            PRIMARY KEY (date, symbol, timeframe)
        )
    ''')

    # 2. 存放個股技術指標分數與糾結標籤
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_scores (
            date TEXT,
            symbol TEXT,
            timeframe TEXT,
            ma_score INTEGER,
            kd_score INTEGER,
            rsi_score INTEGER,
            macd_score INTEGER,
            vol_score INTEGER,
            total_score INTEGER,
            kd_entangled INTEGER,
            rsi_entangled INTEGER,
            macd_entangled INTEGER,
            PRIMARY KEY (date, symbol, timeframe),
            FOREIGN KEY(date, symbol, timeframe) REFERENCES stock_raw(date, symbol, timeframe)
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ 資料庫 A 階段擴充完成：stock_raw 與 stock_scores 表單已建立。")

if __name__ == "__main__":
    update_db()