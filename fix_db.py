import os
import sqlite3

# 自動定位你的資料庫路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'stock_system.db')

def create_watchlist_table():
    print(f"正在檢查並擴建資料庫: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 建立 watchlist 資料表 (如果已經存在就不會重複建立)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS watchlist (
            symbol TEXT PRIMARY KEY,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ 成功！watchlist 追蹤清單資料表已準備就緒！")

if __name__ == '__main__':
    create_watchlist_table()