# 空氣品質資料管線 (V3.0)

## 專案簡介
串接環境部空氣品質指標 (AQI) API 與中央氣象署雨量觀測 API,定時抓取台北市各測站資料,
清洗後以正規化的結構寫入 MySQL,並透過地理關聯鍵(Haversine 公式計算最近測站)將兩個
資料源串接起來,交由 Airflow 排程協調整條 pipeline 的執行順序與依賴關係。
V3.0 在既有 pipeline 基礎上,補齊單元測試、CI、資料品質監控、FastAPI 查詢層,並嘗試將
系統部署至雲端,過程中對資源限制與架構取捨做了完整記錄(詳見下方工程筆記)。

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
        ____________|____________
       |                         |
       v                         v
build_station_mapping.py   data_quality_check.py
(計算最近測站,存入          (檢查數值是否違反定義上的合理範圍,
 station_mapping)            如負數/超過上限,存入 data_quality_issues)

以上四支程式由 Airflow DAG 排程協調:
    [fetch_aqi, fetch_rainfall] >> build_station_mapping
    [fetch_aqi, fetch_rainfall] >> data_quality_check
    排程:每小時第 5 分鐘觸發

                    |
                    v
              db_queries.py
                    |
                    v
                 api.py (FastAPI)
    對外提供測站清單/最新資料/歷史趨勢/異常紀錄查詢
```

## 資料庫設計
**V1.0(空氣品質)**
- `stations`:測站基本資料 (site_id, site_name, county, latitude, longitude)
- `aqi_records`:各測站逐筆觀測數值 (aqi, pm2.5, pm10, o3, co, so2, no2 等),
  以 (site_id, publish_time) 做唯一鍵避免重複寫入

**V2.0(雨量 / 地理關聯鍵)**
- `rain_stations`:雨量測站基本資料
- `rainfall_records`:各測站逐筆雨量觀測 (precipitation),以 (site_id, obs_time) 做唯一鍵
- `station_mapping`:預先計算並儲存每個空氣品質測站對應最近的雨量測站(含實際距離),
  設計上採「預先計算並儲存」而非即時運算,因測站地理位置為靜態資料

**V3.0(資料品質監控)**
- `data_quality_issues`:記錄檢測到的異常數值(來源、測站、欄位、異常類型、原始值),
  只針對「定義上不可能」的數值(如負數、超過理論上限)進行標記,不處理統計上的離群值
  (如颱風天的高雨量屬於真實資料,不應被誤判為異常)

## 查詢層(FastAPI)
- `GET /stations`:測站清單,附上最近雨量站與距離
- `GET /stations/{site_id}/latest`:最新 AQI 資料,若有配對雨量站則一併附上
- `GET /stations/{site_id}/history`:指定時間區間的歷史趨勢
- `GET /data-quality-issues`:資料品質異常紀錄,可依來源篩選

## 測試與 CI
- 使用 pytest,針對純邏輯函式(清洗、距離計算、資料品質判斷)撰寫單元測試,並用
  `unittest.mock` 模擬外部 API 回應與 FastAPI 端點,共 37 個測試
- GitHub Actions 於每次 push / PR 時自動執行語法檢查與完整測試套件

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
3. 啟用 `air_quality_pipeline` 這個 DAG,即可依排程自動執行四支程式

**查詢層(FastAPI)**
1. 啟動: `docker compose -f docker-compose.api.yml up -d --build`
2. 瀏覽器開啟 `http://localhost:8000/docs` 查看互動式 API 文件

**測試**
```
pip install pytest httpx
pytest tests/
```

## 後續規劃
- 延伸方向(不預計實作,作為未來規劃):CD 自動化部署、資料品質告警通知(Discord)、
  簡易資料視覺化端點、批次轉串流架構、結合論文背景的機器學習應用

## 工程筆記

**V1.0/V2.0 遺留**
1. **SSL 憑證驗證失敗**:`.gov.tw` 網域的憑證鏈缺少 Subject Key Identifier,新版 Python 的憑證驗證較嚴格導致連線失敗。本機環境改用系統信任的憑證庫(`pip-system-certs`)後解決。
2. **API 回傳格式不一致**:空氣品質 API 有時直接回傳陣列,有時包在 `{"records": [...]}` 裡;雨量 API 則是多層巢狀結構,且經緯度同時提供 TWD67 與 WGS84 兩種座標系統,需篩選出 WGS84。
3. **Docker volume 掛載檔案變成資料夾**:掛載 `schema.sql` 時,若本機路徑當下不存在該檔案,Docker 會自動建立同名資料夾取代,導致初始化腳本從未被執行。
4. **中文字元寫入後變成問號**:資料庫伺服器、連線、資料表三個層級的字元集需全部對齊 `utf8mb4`。
5. **`ON DUPLICATE KEY UPDATE` 未涵蓋時間戳記欄位**:`DEFAULT CURRENT_TIMESTAMP` 只在首次寫入生效,需在更新語句中明確加入該欄位。
6. **Airflow 容器內無法連線本機 MySQL**:改用 `host.docker.internal`,執行指令時覆蓋 `MYSQL_HOST` 環境變數。
7. **Airflow 容器缺少第三方套件**:採用 `_PIP_ADDITIONAL_REQUIREMENTS` 環境變數於容器啟動時自動安裝(官方文件註明僅適合開發環境)。

**V3.0 新增**
8. **測試撰寫時發現的實際 bug**:`find_nearest_rain_station()` 原先寫法在座標為 `None` 時,先執行 `float(None)` 直接拋出例外,而非設計預期的優雅回傳 `None`。撰寫邊界情況測試時發現此問題,修正判斷順序後解決。
9. **不合理數值 vs. 統計離群值的界線**:資料品質監控設計初期曾考慮以資料庫現有數值的分布範圍設定異常門檻,但該做法會將真實但少見的極端天氣(如颱風高雨量)誤判為異常。改為依據指標**定義本身**(數值範圍、型別)設定門檻,而非依賴現有樣本統計。
10. **PowerShell 不支援 `<` 重新導向語法**:將整份 `schema.sql` 灌入容器時,`docker exec -i ... < db/schema.sql` 在 PowerShell 報錯(`RedirectionNotSupported`)。改用 `Get-Content db/schema.sql | docker exec -i ...` 的原生 PowerShell 語法後解決。
11. **雲端部署的資源限制與架構取捨**:嘗試將 MySQL、Airflow、FastAPI 完整部署至 AWS EC2 時,`t3.micro`(1GB 記憶體)的硬碟空間先不足以下載 Airflow 映像檔;更換至儲存空間充足的執行個體後,記憶體仍不足以同時穩定運行 MySQL 與完整 Airflow(webserver + scheduler + 獨立 PostgreSQL),`airflow_scheduler` 反覆被系統終止。升級至 `t3.small`(2GB)並調整 webserver worker 數量後,記憶體壓力仍逼近上限。評估後判斷:若僅將排程留在本機、資料庫與 API 部署雲端,會產生「雲端服務資料新鮮度依賴本機是否開機」的架構矛盾。因此決定將完整系統保留於本機 Docker 環境運行;雲端所需的容器化配置(`Dockerfile`、`docker-compose.api.yml`)已完成並驗證可行(MySQL 與 FastAPI 曾成功部署於雲端並正確查詢資料)。
12. **雲端環境的 SSL 憑證驗證問題與本機不同**:EC2 主機的 Python 版本較新,連線環境部 API 時出現與本機不同的 SSL 驗證錯誤(`Missing Subject Key Identifier`),推測為新版 OpenSSL 對 TWCA 憑證鏈的驗證邏輯更嚴格所致;因僅為驗證雲端連線可行性的暫時性測試,故於該次測試中以 `verify=False` 繞過,並非本機/正式版本採用的解法。
