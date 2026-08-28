"""
V1.0 排程器:每小時執行一次 fetch_aqi.run()。
之後升級到多資料源整合時,這支會被 Airflow DAG 取代。
"""

import time
import schedule

from fetch_aqi import run

def job():
    try:
        run()
    except Exception as e:
        print(f"[ERROR] 抓取失敗: {e}")


if __name__ == "__main__":
    job()  # 啟動時先跑一次
    schedule.every().hour.at(":05").do(job)  # 之後每小時的第 5 分執行

    while True:
        schedule.run_pending()
        time.sleep(30)
