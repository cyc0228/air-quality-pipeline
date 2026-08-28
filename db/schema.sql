-- 空氣品質資料庫結構 (V1.0)
-- 設計原則:測站基本資料與觀測數值分表,避免像交易機器人那次一樣混在同一張大表

CREATE TABLE IF NOT EXISTS stations (
    site_id     VARCHAR(20) PRIMARY KEY,   -- 測站代碼 (SiteId)
    site_name   VARCHAR(50) NOT NULL,      -- 測站名稱 (SiteName)
    county      VARCHAR(20) NOT NULL,      -- 縣市 (County)
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

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
);

CREATE INDEX idx_aqi_publish_time ON aqi_records (publish_time);
