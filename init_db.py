import sqlite3
import os

def init_db():
    # 取得目前這個腳本所在的絕對路徑 (專案根目錄)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 精準定位到專案底下的 data 資料夾
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    # 組合出完整的資料庫檔案路徑
    db_path = os.path.join(data_dir, "stock_system.db")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. 存放每日原始數據與三大法人整合後的資料 (保留你的原始設定)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_raw (
            date TEXT PRIMARY KEY,
            taiex_price REAL,
            twd_fx REAL,
            foreign_buy REAL,
            sitc_buy REAL,
            dealer_buy REAL,
            is_ready INTEGER DEFAULT 0
        )
    ''')

    # 2. 存放計算後的分數與診斷 (保留你的原始設定)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_scores (
            date TEXT PRIMARY KEY,
            score_a INTEGER,
            score_b_tx INTEGER,
            score_b_mtx INTEGER,
            score_b_elec INTEGER,
            score_b_fin INTEGER,
            score_c_total INTEGER,
            diagnosis TEXT,
            FOREIGN KEY(date) REFERENCES market_raw(date)
        )
    ''')

    # 3. 🌟 新增：存放個股六大指標與分數
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            symbol TEXT,
            timeframe TEXT DEFAULT 'daily',
            total_score INTEGER,
            macd_score INTEGER,
            ma_score INTEGER,
            kd_score INTEGER,
            rsi_score INTEGER,
            vol_score INTEGER,
            UNIQUE(date, symbol, timeframe)
        )
    ''')

    # 4. 🌟 新增：存放專屬追蹤清單 (側邊欄的命脈)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS watchlist (
            symbol TEXT PRIMARY KEY,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    
    # 印出最終的絕對路徑，讓你可以直接複製去檢查
    print(f"✅ 資料庫升級與初始化完成！所有資料表已確實建立於：\n{db_path}")

if __name__ == "__main__":
    init_db()