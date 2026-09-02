"""
V2.0 骨架:抓取全台雨量觀測資料,篩選台北市部分,清洗後寫入 MySQL。

跟 fetch_aqi.py 的差異:這份 API 回傳的資料是多層巢狀結構
(時間包在 ObsTime 裡、經緯度是一個清單、雨量包在 RainfallElement 裡),
需要額外的攤平邏輯。
"""

import os
import logging

import requests
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

API_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0002-001"
CWA_API_KEY = os.getenv("CWA_API_KEY")
TARGET_COUNTY = "臺北市"


def fetch_raw_data() -> list[dict]:
    """呼叫中央氣象署雨量API,取得所有測站資料,篩選出台北市部分。"""
    params = {
        "Authorization": CWA_API_KEY,
        "format": "JSON",
        "RainfallElement": "Past1hr",
    }
    resp = requests.get(API_URL, params=params, timeout=15)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    payload = resp.json()

    # 這份API的records是dict,真正的清單包在 records -> Station 底下
    records = payload.get("records", {}).get("Station", [])

    taipei_records = [
        r for r in records
        if r.get("GeoInfo", {}).get("CountyName") == TARGET_COUNTY
    ]
    logger.info(f"抓到 {len(records)} 筆全台雨量站資料,篩選出台北市 {len(taipei_records)} 筆")
    return taipei_records


def clean_record(raw: dict) -> dict:
    """把雨量API的巢狀資料,攤平並轉型成適合寫入資料庫的格式。"""

    def to_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    # 從 GeoInfo.Coordinates 這個清單裡,挑出 WGS84 那一組座標(國際通用標準)
    coordinates = raw.get("GeoInfo", {}).get("Coordinates", [])
    wgs84 = next((c for c in coordinates if c.get("CoordinateName") == "WGS84"), None)

    return {
        "site_id": raw.get("StationId"),
        "site_name": raw.get("StationName"),
        "county": raw.get("GeoInfo", {}).get("CountyName"),
        "latitude": to_float(wgs84.get("StationLatitude")) if wgs84 else None,
        "longitude": to_float(wgs84.get("StationLongitude")) if wgs84 else None,
        "obs_time": raw.get("ObsTime", {}).get("DateTime"),
        "precipitation": to_float(
            raw.get("RainfallElement", {}).get("Past1hr", {}).get("Precipitation")
        ),
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
    cursor.execute("SET NAMES utf8mb4")
    cursor.close()
    return conn


def upsert_rain_station(cursor, record: dict):
    cursor.execute(
        """
        INSERT INTO rain_stations (site_id, site_name, county, latitude, longitude)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            site_name = VALUES(site_name), county = VALUES(county),
            latitude = VALUES(latitude), longitude = VALUES(longitude)
        """,
        (record["site_id"], record["site_name"], record["county"],
         record["latitude"], record["longitude"]),
    )


def upsert_rainfall_record(cursor, record: dict):
    cursor.execute(
        """
        INSERT INTO rainfall_records (site_id, obs_time, precipitation)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            precipitation = VALUES(precipitation),
            fetched_at = CURRENT_TIMESTAMP
        """,
        (record["site_id"], record["obs_time"], record["precipitation"]),
    )


def run():
    logger.info("開始抓取雨量資料...")
    raw_records = fetch_raw_data()
    cleaned = [clean_record(r) for r in raw_records]

    conn = get_db_connection()
    cursor = conn.cursor()

    for record in cleaned:
        if not record["site_id"] or not record["obs_time"]:
            continue
        upsert_rain_station(cursor, record)
        upsert_rainfall_record(cursor, record)

    conn.commit()
    cursor.close()
    conn.close()
    logger.info(f"完成,共寫入/更新 {len(cleaned)} 筆雨量站資料")


if __name__ == "__main__":
    run()
