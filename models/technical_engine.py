import pandas as pd


def resolve_kd_score(curr_k, prev_k, curr_d, prev_d, mode='precise', zero_if_small=False, threshold_pct=0.0):
    if pd.isna(curr_k) or pd.isna(prev_k) or pd.isna(curr_d) or pd.isna(prev_d):
        return 0, None, False

    curr_k = float(curr_k)
    prev_k = float(prev_k)
    curr_d = float(curr_d)
    prev_d = float(prev_d)

    k_diff = curr_k - prev_k
    curr_gap = curr_k - curr_d
    prev_gap = prev_k - prev_d
    gap_diff = curr_gap - prev_gap
    denominator = max(abs(curr_gap), abs(prev_gap), abs(curr_k), abs(prev_k), 1e-9)
    change_pct = abs(gap_diff) / denominator * 100

    slope_eps = 0.15
    gap_eps = 0.15
    kd_entangled = abs(curr_gap) < 0.5 or abs(k_diff) < slope_eps

    if mode == 'strict':
        if gap_diff > 0:
            return 1, change_pct, kd_entangled
        if gap_diff < 0:
            return -1, change_pct, kd_entangled
        return 0, change_pct, kd_entangled

    if kd_entangled:
        return 0, change_pct, kd_entangled
    if k_diff < -slope_eps or (curr_gap > 0 and gap_diff < -gap_eps):
        return -1, change_pct, kd_entangled
    if k_diff > slope_eps or (curr_gap > 0 and gap_diff > gap_eps):
        return 1, change_pct, kd_entangled
    return 0, change_pct, kd_entangled


def resolve_macd_score(curr_osc, prev_osc, mode='precise', zero_if_small=False, threshold_pct=0.0):
    if pd.isna(curr_osc) or pd.isna(prev_osc):
        return 0, None

    curr_osc = float(curr_osc)
    prev_osc = float(prev_osc)
    osc_diff = curr_osc - prev_osc
    denominator = max(abs(curr_osc), abs(prev_osc), 1e-9)
    change_pct = abs(osc_diff) / denominator * 100

    if mode == 'strict':
        if osc_diff > 0:
            return 1, change_pct
        if osc_diff < 0:
            return -1, change_pct
        return 0, change_pct

    macd_score = 0
    eps = 0.02
    if curr_osc >= 0:
        if curr_osc > prev_osc + eps:
            macd_score = 1
        elif curr_osc < prev_osc - eps:
            macd_score = -1
    else:
        if curr_osc > prev_osc + eps:
            macd_score = 1
        elif curr_osc < prev_osc - eps:
            macd_score = -1

    # 若設定低於閾值時歸 0，則檢查
    if zero_if_small and threshold_pct > 0 and change_pct < threshold_pct:
        macd_score = 0

    return macd_score, change_pct

def calculate_technical_scores(df_history, timeframe='daily', macd_mode='precise', macd_zero_if_small=False, macd_zero_threshold_pct=0.0, kd_mode='precise', kd_zero_if_small=False, kd_zero_threshold_pct=0.0):
    """
    接收歷史 K 線 DataFrame，使用純 Pandas 計算指標，避免套件依賴問題。
    """
    df = df_history.copy()
    
    # === 解決 yfinance 新版雙層表頭 (MultiIndex) 的問題 ===
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    # =======================================================
    
    # === 1. 動態均線設定 (MA) ===
    if timeframe == 'monthly':
        p_short, p_mid, p_long = 3, 6, 12
    elif timeframe == 'weekly':
        p_short, p_mid, p_long = 5, 13, 26
    else: 
        p_short, p_mid, p_long = 5, 10, 20

    # 使用 pandas 內建的 rolling 計算移動平均
    df['MA_short'] = df['Close'].rolling(window=p_short).mean()
    df['MA_mid']   = df['Close'].rolling(window=p_mid).mean()
    df['MA_long']  = df['Close'].rolling(window=p_long).mean()
    
    curr_ma_s, curr_ma_m, curr_ma_l = df['MA_short'].iloc[-1], df['MA_mid'].iloc[-1], df['MA_long'].iloc[-1]
    
    ma_score = 0
    if curr_ma_s > curr_ma_m > curr_ma_l: ma_score = 1
    elif curr_ma_s < curr_ma_m < curr_ma_l: ma_score = -1
        
    # === 2. KD 指標 (9T, 平滑3) ===
    # 計算 9 日內的最高與最低
    low_min = df['Low'].rolling(window=9).min()
    high_max = df['High'].rolling(window=9).max()
    
    # 計算 RSV 與 K 值
    df['RSV'] = 100 * (df['Close'] - low_min) / (high_max - low_min)
    df['K'] = df['RSV'].rolling(window=3).mean()
    df['D'] = df['K'].rolling(window=3).mean()
    
    curr_k = df['K'].iloc[-1]
    prev_k = df['K'].iloc[-2]
    curr_d = df['D'].iloc[-1]
    prev_d = df['D'].iloc[-2]
    kd_score, kd_change_pct, kd_entangled = resolve_kd_score(
        curr_k,
        prev_k,
        curr_d,
        prev_d,
        mode=kd_mode,
        zero_if_small=kd_zero_if_small,
        threshold_pct=kd_zero_threshold_pct
    )

    # === 3. RSI (5T, 10T) ===
    def calculate_rsi(series, period):
        delta = series.diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    df['RSI5'] = calculate_rsi(df['Close'], 5)
    df['RSI10'] = calculate_rsi(df['Close'], 10)
    curr_rsi5, curr_rsi10 = df['RSI5'].iloc[-1], df['RSI10'].iloc[-1]
    
    rsi_score = 1 if curr_rsi5 > curr_rsi10 else -1
    rsi_entangled = abs(curr_rsi5 - curr_rsi10) < 0.5 

    # === 4. MACD (12T, 26T, 9T) ===
    ema_fast = df['Close'].ewm(span=12, adjust=False).mean()
    ema_slow = df['Close'].ewm(span=26, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    df['MACD_line'] = macd_line
    df['MACD_signal'] = signal_line
    df['OSC'] = macd_line - signal_line # 柱狀圖
    
    curr_osc = df['OSC'].iloc[-1] 
    prev_osc = df['OSC'].iloc[-2]
    
    osc_diff = curr_osc - prev_osc
    macd_score, macd_change_pct = resolve_macd_score(
        curr_osc,
        prev_osc,
        mode=macd_mode,
        zero_if_small=macd_zero_if_small,
        threshold_pct=macd_zero_threshold_pct
    )

    macd_entangled = abs(osc_diff) < 0.05 

    # === 5. 交易量與 K 線型態 (Volume) ===
    curr_close, curr_open = df['Close'].iloc[-1], df['Open'].iloc[-1]
    curr_vol, prev_vol = df['Volume'].iloc[-1], df['Volume'].iloc[-2]
    
    is_red = curr_close > curr_open
    is_vol_expand = curr_vol > prev_vol
    
    vol_score = 0
    if is_red and is_vol_expand: vol_score = 1
    elif is_red and not is_vol_expand: vol_score = -1
    elif not is_red and is_vol_expand: vol_score = -1
    elif not is_red and not is_vol_expand: vol_score = 1

    # === 6. 乖離率 (僅日K顯示：((收盤價/五日均線)-1) * 100%) ===
    bias_pct = None
    if timeframe == 'daily' and pd.notna(curr_ma_s) and curr_ma_s != 0:
        bias_pct = ((curr_close / curr_ma_s) - 1) * 100
    
    total_score = ma_score + kd_score + rsi_score + macd_score + vol_score

    # 💡 關鍵修復點：將所有的值套上 int() 與 bool()，徹底解決 Numpy 型態引發的 JSON 報錯！
    return {
        "scores": {
            "MA": int(ma_score), 
            "KD": int(kd_score), 
            "RSI": int(rsi_score), 
            "MACD": int(macd_score), 
            "Volume": int(vol_score), 
            "Total": int(total_score)
        },
        "flags": {
            "KD_entangled": bool(kd_entangled), 
            "RSI_entangled": bool(rsi_entangled), 
            "MACD_entangled": bool(macd_entangled)
        },
        "metrics": {
            "bias_pct": round(float(bias_pct), 2) if bias_pct is not None else None,
            "kd_change_pct": round(float(kd_change_pct), 4) if kd_change_pct is not None else None,
            "macd_change_pct": round(float(macd_change_pct), 4) if macd_change_pct is not None else None
        },
        "indicators": {
            "ma_short": round(float(curr_ma_s), 4) if pd.notna(curr_ma_s) else None,
            "ma_mid": round(float(curr_ma_m), 4) if pd.notna(curr_ma_m) else None,
            "ma_long": round(float(curr_ma_l), 4) if pd.notna(curr_ma_l) else None,
            "k": round(float(df['K'].iloc[-1]), 4) if pd.notna(df['K'].iloc[-1]) else None,
            "prev_k": round(float(prev_k), 4) if pd.notna(prev_k) else None,
            "d": round(float(df['D'].iloc[-1]), 4) if pd.notna(df['D'].iloc[-1]) else None,
            "prev_d": round(float(prev_d), 4) if pd.notna(prev_d) else None,
            "rsi5": round(float(curr_rsi5), 4) if pd.notna(curr_rsi5) else None,
            "rsi10": round(float(curr_rsi10), 4) if pd.notna(curr_rsi10) else None,
            "macd": round(float(df['MACD_line'].iloc[-1]), 6) if pd.notna(df['MACD_line'].iloc[-1]) else None,
            "signal": round(float(df['MACD_signal'].iloc[-1]), 6) if pd.notna(df['MACD_signal'].iloc[-1]) else None,
            "osc": round(float(curr_osc), 6) if pd.notna(curr_osc) else None,
            "prev_osc": round(float(prev_osc), 6) if pd.notna(prev_osc) else None,
            "volume": int(float(curr_vol)) if pd.notna(curr_vol) else None
        }
    }