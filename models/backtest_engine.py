import yfinance as yf
import pandas as pd
import os
import sys
from datetime import datetime, timedelta

# 確保能讀取到同資料夾的技術引擎
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from technical_engine import calculate_technical_scores


def _normalize_timeframe(timeframe):
    """將前端時間級別正規化為系統可用值。"""
    tf = str(timeframe or '1d').strip().lower()

    alias_map = {
        '5': '5m',
        '15': '15m',
        '60': '1h',
        '10': '15m',
        '10m': '15m',  # yfinance 不支援 10m
        'd': '1d',
        'day': '1d',
        'daily': '1d',
        'w': '1wk',
        '1w': '1wk',
        'week': '1wk',
        'weekly': '1wk',
        'm': '1mo',
        'month': '1mo',
        'monthly': '1mo',
        'mth': '1mo',
        '60m': '1h'
    }
    if tf in alias_map:
        return alias_map[tf]
    return tf


def _tf_config(timeframe):
    """回傳 (yfinance interval, period, technical timeframe)。"""
    tf = _normalize_timeframe(timeframe)
    config = {
        '5m': ('5m', '60d', 'daily'),
        '15m': ('15m', '60d', 'daily'),
        '1h': ('60m', '730d', 'daily'),
        '1d': ('1d', '6mo', 'daily'),
        '1wk': ('1wk', '5y', 'weekly'),
        '1mo': ('1mo', '10y', 'monthly')
    }
    return config.get(tf, ('1d', '6mo', 'daily'))


def compute_recent_scores(symbol, timeframe='1d', days=15, macd_options=None, kd_options=None):
    """回抓並計算最近 N 個交易日（或該級別K棒）的技術分數。"""
    try:
        macd_options = macd_options or {}
        kd_options = kd_options or {}
        yf_interval, yf_period, tech_timeframe = _tf_config(timeframe)

        df = yf.download(f"{symbol}.TW", period=yf_period, interval=yf_interval, progress=False)
        if df is None or df.empty:
            return []

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 確保有足夠資料計算指標（長均線 + 緩衝）
        min_need = 35
        if len(df) < min_need:
            return []

        start_idx = max(min_need - 1, len(df) - int(days))
        results = []

        for i in range(start_idx, len(df)):
            sub_df = df.iloc[:i + 1]
            analysis = calculate_technical_scores(
                sub_df,
                timeframe=tech_timeframe,
                macd_mode=macd_options.get('mode', 'precise'),
                macd_zero_if_small=bool(macd_options.get('zero_if_small', False)),
                macd_zero_threshold_pct=float(macd_options.get('threshold_pct', 0.0) or 0.0),
                kd_mode=kd_options.get('mode', 'precise'),
                kd_zero_if_small=bool(kd_options.get('zero_if_small', False)),
                kd_zero_threshold_pct=float(kd_options.get('threshold_pct', 0.0) or 0.0)
            )
            scores = analysis.get('scores', {})
            metrics = analysis.get('metrics', {})
            indicators = analysis.get('indicators', {})
            dt = sub_df.index[-1]

            if yf_interval in ('5m', '15m', '60m'):
                trade_date = dt.strftime('%Y-%m-%d %H:%M')
            else:
                trade_date = dt.strftime('%Y-%m-%d')

            close_val = sub_df['Close'].iloc[-1]
            open_val = sub_df['Open'].iloc[-1]
            high_val = sub_df['High'].iloc[-1]
            low_val = sub_df['Low'].iloc[-1]
            vol_val = sub_df['Volume'].iloc[-1]
            close_price = round(float(close_val), 2)

            results.append({
                'date': trade_date,
                'score': int(scores.get('Total', 0)),
                'scores': {
                    'MA': int(scores.get('MA', 0)),
                    'KD': int(scores.get('KD', 0)),
                    'RSI': int(scores.get('RSI', 0)),
                    'MACD': int(scores.get('MACD', 0)),
                    'Volume': int(scores.get('Volume', 0)),
                    'Total': int(scores.get('Total', 0))
                },
                'metrics': {
                    'bias_pct': metrics.get('bias_pct'),
                    'kd_change_pct': metrics.get('kd_change_pct'),
                    'macd_change_pct': metrics.get('macd_change_pct')
                },
                'indicators': indicators,
                'close_price': close_price,
                'open_price': round(float(open_val), 2),
                'high_price': round(float(high_val), 2),
                'low_price': round(float(low_val), 2),
                'volume': int(float(vol_val))
            })

        return results[-int(days):]
    except Exception as e:
        print(f"歷史分數計算失敗 ({symbol}, tf={timeframe}): {e}")
        return []

def get_instant_analysis(symbol, timeframe='1d', macd_options=None, kd_options=None):
    """一鍵算分：獲取個股當前的即時分數與決策（僅使用最近40支K棒）"""
    try:
        macd_options = macd_options or {}
        kd_options = kd_options or {}
        # 根據時間週期設定 yfinance 參數
        yf_interval, yf_period, tech_timeframe = _tf_config(timeframe)
        
        df = yf.download(f"{symbol}.TW", period=yf_period, interval=yf_interval, progress=False)
        if df.empty: return None

        # yfinance 可能回傳 MultiIndex 欄位，先扁平化避免後續取值異常
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # 只取最近 40 支 K 棒以加快響應速度
        df = df.tail(40)
        
        # 🔍 調試：印出最後 3 筆行情資料以驗證數據正確性
        print(f"\n[{symbol}] {timeframe} 最後 3 根 K 棒:")
        print(df[['Open', 'High', 'Low', 'Close', 'Volume']].tail(3).to_string())
        
        # 使用我們原本的技術大腦算分
        analysis = calculate_technical_scores(
            df,
            timeframe=tech_timeframe,
            macd_mode=macd_options.get('mode', 'precise'),
            macd_zero_if_small=bool(macd_options.get('zero_if_small', False)),
            macd_zero_threshold_pct=float(macd_options.get('threshold_pct', 0.0) or 0.0),
            kd_mode=kd_options.get('mode', 'precise'),
            kd_zero_if_small=bool(kd_options.get('zero_if_small', False)),
            kd_zero_threshold_pct=float(kd_options.get('threshold_pct', 0.0) or 0.0)
        )
        
        # 🔍 印出計算的分數
        print(f"[{symbol}] 技術分數各項: MA={analysis['scores']['MA']}, KD={analysis['scores']['KD']}, RSI={analysis['scores']['RSI']}, MACD={analysis['scores']['MACD']}, Vol={analysis['scores']['Volume']}, Total={analysis['scores']['Total']}")
        print(f"{'='*60}")
        
        # 加上當前價格資訊
        latest_price = df['Close'].iloc[-1]
        analysis['current_price'] = round(float(latest_price), 2)
        analysis['symbol'] = symbol
        analysis['timeframe'] = timeframe  # 記錄使用的時間週期
        return analysis
    except Exception as e:
        print(f"算分出錯 (tf={timeframe}): {e}")
        return None

def run_perfect_backtest(symbol, hold_days=[5, 10, 20]):
    """一鍵回測：尋找歷史中所有「完美轉折」點並計算勝率"""
    try:
        # 抓取較長歷史資料進行回測
        df = yf.download(f"{symbol}.TW", period="2y", interval="1d", progress=False)
        if len(df) < 60: return None

        results = []
        # 逐日掃描歷史 (從第 30 天開始，確保有足夠均線資料)
        for i in range(30, len(df) - max(hold_days)):
            sub_df = df.iloc[:i+1]
            analysis = calculate_technical_scores(sub_df)
            
            s = analysis['scores']
            # 觸發你的「完美轉折」條件：總分 -1 且 MACD +1
            if s['Total'] == -1 and s['MACD'] == 1:
                buy_price = df['Close'].iloc[i]
                buy_date = df.index[i].strftime('%Y-%m-%d')
                
                perf = {"date": buy_date, "buy_price": round(float(buy_price), 2)}
                
                # 計算後續持有收益
                for d in hold_days:
                    sell_price = df['Close'].iloc[i + d]
                    return_pct = (sell_price - buy_price) / buy_price * 100
                    perf[f'day_{d}_ret'] = round(float(return_pct), 2)
                
                results.append(perf)
        
        return results
    except Exception as e:
        print(f"回測出錯: {e}")
        return None

# =====================================================================
# 🚀 全新加入：矩陣式歷史回測引擎 (對接前端指揮中心)
# =====================================================================
def run_matrix_backtest(symbol, start_time, end_time, level, capital, unit, fee_rate, tax_rate, buy_scores, sell_scores):
    """
    多維度矩陣回測：支援自訂資金、摩擦成本、多個買入與賣出分數同時驗證
    """
    try:
        # 1. 處理前端傳來的萬年曆時間格式 (例如 "2023-01-01T09:00")
        try:
            start_dt = datetime.strptime(start_time, '%Y-%m-%dT%H:%M')
            end_dt = datetime.strptime(end_time, '%Y-%m-%dT%H:%M')
        except ValueError:
            # 相容只有日期的格式
            start_dt = datetime.strptime(start_time, '%Y-%m-%d')
            end_dt = datetime.strptime(end_time, '%Y-%m-%d')

        # 2. 設定 yfinance 級別與技術分析級別
        # 注意：yfinance 小時級別使用 60m，而非 1h
        bt_map = {
            '5m': ('5m', 'daily'),
            '15m': ('15m', 'daily'),
            '1h': ('60m', 'daily'),
            '1d': ('1d', 'daily'),
            '1wk': ('1wk', 'weekly'),
            '1mo': ('1mo', 'monthly')
        }
        yf_interval, tech_timeframe = bt_map.get(level, ('1d', 'daily'))

        print(f"[{symbol}] 下載資料區間: {start_dt} 到 {end_dt}, 級別: {yf_interval}")
        fallback_period_map = {
            '5m': '60d',
            '15m': '60d',
            '60m': '730d',
            '1d': '5y',
            '1wk': '10y',
            '1mo': '20y'
        }

        if yf_interval in ('5m', '15m', '60m'):
            # 小時/分鐘級別直接用 period，避免 start/end 超出 Yahoo 可用範圍造成長時間失敗
            fallback_period = fallback_period_map[yf_interval]
            df = yf.download(f"{symbol}.TW", period=fallback_period, interval=yf_interval, progress=False)
        else:
            df = yf.download(f"{symbol}.TW", start=start_dt, end=end_dt, interval=yf_interval, progress=False)
            if df.empty:
                # 日K以上仍可保留 fallback 行為
                fallback_period = fallback_period_map.get(yf_interval, '2y')
                print(f"[{symbol}] 指定區間無資料，改用 fallback: period={fallback_period}, interval={yf_interval}")
                df = yf.download(f"{symbol}.TW", period=fallback_period, interval=yf_interval, progress=False)

        if df.empty:
            print(f"[{symbol}] 仍無資料 (interval={yf_interval})")
            return None

        # yfinance 可能回傳 MultiIndex 欄位，先扁平化避免每根K棒取值告警與錯誤
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 非日K資料量過大時會嚴重拖慢回測（本引擎為逐步重算，近似 O(n^2)）
        # 因此限制樣本數，確保前端能在可接受時間內回應
        intraday_limit_map = {
            '5m': 400,
            '15m': 500,
            '60m': 700
        }
        if yf_interval in intraday_limit_map:
            df = df.tail(intraday_limit_map[yf_interval])

        # 3. 初始化「矩陣策略狀態」
        # 我們為每一個前端傳來的 buy_score (例如 -1, 1) 建立獨立的帳戶狀態
        strategies = {}
        for bs in buy_scores:
            strategies[str(bs)] = {
                'roi': 0.0,
                'trade_count': 0,
                'trades': [],
                'position': 0,        # 持有股數
                'buy_price': 0.0,     # 進場均價
                'balance': capital,   # 當前現金
                'initial_cap': capital
            }

        sell_scores_int = [int(s) for s in sell_scores]

        # 4. 步進歷史迴圈 (從第30根K棒開始確保均線有數值)
        for i in range(30, len(df)):
            sub_df = df.iloc[:i+1]
            analysis = calculate_technical_scores(sub_df, timeframe=tech_timeframe)
            
            if not analysis or 'scores' not in analysis: 
                continue
                
            current_score = int(analysis['scores']['Total'])
            current_price = float(df['Close'].iloc[i])
            current_time = df.index[i].strftime('%Y-%m-%d %H:%M')

            # 🎲 同時對所有「買入策略」進行獨立結算
            for bs_str, state in strategies.items():
                bs_int = int(bs_str)
                
                # --- 賣出邏輯 (若有持倉，檢查是否命中任一賣出分數) ---
                if state['position'] > 0:
                    if current_score in sell_scores_int:
                        qty = state['position']
                        # 賣出成本 = 手續費 + 交易稅
                        fee = current_price * qty * fee_rate
                        tax = current_price * qty * tax_rate
                        total_cost = fee + tax
                        
                        revenue = (current_price * qty) - total_cost
                        state['balance'] += revenue
                        
                        pnl_pct = ((current_price - state['buy_price']) / state['buy_price']) * 100
                        
                        state['trades'].append({
                            'time': current_time,
                            'action': 'SELL',
                            'price': round(current_price, 2),
                            'cost': round(total_cost, 0),
                            'balance': round(state['balance'], 0),
                            'pnl_pct': round(pnl_pct, 2)
                        })
                        
                        # 清空持倉
                        state['position'] = 0
                        state['buy_price'] = 0.0
                
                # --- 買入邏輯 (若空手，檢查是否命中該策略的專屬買入分數) ---
                elif state['position'] == 0:
                    if current_score == bs_int:
                        # 計算買得起的最大股數 (預扣手續費)
                        max_qty = state['balance'] / (current_price * (1 + fee_rate))
                        
                        if unit == 'lot':
                            qty = int(max_qty // 1000) * 1000  # 只買整張
                        else:
                            qty = int(max_qty)                 # 買零股
                            
                        # 如果資金還夠買
                        if qty > 0:
                            fee = current_price * qty * fee_rate
                            total_cost = (current_price * qty) + fee
                            
                            state['balance'] -= total_cost
                            state['position'] = qty
                            state['buy_price'] = current_price
                            state['trade_count'] += 1
                            
                            state['trades'].append({
                                'time': current_time,
                                'action': 'BUY',
                                'price': round(current_price, 2),
                                'cost': round(fee, 0),
                                'balance': round(state['balance'], 0),
                                'pnl_pct': 0.0
                            })

        # 5. 迴圈結束後，結算最終資產與 ROI
        for bs_str, state in strategies.items():
            final_asset = state['balance']
            
            # 如果回測結束時還有持倉，以最後一天收盤價強制平倉估值
            if state['position'] > 0:
                last_price = float(df['Close'].iloc[-1])
                sell_cost = (last_price * state['position']) * (fee_rate + tax_rate)
                final_asset += (last_price * state['position']) - sell_cost
            
            # 計算最終總報酬率
            state['roi'] = round(((final_asset - state['initial_cap']) / state['initial_cap']) * 100, 2)
            
            # 刪除不需要傳給前端的暫存變數
            del state['position']
            del state['buy_price']
            del state['initial_cap']

        # 6. 回傳前端所需的標準 JSON 格式
        return {
            "symbol": symbol,
            "name": symbol, # 這裡如果需要中文名，可串接您的名稱清單
            "strategies": strategies
        }

    except Exception as e:
        print(f"[{symbol}] 矩陣回測發生錯誤: {e}")
        return None

if __name__ == "__main__":
    # 測試程式碼
    test_symbol = "2330"
    print(f"--- 正在測試 {test_symbol} 即時算分 ---")
    print(get_instant_analysis(test_symbol))
    
    # 測試新的矩陣回測
    print(f"\n--- 正在測試 {test_symbol} 矩陣回測 ---")
    matrix_res = run_matrix_backtest(
        symbol=test_symbol,
        start_time="2024-01-01T09:00",
        end_time="2024-04-01T13:30",
        level="1d",
        capital=1000000,
        unit="share",
        fee_rate=0.001425,
        tax_rate=0.003,
        buy_scores=["-1", "1"],
        sell_scores=["5", "4", "-3"]
    )
    import json
    print(json.dumps(matrix_res, indent=2, ensure_ascii=False))