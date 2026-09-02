"""
診斷腳本:呼叫中央氣象署雨量觀測站 API,
確認實際回傳的資料長相(欄位名稱、巢狀結構),做為正式抓取程式的依據。
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0002-001"
CWA_API_KEY = os.getenv("CWA_API_KEY")

params = {
    "Authorization": CWA_API_KEY,
    "format": "JSON",
    "limit": 5,  # 先只拿5筆看格式,確認沒問題後再拿全部
    "RainfallElement": "Past1hr",  # 對齊空氣品質「每小時」的時間顆粒度
}

resp = requests.get(API_URL, params=params, timeout=15)
resp.raise_for_status()
resp.encoding = "utf-8"
payload = resp.json()

print("=== 回傳的最外層結構,有哪些鍵 ===")
print(payload.keys() if isinstance(payload, dict) else "回傳的是list,不是dict")
print()

print("=== 完整內容(前一小部分) ===")
import json
print(json.dumps(payload, ensure_ascii=False, indent=2)[:3000])
