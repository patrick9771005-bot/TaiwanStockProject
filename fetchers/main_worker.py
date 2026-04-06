import os
import sys
import pandas as pd
import yfinance as yf
import requests
import time
from datetime import datetime
from db.compat import get_connection

# 修正路徑以載入 models
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(base_dir)
from models.scoring_engine import calculate_score_a, calculate_score_b, calculate_score_c, generate_diagnosis

def get_db_connection():
    db_path = os.environ.get('STOCK_DB_PATH', os.path.join(base_dir, "data", "stock_system.db"))
    return get_connection(db_path)


def ensure_market_tables(conn):
    cursor = conn.cursor()
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
    conn.commit()

def main_job():
    print("🔍 啟動大盤時光機：往前抓取最近 5 個交易日資料...")
    
    # === 1. 取得最近 15 天的大盤與匯率資料 ===
    try:
        taiex_df = yf.download("^TWII", period="15d", progress=False)
        twd_df = yf.download("TWD=X", period="15d", progress=False)
        
        # 🛠️ 核心修復：處理 yfinance 新版雙層表頭 (MultiIndex)
        if isinstance(taiex_df.columns, pd.MultiIndex):
            taiex_series = taiex_df['Close'].iloc[:, 0]
        else:
            taiex_series = taiex_df['Close']

        if isinstance(twd_df.columns, pd.MultiIndex):
            twd_series = twd_df['Close'].iloc[:, 0]
        else:
            twd_series = twd_df['Close']
            
        # 🛠️ 核心修復：使用 pd.concat 更安全地合併，避免 Scalar 錯誤
        df_prices = pd.concat([taiex_series, twd_series], axis=1)
        df_prices.columns = ['TWII', 'TWD']
        df_prices = df_prices.dropna()

    except Exception as e:
        print(f"⚠️ yfinance 資料讀取失敗: {e}")
        return
        
    valid_dates = df_prices.index.tolist()
    if len(valid_dates) < 6:
        print("⚠️ 歷史交易日資料不足，無法計算漲跌幅。")
        return
        
    # 精準取最近的 5 個交易日
    target_dates = valid_dates[-5:]
    
    conn = get_db_connection()
    ensure_market_tables(conn)
    cursor = conn.cursor()
    
    for target_date in target_dates:
        date_dash = target_date.strftime("%Y-%m-%d")
        date_str = target_date.strftime("%Y%m%d") # 證交所 API 專用格式
        
        print(f"⏳ 正在處理交易日: {date_dash} ...")
        
        loc = df_prices.index.get_loc(target_date)
        
        def get_val(val):
            return float(val.iloc[0]) if hasattr(val, 'iloc') else float(val)

        taiex_price = get_val(df_prices['TWII'].iloc[loc])
        taiex_prev = get_val(df_prices['TWII'].iloc[loc-1])
        taiex_change = taiex_price - taiex_prev
        
        twd_fx = get_val(df_prices['TWD'].iloc[loc])
        twd_prev = get_val(df_prices['TWD'].iloc[loc-1])
        twd_change = twd_fx - twd_prev
        
        # === 2. 抓取三大法人現貨 (TWSE API) ===
        twse_url = f"https://www.twse.com.tw/fund/BFI82U?response=json&dayDate={date_str}&type=day"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        
        # 💡 加入 urllib3 警告消除，讓畫面乾淨一點
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        try:
            # 🛡️ 核心修復：加上 verify=False 跳過 SSL 憑證檢查
            response = requests.get(twse_url, headers=headers, timeout=15, verify=False)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"⚠️ {date_dash} 證交所 API 請求失敗 ({e})，跳過。")
            continue
            
        if data.get("stat") != "OK":
            print(f"⚠️ {date_dash} 證交所無法人資料 (可能休市或尚未公佈)，跳過。")
            continue
            
        rows = data['data']
        try:
            foreign_net = float(rows[3][3].replace(',', '')) + float(rows[4][3].replace(',', '')) # 外資
            sitc_net = float(rows[2][3].replace(',', '')) # 投信
            dealer_net = float(rows[0][3].replace(',', '')) + float(rows[1][3].replace(',', '')) # 自營商
        except IndexError:
            print(f"⚠️ {date_dash} 證交所資料格式解析失敗，跳過。")
            continue

        foreign_buy = foreign_net / 100000000
        sitc_buy = sitc_net / 100000000
        dealer_buy = dealer_net / 100000000

        # === 3. 模擬期指籌碼 ===
        mock_futures = { "tx": 1000, "mtx": 500, "elec": 100, "fin": -50, "net_oi": 1 }

        # === 4. 計算分數 ===
        score_a = calculate_score_a(foreign_buy, sitc_buy, dealer_buy)
        score_b = calculate_score_b(mock_futures["tx"], mock_futures["mtx"], mock_futures["elec"], mock_futures["fin"])
        score_c = calculate_score_c(foreign_buy, twd_change, taiex_change, mock_futures["net_oi"])
        diagnosis = generate_diagnosis(score_c)

        # === 5. 寫入資料庫 ===
        cursor.execute('''
            INSERT INTO market_raw (date, taiex_price, twd_fx, foreign_buy, sitc_buy, dealer_buy, is_ready)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(date)
            DO UPDATE SET
                taiex_price = excluded.taiex_price,
                twd_fx = excluded.twd_fx,
                foreign_buy = excluded.foreign_buy,
                sitc_buy = excluded.sitc_buy,
                dealer_buy = excluded.dealer_buy,
                is_ready = excluded.is_ready
        ''', (date_dash, taiex_price, twd_fx, foreign_buy, sitc_buy, dealer_buy))
        
        cursor.execute('''
            INSERT INTO market_scores (date, score_a, score_b_tx, score_b_mtx, score_b_elec, score_b_fin, score_c_total, diagnosis)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date)
            DO UPDATE SET
                score_a = excluded.score_a,
                score_b_tx = excluded.score_b_tx,
                score_b_mtx = excluded.score_b_mtx,
                score_b_elec = excluded.score_b_elec,
                score_b_fin = excluded.score_b_fin,
                score_c_total = excluded.score_c_total,
                diagnosis = excluded.diagnosis
        ''', (date_dash, int(score_a), int(score_b["TX"]), int(score_b["MTX"]), int(score_b["ELEC"]), int(score_b["FIN"]), int(score_c), diagnosis))
        
        conn.commit()
        print(f"✅ {date_dash} 數據與評分已成功寫入！")
        
        # 🛡️ 暫停 3 秒避免被證交所封鎖 IP
        time.sleep(3)

    conn.close()
    print("🎉 大盤時光機回補任務全部完成！")

if __name__ == "__main__":
    main_job()