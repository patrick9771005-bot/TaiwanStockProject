# 此檔案包含 KD/MACD 調整記錄的 API 端點
# 將以下內容加入 web/app.py

# 在 ensure_user_tables() 函式的 conn.commit() 之前加入:
# cursor.execute('''
#     CREATE TABLE IF NOT EXISTS indicator_adjustment_log (
#         id INTEGER PRIMARY KEY AUTOINCREMENT,
#         user_id INTEGER NOT NULL,
#         symbol TEXT NOT NULL,
#         indicator_type TEXT NOT NULL,
#         timeframe TEXT,
#         change_pct REAL,
#         original_score INTEGER,
#         adjusted_score INTEGER,
#         adjusted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#         FOREIGN KEY(user_id) REFERENCES users(id)
#     )
# ''')

# 在 app.run() 之前加入以下 API 端點:

from flask import jsonify, request

# --------------------------------------------------------
# API: 記錄 KD/MACD 手動調整
# --------------------------------------------------------
@app.route('/api/log-adjustment', methods=['POST'])
def api_log_adjustment():
    try:
        user_id = current_user_id()
        if not user_id:
            return jsonify({"error": "未登入"}), 401

        data = request.get_json() or {}
        symbol = data.get('symbol')
        indicator_type = data.get('indicator_type')  # 'MACD' or 'KD'
        timeframe = data.get('timeframe', '1d')
        change_pct = float(data.get('change_pct', 0))
        original_score = int(data.get('original_score', 0))
        adjusted_score = int(data.get('adjusted_score', 0))

        if not symbol or not indicator_type:
            return jsonify({"error": "缺少 symbol 或 indicator_type"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO indicator_adjustment_log
            (user_id, symbol, indicator_type, timeframe, change_pct, original_score, adjusted_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, symbol, indicator_type, timeframe, change_pct, original_score, adjusted_score))
        conn.commit()
        conn.close()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --------------------------------------------------------
# API: 查詢 KD/MACD 調整記錄
# --------------------------------------------------------
@app.route('/api/adjustment-history', methods=['GET'])
def api_adjustment_history():
    try:
        user_id = current_user_id()
        if not user_id:
            return jsonify({"error": "未登入"}), 401

        limit = int(request.args.get('limit', 500))
        indicator_filter = request.args.get('indicator')
        symbol_filter = request.args.get('symbol')

        conn = get_db_connection()
        cursor = conn.cursor()

        query = "SELECT id, symbol, indicator_type, timeframe, change_pct, original_score, adjusted_score, adjusted_at FROM indicator_adjustment_log WHERE user_id = ?"
        params = [user_id]

        if indicator_filter:
            query += " AND indicator_type = ?"
            params.append(indicator_filter)
        if symbol_filter:
            query += " AND symbol = ?"
            params.append(symbol_filter)

        query += " ORDER BY adjusted_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        items = [
            {
                "id": r['id'],
                "symbol": r['symbol'],
                "indicator_type": r['indicator_type'],
                "timeframe": r['timeframe'],
                "change_pct": round(float(r['change_pct']), 4) if r['change_pct'] is not None else None,
                "original_score": r['original_score'],
                "adjusted_score": r['adjusted_score'],
                "adjusted_at": r['adjusted_at']
            }
            for r in rows
        ]

        return jsonify({"count": len(items), "data": items})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
