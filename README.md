# 空氣品質資料管線 (V2.0)

## 專案簡介
串接環境部空氣品質指標 (AQI) API 與中央氣象署雨量觀測 API,定時抓取台北市各測站資料,
清洗後以正規化的結構寫入 MySQL,並透過地理關聯鍵(Haversine 公式計算最近測站)將兩個
資料源串接起來,交由 Airflow 排程協調整條 pipeline 的執行順序與依賴關係。
(V3.0 規劃:單元測試、CI、資料品質監控、簡易查詢層、雲端部署)

## 架構
```
環境部 AQI API              中央氣象署雨量 API
      |                              |
      v                              v
 fetch_aqi.py                fetch_rainfall.py
 (抓取 + 清洗)                (抓取 + 攤平巢狀結構 + 清洗)
      |                              |
      v                              v
   MySQL: stations/aqi_records   MySQL: rain_stations/rainfall_records
      |______________________________|
                    |
                    v
        build_station_mapping.py
        (Haversine 公式計算最近測站,預先計算並儲存於 station_mapping)

以上三支程式由 Airflow DAG 排程協調:
    [fetch_aqi, fetch_rainfall] >> build_station_mapping
    排程:每小時第 5 分鐘觸發
```

## 資料庫設計
**V1.0(空氣品質)**
- `stations`:測站基本資料 (site_id, site_name, county, latitude, longitude)
- `aqi_records`:各測站逐筆觀測數值 (aqi, pm2.5, pm10, o3, co, so2, no2 等),
  以 (site_id, publish_time) 做唯一鍵避免重複寫入

**V2.0(雨量)**
- `rain_stations`:雨量測站基本資料 (site_id, site_name, county, latitude, longitude)
- `rainfall_records`:各測站逐筆雨量觀測 (precipitation),以 (site_id, obs_time) 做唯一鍵

**V2.0(地理關聯鍵)**
- `station_mapping`:預先計算並儲存每個空氣品質測站對應最近的雨量測站(含實際距離),
  避免每次查詢時重複計算;設計上採「預先計算並儲存」而非即時運算,因測站地理位置為靜態資料

## 環境設置

**空氣品質 + 雨量資料庫**
1. 分別至 https://data.moenv.gov.tw 與 https://opendata.cwa.gov.tw 申請 API 金鑰
2. 複製 `.env.example` 為 `.env`,填入金鑰與 MySQL 帳密
3. 啟動資料庫: `docker compose up -d`
4. 安裝套件: `pip install -r requirements.txt`
5. 依序執行: `python fetch_aqi.py` → `python fetch_rainfall.py` → `python build_station_mapping.py`

**Airflow 排程協調**
1. 啟動: `docker compose -f docker-compose.airflow.yml up -d`
2. 瀏覽器開啟 `http://localhost:8080`,帳密 admin/admin
3. 啟用 `air_quality_pipeline` 這個 DAG,即可依排程自動執行三支程式

## 後續規劃
- V3.0:單元測試、CI(GitHub Actions)、資料品質監控/告警機制、FastAPI 簡易查詢層、雲端部署
- 延伸方向(不預計實作,作為未來規劃):批次轉串流架構、結合論文背景的機器學習應用、CD 自動化部署

## 工程筆記

**資料源更新頻率、缺值處理策略**
- 空氣品質 API 每小時更新一次,雨量 API 支援指定時間窗口(採用 Past1hr 對齊空氣品質的時間顆粒度)
- 同一測站同一時間重複抓取時,靠唯一鍵搭配 upsert 避免重複寫入
- 數值欄位轉型失敗時一律存為 NULL,不中斷整批寫入;身分識別欄位(site_id、時間戳記)缺失則直接跳過該筆

**遇到的坑與排查過程**
1. **SSL 憑證驗證失敗**:`.gov.tw` 網域的憑證鏈缺少 Subject Key Identifier,新版 Python 的憑證驗證較嚴格導致連線失敗。改用系統信任的憑證庫(`pip-system-certs`)後解決。
2. **API 回傳格式不一致**:文件描述與實際回傳不符,空氣品質 API 有時直接回傳陣列,有時包在 `{"records": [...]}` 裡;雨量 API 則是多層巢狀結構(時間、經緯度、觀測值各自包在不同子物件裡),且經緯度同時提供 TWD67 與 WGS84 兩種座標系統,需篩選出 WGS84(國際通用標準)。
3. **Docker volume 掛載檔案變成資料夾**:`docker-compose.yml` 掛載 `schema.sql` 時,若本機路徑當下不存在該檔案,Docker 會自動建立一個同名資料夾取代,導致初始化腳本從未被執行、資料表始終不存在。刪除誤建的資料夾、重新建立正確的檔案後解決。
4. **中文字元寫入後變成問號**:資料庫存取牽涉伺服器、連線、資料表三個層級的字元集設定,三者沒有全部對齊為 `utf8mb4` 就會在寫入時被砍成問號。最終在 `docker-compose.yml` 用 `command` 強制伺服器層級預設編碼,並在連線建立後執行 `SET NAMES utf8mb4` 雙重保險後解決。
5. **`ON DUPLICATE KEY UPDATE` 未涵蓋時間戳記欄位**:欄位的 `DEFAULT CURRENT_TIMESTAMP` 只在首次寫入時生效,同一小時內重複執行時該欄位不會更新,導致誤以為排程沒有真的重新抓取。修正為在更新語句中明確加入該欄位的更新。
6. **Airflow 容器內無法連線本機 MySQL**:容器內部的 `localhost` 指向容器自身,不是宿主機。改用 Docker Desktop 提供的 `host.docker.internal` 這個特殊網址,在執行指令時覆蓋 `MYSQL_HOST` 環境變數,不需修改任何既有程式碼(`python-dotenv` 預設不覆蓋已存在的環境變數,故此法可行)。
7. **Airflow 容器缺少第三方套件**:採用官方提供的 `_PIP_ADDITIONAL_REQUIREMENTS` 環境變數,在容器啟動時自動安裝所需套件,避免另外維護一份 Dockerfile(官方文件註明此法僅適合開發環境,正式環境建議改為客製化映像檔)。

