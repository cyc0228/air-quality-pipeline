"""
V1.0 骨架:抓取台北市空氣品質指標 (AQI) 資料,清洗後寫入 MySQL。

流程:
1. 呼叫環境部開放資料平台 API,取得台北市各測站最新 AQI 資料
2. 清洗/轉型欄位 (字串轉數值、缺值處理)
3. Upsert 寫入 stations、aqi_records 兩張表 (正規化設計)
"""

import os
import logging
from datetime import datetime

import requests
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

API_URL = "https://data.moenv.gov.tw/api/v2/aqx_p_432"
API_KEY = os.getenv("MOENV_API_KEY")
TARGET_COUNTY = "臺北市"  # V1.0 先鎖定台北市測站


def fetch_raw_data() -> list[dict]:
    """呼叫 API,取得所有測站資料,篩選出台北市部分。"""
    params = {
        "api_key": API_KEY,
        "limit": 1000,
        "format": "json",
    }
    resp = requests.get(API_URL, params=params, timeout=15)
    resp.raise_for_status()
    resp.encoding = "utf-8"  # 明確指定編碼,避免 requests 誤判導致中文亂碼
    payload = resp.json()

    # 這個 API 有時直接回傳陣列,有時回傳 {"records": [...]},兩種都要能處理
    if isinstance(payload, list):
        records = payload
    else:
        records = payload.get("records", [])

    taipei_records = [r for r in records if r.get("county") == TARGET_COUNTY]
    logger.info(f"抓到 {len(records)} 筆全台資料,篩選出台北市 {len(taipei_records)} 筆")
    return taipei_records


def clean_record(raw: dict) -> dict:
    """把 API 回傳的字串欄位轉成適合寫入資料庫的型別,缺值一律轉 None。"""

    def to_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def to_int(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    return {
        "site_id": raw.get("siteid"),
        "site_name": raw.get("sitename"),
        "county": raw.get("county"),
        "latitude": to_float(raw.get("latitude")),
        "longitude": to_float(raw.get("longitude")),
        "publish_time": raw.get("publishtime"),
        "aqi": to_int(raw.get("aqi")),
        "status": raw.get("status"),
        "pm2_5": to_float(raw.get("pm2.5")),
        "pm10": to_float(raw.get("pm10")),
        "o3": to_float(raw.get("o3")),
        "co": to_float(raw.get("co")),
        "so2": to_float(raw.get("so2")),
        "no2": to_float(raw.get("no2")),
    }


def get_db_connection():
    conn = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
        charset="utf8mb4",
    )
    cursor = conn.cursor()
    cursor.execute("SET NAMES utf8mb4")  # 雙重保險,強制這個連線用utf8mb4溝通
    cursor.close()
    return conn


def upsert_station(cursor, record: dict):
    cursor.execute(
        """
        INSERT INTO stations (site_id, site_name, county, latitude, longitude)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            site_name = VALUES(site_name), county = VALUES(county),
            latitude = VALUES(latitude), longitude = VALUES(longitude)
        """,
        (record["site_id"], record["site_name"], record["county"],
         record["latitude"], record["longitude"]),
    )


def upsert_aqi_record(cursor, record: dict):
    cursor.execute(
        """
        INSERT INTO aqi_records
            (site_id, publish_time, aqi, status, pm2_5, pm10, o3, co, so2, no2)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            aqi = VALUES(aqi), status = VALUES(status),
            pm2_5 = VALUES(pm2_5), pm10 = VALUES(pm10),
            o3 = VALUES(o3), co = VALUES(co), so2 = VALUES(so2), no2 = VALUES(no2),            
            fetched_at = CURRENT_TIMESTAMP
        """,
        (
            record["site_id"], record["publish_time"], record["aqi"], record["status"],
            record["pm2_5"], record["pm10"], record["o3"], record["co"],
            record["so2"], record["no2"],
        ),
    )


def run():
    logger.info("開始抓取空氣品質資料...")
    raw_records = fetch_raw_data()
    cleaned = [clean_record(r) for r in raw_records]

    conn = get_db_connection()
    cursor = conn.cursor()

    for record in cleaned:
        if not record["site_id"] or not record["publish_time"]:
            continue  # 關鍵欄位缺失,跳過這筆
        upsert_station(cursor, record)
        upsert_aqi_record(cursor, record)

    conn.commit()
    cursor.close()
    conn.close()
    logger.info(f"完成,共寫入/更新 {len(cleaned)} 筆測站資料")

if __name__ == "__main__":
    run()
