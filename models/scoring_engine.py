def calculate_score_a(foreign_buy, sitc_buy, dealer_buy):
    """計算現貨籌碼分數 (A類)"""
    score = 0
    # 外資與投信：買超 +1, 賣超 -1
    if foreign_buy > 0: score += 1
    elif foreign_buy < 0: score -= 1
    
    if sitc_buy > 0: score += 1
    elif sitc_buy < 0: score -= 1
    
    # 自營商：買超 -1, 賣超 +1 (反向)
    if dealer_buy > 0: score -= 1
    elif dealer_buy < 0: score += 1
    
    # 這裡可以根據你的需求，決定A類是看總和，還是單純限制在 1, 0, -1
    # 若限制在區間：
    if score > 0: return 1
    elif score < 0: return -1
    return 0

def calculate_score_b(foreign_tx, foreign_mtx, foreign_elec, foreign_fin):
    """計算期貨籌碼分數 (B類)，回傳四個期指的分數"""
    def eval_score(net_buy):
        if net_buy > 0: return 1
        elif net_buy < 0: return -1
        return 0
    
    return {
        "TX": eval_score(foreign_tx),
        "MTX": eval_score(foreign_mtx),
        "ELEC": eval_score(foreign_elec),
        "FIN": eval_score(foreign_fin)
    }

def calculate_score_c(foreign_buy, twd_change, taiex_change, net_oi_status):
    """計算綜合連動指標 (C類 = B1 + B2 + B3)"""
    # B1: 外資現貨 vs 臺幣 (twd_change < 0 代表臺幣漲/升值)
    b1 = 0
    if foreign_buy > 0 and twd_change < 0: b1 = 1
    elif foreign_buy < 0 and twd_change > 0: b1 = -1
    
    # B2: 大盤 vs 臺幣
    b2 = 0
    if taiex_change > 0 and twd_change < 0: b2 = 1
    elif taiex_change < 0 and twd_change > 0: b2 = -1
    
    # B3: 外資單量增減 vs 期貨多空單 (net_oi_status: 1為多單多, -1為空單多)
    b3 = 0
    if foreign_buy > 0 and net_oi_status == 1: b3 = 1
    elif foreign_buy < 0 and net_oi_status == -1: b3 = 1
    elif foreign_buy > 0 and net_oi_status == -1: b3 = -1
    elif foreign_buy < 0 and net_oi_status == 1: b3 = -1
    
    return b1 + b2 + b3

def generate_diagnosis(total_score):
    """根據總分產生診斷文字"""
    if total_score >= 2:
        return "強烈進場 (偏多方，力道強勁)"
    elif total_score <= -2:
        return "減碼/做空 (偏空方，力道強勁)"
    else:
        return "觀望 (市場訊號紛雜)"