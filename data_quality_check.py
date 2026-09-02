"""
V3.0:資料品質監控機制。

目的:檢查 aqi_records、rainfall_records 裡的數值,是否違反該指標「定義上不可能」的規則
(例如負數、超過理論上限),而非篩選統計上的離群值(離群值可能是真實的極端天氣,不應被當成錯誤)。

檢查規則:
- AQI:負數 -> 異常;超過 500(官方定義最高等級)-> 異常;非整數 -> 異常
- 雨量:負數 -> 異常;超過 200mm(遠超台灣史上單筆極端紀錄,視為保底異常值)-> 異常

偵測到異常時,寫入 data_quality_issues 表留存紀錄,不修改原始資料。
"""

import os
import logging

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

AQI_MAX = 500
RAINFALL_MAX = 200.0


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


def check_aqi_value(value) -> str | None:
    """檢查單一 AQI 數值,回傳異常類型代碼;沒有異常則回傳 None。"""
    if value is None:
        return None  # 缺值已經在清洗階段處理過,這裡不重複判定

    if not isinstance(value, int):
        return "not_integer"

    if value < 0:
        return "negative_value"

    if value > AQI_MAX:
        return "exceeds_max"

    return None


def check_rainfall_value(value) -> str | None:
    """檢查單一雨量數值,回傳異常類型代碼;沒有異常則回傳 None。"""
    if value is None:
        return None

    if value < 0:
        return "negative_value"

    if value > RAINFALL_MAX:
        return "exceeds_max"

    return None


def fetch_recent_aqi_records(cursor, limit: int = 500) -> list[dict]:
    """讀取最近寫入的 AQI 資料,做為本次檢查的範圍。"""
    cursor.execute(
        "SELECT site_id, aqi FROM aqi_records ORDER BY fetched_at DESC LIMIT %s",
        (limit,),
    )
    return [{"site_id": row[0], "aqi": row[1]} for row in cursor.fetchall()]


def fetch_recent_rainfall_records(cursor, limit: int = 500) -> list[dict]:
    """讀取最近寫入的雨量資料,做為本次檢查的範圍。"""
    cursor.execute(
        "SELECT site_id, precipitation FROM rainfall_records ORDER BY fetched_at DESC LIMIT %s",
        (limit,),
    )
    return [{"site_id": row[0], "precipitation": row[1]} for row in cursor.fetchall()]


def log_issue(cursor, data_source: str, site_id: str, field_name: str, issue_type: str, raw_value):
    cursor.execute(
        """
        INSERT INTO data_quality_issues (data_source, site_id, field_name, issue_type, raw_value)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (data_source, site_id, field_name, issue_type, str(raw_value)),
    )


def run():
    logger.info("開始執行資料品質檢查...")
    conn = get_db_connection()
    cursor = conn.cursor()

    issue_count = 0

    aqi_records = fetch_recent_aqi_records(cursor)
    for record in aqi_records:
        issue_type = check_aqi_value(record["aqi"])
        if issue_type:
            logger.warning(f"AQI異常:測站{record['site_id']},數值{record['aqi']},類型{issue_type}")
            log_issue(cursor, "aqi", record["site_id"], "aqi", issue_type, record["aqi"])
            issue_count += 1

    rainfall_records = fetch_recent_rainfall_records(cursor)
    for record in rainfall_records:
        issue_type = check_rainfall_value(record["precipitation"])
        if issue_type:
            logger.warning(f"雨量異常:測站{record['site_id']},數值{record['precipitation']},類型{issue_type}")
            log_issue(cursor, "rainfall", record["site_id"], "precipitation", issue_type, record["precipitation"])
            issue_count += 1

    conn.commit()
    cursor.close()
    conn.close()
    logger.info(f"完成,共檢查 {len(aqi_records) + len(rainfall_records)} 筆資料,發現 {issue_count} 筆異常")


if __name__ == "__main__":
    run()
