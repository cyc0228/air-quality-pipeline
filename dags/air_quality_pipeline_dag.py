"""
空氣品質資料管線 DAG

依賴關係:
    fetch_aqi 跟 fetch_rainfall 互相獨立,可以同時執行
    build_station_mapping 跟 data_quality_check 都必須等前兩者完成後才能開始
    (build_station_mapping 需要讀取兩邊的測站清單才能計算地理關聯鍵;
     data_quality_check 需要讀取兩邊剛寫入的資料才能檢查數值是否異常)
    build_station_mapping 跟 data_quality_check 彼此獨立,互不依賴,可以同時執行

排程:每小時的第5分執行,對齊原本 scheduler.py 的排程邏輯
"""

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_DIR = "/opt/airflow/project"

# Docker Desktop提供的特殊網址,讓容器內部能連回"你的電腦本身"
# 這樣不用修改fetch_aqi.py等程式碼裡的任何一行,就能讓它們在容器裡也連得到MySQL
MYSQL_HOST_OVERRIDE = "host.docker.internal"


with DAG(
    dag_id="air_quality_pipeline",
    description="空氣品質+雨量資料抓取,計算地理關聯鍵,並檢查資料品質",
    start_date=datetime(2026, 8, 1),
    schedule="5 * * * *",   # cron表達式:每小時的第5分鐘
    catchup=False,           # 不要把過去錯過的時間點,一次全部補跑
    tags=["air_quality"],
) as dag:

    fetch_aqi = BashOperator(
        task_id="fetch_aqi",
        bash_command=f"cd {PROJECT_DIR} && MYSQL_HOST={MYSQL_HOST_OVERRIDE} python fetch_aqi.py",
    )

    fetch_rainfall = BashOperator(
        task_id="fetch_rainfall",
        bash_command=f"cd {PROJECT_DIR} && MYSQL_HOST={MYSQL_HOST_OVERRIDE} python fetch_rainfall.py",
    )

    build_station_mapping = BashOperator(
        task_id="build_station_mapping",
        bash_command=f"cd {PROJECT_DIR} && MYSQL_HOST={MYSQL_HOST_OVERRIDE} python build_station_mapping.py",
    )

    data_quality_check = BashOperator(
        task_id="data_quality_check",
        bash_command=f"cd {PROJECT_DIR} && MYSQL_HOST={MYSQL_HOST_OVERRIDE} python data_quality_check.py",
    )

    # 依賴關係:fetch_aqi、fetch_rainfall 都完成後,才能開始 build_station_mapping 和 data_quality_check
    # 這兩者互相獨立,會平行執行
    [fetch_aqi, fetch_rainfall] >> build_station_mapping
    [fetch_aqi, fetch_rainfall] >> data_quality_check
