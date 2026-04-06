# Render 完整功能上線（給朋友測試）

本專案已支援兩種資料庫模式：
1. `DATABASE_URL` 有設定：使用外部 PostgreSQL（推薦，免費層也可持久化）
2. `DATABASE_URL` 未設定：回退使用本機 SQLite（會有重啟遺失風險）

## 1. 推到 GitHub
1. 把專案 push 到 GitHub。

## 2. 建立 Render Web Service（推薦用 Blueprint）
1. 到 Render 選 `New` -> `Blueprint`。
2. 指向你的 GitHub repo（會讀取 `render.yaml`）。
3. 直接建立服務；系統會自動套用：
   - Build：`pip install -r requirements.txt`
   - Start：`gunicorn --chdir web app:app --workers 1 --threads 4 --timeout 120`
   - Cron：`main_worker` 與 `stock_fetcher` 定時任務（自動抓資料）
   - `DATABASE_URL` 由 Render Dashboard 手動填入（sync: false）

## 3. 環境變數
在 Render 的 Environment 設定：
1. `DATABASE_URL`：填入 Supabase/Neon/Render Postgres 連線字串
1. `FLASK_SECRET_KEY`：請設成長且隨機字串（Blueprint 會自動產生）。
2. `FLASK_DEBUG`：`0`
3. `SESSION_COOKIE_SECURE`：`1`
4. `CROSS_DAY_SESSION_EXPIRE`：`0`（避免隔天被強制登出）
5. `STOCK_DB_PATH`：保留預設 `data/stock_system.db` 作為 fallback

## 4. 免費方案建議
若你希望盡量不花錢，建議使用外部 Postgres 免費層：

1. 建立 Supabase 或 Neon 專案（免費層）。
2. 取得 `DATABASE_URL`。
3. 在 Render Web 與兩個 Cron 服務都設定同一個 `DATABASE_URL`。
4. 部署後資料即由外部 DB 持久保存，不依賴容器磁碟。

## 4-1. SQLite 舊資料一鍵搬移到 Postgres
1. 在本機 terminal 設定 `DATABASE_URL`（Supabase/Neon 提供）。
2. 執行：
   `python migrate_sqlite_to_postgres.py`
3. 腳本會自動建立必要資料表，並搬移以下資料：
   - users / user_watchlist / user_settings / indicator_adjustment_log
   - market_raw / market_scores
   - stock_raw / stock_scores / stock_score_cache_15d
4. 腳本結尾會列出 Postgres 各表筆數做驗證。

## 5. 部署後測試
1. 開啟 Render 提供的 URL。
2. 註冊帳號並登入。
3. 測試搜尋個股、圖表、自選清單、登出。
4. 檢查健康端點：`/healthz` 應回 `{ "ok": true, "db": "ok" }`。
5. 重新部署一次後再登入，確認帳號與資料仍在（驗證外部 DB 持久化）。

## 6. 完整功能上線注意事項
1. 若使用 PostgreSQL，可支援多實例，穩定性優於 SQLite。
2. 若 `DATABASE_URL` 缺失，系統會回退到 SQLite（資料可能因重啟遺失）。
3. 若你想自訂網域，先確認 HTTPS 已啟用再開放使用。
