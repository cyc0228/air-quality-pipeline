import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fetch_aqi import clean_record, fetch_raw_data


def test_clean_record_normal():
    """正常資料應該被正確轉型。"""
    raw = {
        "siteid": "1", "sitename": "古亭", "county": "臺北市",
        "latitude": "25.02", "longitude": "121.52",
        "publishtime": "2026-09-01 10:00",
        "aqi": "35", "status": "良好",
        "pm2.5": "12.5", "pm10": "20", "o3": "30", "co": "0.5", "so2": "1.2", "no2": "5.5",
    }
    result = clean_record(raw)
    assert result["site_id"] == "1"
    assert result["aqi"] == 35
    assert result["pm2_5"] == 12.5
    assert result["latitude"] == 25.02


def test_clean_record_missing_fields():
    """缺值(空字串/None)應該被轉成 None,不能噴例外。"""
    raw = {"siteid": "1", "aqi": "", "pm2.5": None, "latitude": ""}
    result = clean_record(raw)
    assert result["aqi"] is None
    assert result["pm2_5"] is None
    assert result["latitude"] is None


def test_clean_record_garbage_value():
    """格式錯誤的字串(非數字)應該被轉成 None,不能噴例外。"""
    raw = {"siteid": "1", "aqi": "N/A", "latitude": "abc"}
    result = clean_record(raw)
    assert result["aqi"] is None
    assert result["latitude"] is None


def test_clean_record_empty_dict():
    """完全空的輸入,所有欄位都應該安全地回傳 None。"""
    result = clean_record({})
    assert result["site_id"] is None
    assert result["aqi"] is None
    assert result["pm2_5"] is None


@patch("fetch_aqi.requests.get")
def test_fetch_raw_data_filters_taipei(mock_get):
    """API 回傳多縣市資料時,應該只篩選出臺北市的部分。"""
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"county": "臺北市", "siteid": "1"},
        {"county": "新北市", "siteid": "2"},
        {"county": "臺北市", "siteid": "3"},
    ]
    mock_get.return_value = mock_response

    result = fetch_raw_data()

    assert len(result) == 2
    assert all(r["county"] == "臺北市" for r in result)


@patch("fetch_aqi.requests.get")
def test_fetch_raw_data_handles_array_format(mock_get):
    """API 直接回傳陣列格式時,應該正確處理。"""
    mock_response = MagicMock()
    mock_response.json.return_value = [{"county": "臺北市", "siteid": "1"}]
    mock_get.return_value = mock_response

    result = fetch_raw_data()

    assert len(result) == 1
    assert result[0]["siteid"] == "1"


@patch("fetch_aqi.requests.get")
def test_fetch_raw_data_handles_wrapped_format(mock_get):
    """API 回傳 {"records": [...]} 包裝格式時,應該正確處理。"""
    mock_response = MagicMock()
    mock_response.json.return_value = {"records": [{"county": "臺北市", "siteid": "1"}]}
    mock_get.return_value = mock_response

    result = fetch_raw_data()

    assert len(result) == 1
    assert result[0]["siteid"] == "1"


@patch("fetch_aqi.requests.get")
def test_fetch_raw_data_no_taipei_results(mock_get):
    """篩選後若沒有任何臺北市資料,應該回傳空清單,不噴例外。"""
    mock_response = MagicMock()
    mock_response.json.return_value = [{"county": "新北市", "siteid": "2"}]
    mock_get.return_value = mock_response

    result = fetch_raw_data()

    assert result == []
