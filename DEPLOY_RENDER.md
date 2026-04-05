# Render 完整功能上線（給朋友測試）

## 1. 推到 GitHub
1. 把專案 push 到 GitHub。

## 2. 建立 Render Web Service（推薦用 Blueprint）
1. 到 Render 選 `New` -> `Blueprint`。
2. 指向你的 GitHub repo（會讀取 `render.yaml`）。
3. 直接建立服務；系統會自動套用：
   - Build：`pip install -r requirements.txt`
   - Start：`gunicorn --chdir web app:app --workers 1 --threads 4 --timeout 120`
   - Persistent Disk：`/var/data`（SQLite 持久化）

## 3. 環境變數
在 Render 的 Environment 設定：
1. `FLASK_SECRET_KEY`：請設成長且隨機字串（Blueprint 會自動產生）。
2. `FLASK_DEBUG`：`0`
3. `SESSION_COOKIE_SECURE`：`1`
3. `STOCK_DB_PATH`：建議設成 `/var/data/stock_system.db`

## 4. 持久化資料庫（建議）
SQLite 若不掛載磁碟，服務重啟可能遺失資料。

1. 在 Render 建立一個 Persistent Disk。
2. Mount path 設為 `/var/data`。
3. 配合上面的 `STOCK_DB_PATH=/var/data/stock_system.db`。

## 5. 部署後測試
1. 開啟 Render 提供的 URL。
2. 註冊帳號並登入。
3. 測試搜尋個股、圖表、自選清單、登出。
4. 檢查健康端點：`/healthz` 應回 `{ "ok": true, "db": "ok" }`。
5. 重新部署一次後再登入，確認資料仍在（驗證磁碟持久化）。

## 6. 完整功能上線注意事項
1. 保持單一服務實例（避免 SQLite 同步問題）。
2. 多人同時測試可用，但高併發建議改 PostgreSQL。
3. 若你想自訂網域，先確認 HTTPS 已啟用再開放使用。
