# 空氣品質資料管線 (V1.0)

## 專案簡介
串接環境部環境資料開放平臺的空氣品質指標 (AQI) API,定時抓取台北市各測站資料,
清洗後以正規化的結構寫入 MySQL,作為後續多資料源整合分析 (V2.0: 加入天氣資料;
V3.0: 加入交通流量資料) 的基礎資料層。

## 架構
```
API (環境部開放資料平台)
      |
      v
 fetch_aqi.py  ---- 抓取 + 清洗
      |
      v
   MySQL (stations / aqi_records 正規化雙表)
      ^
      |
 scheduler.py  ---- 每小時觸發一次
```

## 資料庫設計
- `stations`:測站基本資料 (site_id, site_name, county)
- `aqi_records`:各測站逐筆觀測數值 (aqi, pm2.5, pm10, o3, co, so2, no2 等),
  以 (site_id, publish_time) 做唯一鍵避免重複寫入

## 環境設置
1. 至 https://data.moenv.gov.tw 註冊會員取得 API Key
2. 複製 `.env.example` 為 `.env`,填入 API Key 與 MySQL 帳密
3. 啟動資料庫: `docker compose up -d`
4. 安裝套件: `pip install -r requirements.txt`
5. 手動測試抓取: `python fetch_aqi.py`
6. 啟動排程: `python scheduler.py`

## 後續規劃
- V2.0:加入中央氣象署天氣資料,設計測站地理對應關聯鍵,改用 Airflow 排程協調多來源任務
- V3.0:加入 TDX 交通流量資料,分析環境因素與交通流量的關聯性

## 工程筆記

**資料源更新頻率、缺值處理策略**
- API 每小時更新一次,同一測站同一時間重複抓取時,靠 `(site_id, publish_time)` 唯一鍵搭配 upsert 避免重複寫入
- 數值欄位(AQI、PM2.5 等)轉型失敗時一律存為 NULL,不中斷整批寫入;`site_id`、`publish_time` 缺失則直接跳過該筆,因為這兩者是關聯資料庫用來識別資料的必要欄位

**遇到的坑與排查過程**
1. **SSL 憑證驗證失敗**:`.gov.tw` 網域的憑證鏈缺少 Subject Key Identifier,新版 Python 的憑證驗證較嚴格導致連線失敗。改用系統信任的憑證庫(`pip-system-certs`)後解決。
2. **API 回傳格式不一致**:文件描述與實際回傳不符,API 有時直接回傳陣列,有時包在 `{"records": [...]}` 裡。改為先用 `isinstance()` 判斷型別,兩種情況都能正確解析。
3. **Docker volume 掛載檔案變成資料夾**:`docker-compose.yml` 掛載 `schema.sql` 時,若本機路徑當下不存在該檔案,Docker 會自動建立一個同名資料夾取代,導致初始化腳本從未被執行、資料表始終不存在。刪除誤建的資料夾、重新建立正確的檔案後解決。
4. **中文字元寫入後變成問號**:資料庫存取牽涉伺服器、連線、資料表三個層級的字元集設定,三者沒有全部對齊為 `utf8mb4` 就會在寫入時被砍成問號。最終在 `docker-compose.yml` 用 `command` 強制伺服器層級預設編碼,並在連線建立後執行 `SET NAMES utf8mb4` 雙重保險後解決。
5. **`ON DUPLICATE KEY UPDATE` 未涵蓋 `fetched_at`**:欄位的 `DEFAULT CURRENT_TIMESTAMP` 只在首次寫入時生效,同一小時內重複執行時該欄位不會更新,導致誤以為排程沒有真的重新抓取。修正為在更新語句中明確加入 `fetched_at = CURRENT_TIMESTAMP`。

