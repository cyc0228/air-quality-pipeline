"""
V2.0 地理關聯鍵:計算每個空氣品質測站,距離最近的雨量測站是哪一個。

設計考量:
- 測站地理位置是靜態資料,採用「預先計算並儲存」而非每次查詢時即時計算
- 用 Haversine 公式計算球面距離,不能直接比較經緯度數字差
- 若最近的雨量站距離仍然太遠(超過 MAX_DISTANCE_KM),視為配對失敗,標記為 None
"""

import os
import math
import logging

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MAX_DISTANCE_KM = 10.0  # 超過這個距離,視為附近沒有合適的雨量站可對應


def haversine_distance(lat1, lon1, lat2, lon2) -> float:
    """計算兩個經緯度座標之間的實際球面距離(公里)。"""
    R = 6371.0  # 地球平均半徑(公里)

    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)

    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return R * c


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


def fetch_stations(cursor, table_name: str) -> list[dict]:
    """從資料庫讀取測站清單(適用 stations 或 rain_stations 表)。"""
    cursor.execute(f"SELECT site_id, site_name, latitude, longitude FROM {table_name}")
    columns = ["site_id", "site_name", "latitude", "longitude"]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def find_nearest_rain_station(aqi_station: dict, rain_stations: list[dict]) -> dict | None:
    """找出離這個空氣品質測站最近的雨量測站,超過門檻距離則回傳 None。"""

    if aqi_station["latitude"] is None or aqi_station["longitude"] is None:
        return None

    # 型別防呆:資料庫讀出來的 DECIMAL 可能是 Decimal 型別,先統一轉成 float 再計算
    aqi_lat = float(aqi_station["latitude"])
    aqi_lon = float(aqi_station["longitude"])

    nearest = None
    min_distance = float("inf")

    for rain_station in rain_stations:
        if rain_station["latitude"] is None or rain_station["longitude"] is None:
            continue  # 缺經緯度的雨量站,無法參與距離計算,跳過

        rain_lat = float(rain_station["latitude"])
        rain_lon = float(rain_station["longitude"])

        distance = haversine_distance(aqi_lat, aqi_lon, rain_lat, rain_lon)

        if distance < min_distance:
            min_distance = distance
            nearest = rain_station

    if nearest is None or min_distance > MAX_DISTANCE_KM:
        return None  # 沒有找到,或最近的也太遠,視為配對失敗

    return {"rain_site_id": nearest["site_id"], "distance_km": round(min_distance, 2)}


def upsert_mapping(cursor, aqi_site_id: str, rain_site_id: str, distance_km: float):
    cursor.execute(
        """
        INSERT INTO station_mapping (aqi_site_id, rain_site_id, distance_km)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            rain_site_id = VALUES(rain_site_id),
            distance_km = VALUES(distance_km)
        """,
        (aqi_site_id, rain_site_id, distance_km),
    )


def run():
    logger.info("開始計算地理關聯鍵...")
    conn = get_db_connection()
    cursor = conn.cursor()

    aqi_stations = fetch_stations(cursor, "stations")
    rain_stations = fetch_stations(cursor, "rain_stations")
    logger.info(f"讀取到 {len(aqi_stations)} 個空氣品質測站,{len(rain_stations)} 個雨量測站")

    matched_count = 0
    for aqi_station in aqi_stations:
        result = find_nearest_rain_station(aqi_station, rain_stations)
        if result is None:
            logger.warning(f"測站 {aqi_station['site_name']} 附近找不到合適的雨量站(超過{MAX_DISTANCE_KM}km)")
            continue
        upsert_mapping(cursor, aqi_station["site_id"], result["rain_site_id"], result["distance_km"])
        matched_count += 1

    conn.commit()
    cursor.close()
    conn.close()
    logger.info(f"完成,共配對 {matched_count}/{len(aqi_stations)} 個空氣品質測站")


if __name__ == "__main__":
    run()
