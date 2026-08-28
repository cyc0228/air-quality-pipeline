"""
診斷腳本:印出 API 回傳的原始內容與編碼資訊,
用來確認中文亂碼問題到底出在哪一層(API 本身、requests 解碼、還是資料庫寫入)。
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://data.moenv.gov.tw/api/v2/aqx_p_432"
API_KEY = os.getenv("MOENV_API_KEY")

params = {
    "api_key": API_KEY,
    "limit": 5,
    "format": "json",
}

resp = requests.get(API_URL, params=params, timeout=15)

print("=== HTTP Header 宣告的編碼 ===")
print("resp.encoding (requests猜測/宣告的編碼):", resp.encoding)
print("resp.apparent_encoding (根據內容猜測的編碼):", resp.apparent_encoding)
print("Content-Type header:", resp.headers.get("Content-Type"))
print()

print("=== 原始 bytes (前 500 bytes) ===")
print(resp.content[:500])
print()

print("=== 直接用 utf-8 解碼 resp.content 的結果 ===")
try:
    text_utf8 = resp.content.decode("utf-8")
    print(text_utf8[:1000])
except Exception as e:
    print(f"utf-8 解碼失敗: {e}")
print()

print("=== resp.json() 解析後,第一筆資料的完整內容 ===")
payload = resp.json()
records = payload if isinstance(payload, list) else payload.get("records", [])
if records:
    first = records[0]
    print(first)
    print()
    print("status 欄位的 repr():", repr(first.get("status")))
