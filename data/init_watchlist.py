import sqlite3

def init_watchlist_table():
    # 連線到你的資料庫 (請確保檔名與你的實際資料庫檔名一致)
    conn = sqlite3.connect('stock_system.db')
    cursor = conn.cursor()
    
    # 建立自選名單表 (如果已經存在則不會重複建立)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_watchlist (
            symbol TEXT PRIMARY KEY,
            added_date TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ 動作 A 完成：user_watchlist 表格已成功建立！")

if __name__ == "__main__":
    init_watchlist_table()