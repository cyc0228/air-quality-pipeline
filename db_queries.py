"""
FastAPI 查詢層專用的資料庫存取邏輯。

跟 fetch_aqi.py 等抓取腳本不同,這裡只做「讀取」,不寫入資料庫。
"""

import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


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


def get_all_stations_with_mapping():
    """查詢所有AQI測站,並附上最近的雨量站與距離(若有配對成功)。"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            s.site_id, s.site_name, s.county, s.latitude, s.longitude,
            m.rain_site_id, m.distance_km, rs.site_name
        FROM stations s
        LEFT JOIN station_mapping m ON s.site_id = m.aqi_site_id
        LEFT JOIN rain_stations rs ON m.rain_site_id = rs.site_id
        """
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_latest_aqi(site_id: str):
    """查詢某AQI測站最新一筆資料。"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT site_id, publish_time, aqi, status, pm2_5, pm10, o3, co, so2, no2
        FROM aqi_records
        WHERE site_id = %s
        ORDER BY publish_time DESC
        LIMIT 1
        """,
        (site_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def get_mapped_rain_site(site_id: str):
    """查詢某AQI測站配對到的雨量站ID(若無配對則回傳None)。"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT rain_site_id FROM station_mapping WHERE aqi_site_id = %s",
        (site_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row[0] if row else None


def get_latest_rainfall(rain_site_id: str):
    """查詢某雨量站最新一筆資料。"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT site_id, obs_time, precipitation
        FROM rainfall_records
        WHERE site_id = %s
        ORDER BY obs_time DESC
        LIMIT 1
        """,
        (rain_site_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def get_aqi_history(site_id: str, start: str, end: str):
    """查詢某AQI測站在指定時間區間內的歷史資料。"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT site_id, publish_time, aqi, status, pm2_5, pm10
        FROM aqi_records
        WHERE site_id = %s AND publish_time BETWEEN %s AND %s
        ORDER BY publish_time ASC
        """,
        (site_id, start, end),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def get_data_quality_issues(data_source: str = None, limit: int = 100):
    """查詢資料品質異常紀錄,可選擇依data_source篩選('aqi'或'rainfall')。"""
    conn = get_db_connection()
    cursor = conn.cursor()
    if data_source:
        cursor.execute(
            """
            SELECT id, data_source, site_id, field_name, issue_type, raw_value, detected_at
            FROM data_quality_issues
            WHERE data_source = %s
            ORDER BY detected_at DESC
            LIMIT %s
            """,
            (data_source, limit),
        )
    else:
        cursor.execute(
            """
            SELECT id, data_source, site_id, field_name, issue_type, raw_value, detected_at
            FROM data_quality_issues
            ORDER BY detected_at DESC
            LIMIT %s
            """,
            (limit,),
        )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows
