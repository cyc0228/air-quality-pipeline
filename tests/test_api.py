import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from api import app

client = TestClient(app)


def test_read_root():
    """根路徑應該回傳服務正常運作的訊息。"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@patch("api.get_all_stations_with_mapping")
def test_read_stations(mock_get_stations):
    """測站清單端點應該正確組裝資料,並附上地理配對資訊。"""
    mock_get_stations.return_value = [
        ("1", "古亭", "臺北市", 25.02, 121.52, "C0A770", 2.5, "文山"),
        ("2", "士林", "臺北市", 25.10, 121.55, None, None, None),
    ]

    response = client.get("/stations")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert data["stations"][0]["site_id"] == "1"
    assert data["stations"][0]["nearest_rain_site_id"] == "C0A770"
    assert data["stations"][1]["nearest_rain_site_id"] is None


@patch("api.get_latest_rainfall")
@patch("api.get_mapped_rain_site")
@patch("api.get_latest_aqi")
def test_read_latest_with_rainfall(mock_get_aqi, mock_get_rain_site, mock_get_rainfall):
    """查詢最新AQI時,若測站有配對雨量站,應該一併附上雨量資料。"""
    mock_get_aqi.return_value = ("11", "2026-09-03 14:00:00", 26, "良好", 0, 3, 24, 0.17, 1.1, 8)
    mock_get_rain_site.return_value = "C0A770"
    mock_get_rainfall.return_value = ("C0A770", "2026-09-03 06:20:00", 3.0)

    response = client.get("/stations/11/latest")

    assert response.status_code == 200
    data = response.json()
    assert data["aqi"] == 26
    assert data["rainfall"]["precipitation"] == 3.0


@patch("api.get_latest_aqi")
def test_read_latest_not_found(mock_get_aqi):
    """查詢不存在的測站,應該回傳404,而不是空白或錯誤的成功訊息。"""
    mock_get_aqi.return_value = None

    response = client.get("/stations/不存在的測站/latest")

    assert response.status_code == 404


@patch("api.get_aqi_history")
def test_read_history_valid_range(mock_get_history):
    """查詢歷史趨勢,時間格式正確時應該正常回傳。"""
    mock_get_history.return_value = [
        ("11", "2026-09-03 10:00:00", 26, "良好", 0, 3),
        ("11", "2026-09-03 11:00:00", 28, "良好", 1, 4),
    ]

    response = client.get(
        "/stations/11/history",
        params={"start": "2026-09-03 00:00:00", "end": "2026-09-03 23:59:59"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2


def test_read_history_invalid_date_format():
    """時間格式錯誤時,應該回傳400,而不是讓資料庫查詢直接失敗。"""
    response = client.get(
        "/stations/11/history",
        params={"start": "不是時間格式", "end": "2026-09-03 23:59:59"},
    )

    assert response.status_code == 400


@patch("api.get_data_quality_issues")
def test_read_data_quality_issues(mock_get_issues):
    """資料品質異常紀錄端點應該正確回傳清單。"""
    mock_get_issues.return_value = [
        (1, "aqi", "11", "aqi", "negative_value", "-10", "2026-09-03 12:00:00"),
    ]

    response = client.get("/data-quality-issues")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["issues"][0]["issue_type"] == "negative_value"
