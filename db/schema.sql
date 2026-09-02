-- 空氣品質資料庫結構 (V1.0)
-- 設計原則:測站基本資料與觀測數值分表,避免像交易機器人那次一樣混在同一張大表

CREATE TABLE IF NOT EXISTS stations (
    site_id     VARCHAR(20) PRIMARY KEY,   -- 測站代碼 (SiteId)
    site_name   VARCHAR(50) NOT NULL,      -- 測站名稱 (SiteName)
    county      VARCHAR(20) NOT NULL,      -- 縣市 (County)
    latitude    DECIMAL(9,6) NULL,         -- 緯度 (WGS84),V2.0多來源地理關聯鍵用
    longitude   DECIMAL(9,6) NULL,         -- 經度 (WGS84)
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS aqi_records (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    site_id         VARCHAR(20) NOT NULL,
    publish_time    DATETIME NOT NULL,      -- 資料發布時間 (PublishTime)
    aqi             INT NULL,               -- AQI 數值
    status          VARCHAR(20) NULL,       -- 空品狀態 (良好/普通/對敏感族群不健康...)
    pm2_5           DECIMAL(6,2) NULL,
    pm10            DECIMAL(6,2) NULL,
    o3              DECIMAL(6,2) NULL,
    co              DECIMAL(6,2) NULL,
    so2             DECIMAL(6,2) NULL,
    no2             DECIMAL(6,2) NULL,
    fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_station FOREIGN KEY (site_id) REFERENCES stations(site_id),
    UNIQUE KEY uniq_site_time (site_id, publish_time)  -- 避免同一測站同一時間重複寫入
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_aqi_publish_time ON aqi_records (publish_time);


-- 雨量觀測資料庫結構 (V2.0)
-- 設計邏輯與空氣品質相同:測站身分與觀測數值分表

CREATE TABLE IF NOT EXISTS rain_stations (
    site_id     VARCHAR(20) PRIMARY KEY,   -- 測站代碼 (StationId)
    site_name   VARCHAR(50) NOT NULL,      -- 測站名稱 (StationName)
    county      VARCHAR(20) NOT NULL,      -- 縣市 (CountyName)
    latitude    DECIMAL(9,6) NULL,         -- 緯度 (WGS84)
    longitude   DECIMAL(9,6) NULL,         -- 經度 (WGS84)
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS rainfall_records (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    site_id         VARCHAR(20) NOT NULL,
    obs_time        DATETIME NOT NULL,      -- 觀測時間 (ObsTime.DateTime)
    precipitation   DECIMAL(6,2) NULL,      -- 過去一小時雨量 (mm)
    fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_rain_station FOREIGN KEY (site_id) REFERENCES rain_stations(site_id),
    UNIQUE KEY uniq_rain_site_time (site_id, obs_time)  -- 避免同一測站同一時間重複寫入
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_rainfall_obs_time ON rainfall_records (obs_time);


-- 地理關聯鍵 (V2.0)
-- 預先計算並儲存每個空氣品質測站對應最近的雨量測站,避免每次查詢時重複計算距離

CREATE TABLE IF NOT EXISTS station_mapping (
    aqi_site_id     VARCHAR(20) PRIMARY KEY,
    rain_site_id    VARCHAR(20) NOT NULL,
    distance_km     DECIMAL(6,2) NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_mapping_aqi FOREIGN KEY (aqi_site_id) REFERENCES stations(site_id),
    CONSTRAINT fk_mapping_rain FOREIGN KEY (rain_site_id) REFERENCES rain_stations(site_id)
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
