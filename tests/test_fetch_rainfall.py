import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fetch_rainfall import clean_record, fetch_raw_data


def test_clean_record_normal():
    """正常資料(含 WGS84 座標)應該被正確攤平與轉型。"""
    raw = {
        "StationId": "A1", "StationName": "測站A",
        "GeoInfo": {"CountyName": "臺北市", "Coordinates": [
            {"CoordinateName": "WGS84", "StationLatitude": "25.0", "StationLongitude": "121.5"}
        ]},
        "ObsTime": {"DateTime": "2026-09-01T10:00:00+08:00"},
        "RainfallElement": {"Past1hr": {"Precipitation": "5.5"}}
    }
    result = clean_record(raw)
    assert result["site_id"] == "A1"
    assert result["latitude"] == 25.0
    assert result["longitude"] == 121.5
    assert result["precipitation"] == 5.5


def test_clean_record_missing_wgs84():
    """座標清單裡沒有 WGS84 這組座標時,經緯度應該回傳 None,不能噴例外。"""
    raw = {
        "StationId": "A1", "StationName": "測站A",
        "GeoInfo": {"CountyName": "臺北市", "Coordinates": [
            {"CoordinateName": "TWD97", "StationLatitude": "25.0", "StationLongitude": "121.5"}
        ]},
        "ObsTime": {"DateTime": "2026-09-01T10:00:00+08:00"},
        "RainfallElement": {"Past1hr": {"Precipitation": "5.5"}}
    }
    result = clean_record(raw)
    assert result["latitude"] is None
    assert result["longitude"] is None


def test_clean_record_nested_missing_keys():
    """巢狀結構中若整個層級都缺失(如 RainfallElement 不存在),不應該噴例外。"""
    raw = {"StationId": "A1", "GeoInfo": {}}
    result = clean_record(raw)
    assert result["precipitation"] is None
    assert result["latitude"] is None
    assert result["longitude"] is None


@patch("fetch_rainfall.requests.get")
def test_fetch_raw_data_filters_taipei(mock_get):
    """API 回傳多縣市測站資料時,應該只篩選出臺北市的部分。"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "records": {
            "Station": [
                {"StationId": "1", "GeoInfo": {"CountyName": "臺北市"}},
                {"StationId": "2", "GeoInfo": {"CountyName": "新北市"}},
                {"StationId": "3", "GeoInfo": {"CountyName": "臺北市"}},
            ]
        }
    }
    mock_get.return_value = mock_response

    result = fetch_raw_data()

    assert len(result) == 2
    assert all(r["GeoInfo"]["CountyName"] == "臺北市" for r in result)


@patch("fetch_rainfall.requests.get")
def test_fetch_raw_data_missing_records_key(mock_get):
    """API 回傳結構若缺少 records 或 Station 這一層,應該回傳空清單,不噴例外。"""
    mock_response = MagicMock()
    mock_response.json.return_value = {"records": {}}
    mock_get.return_value = mock_response

    result = fetch_raw_data()

    assert result == []


@patch("fetch_rainfall.requests.get")
def test_fetch_raw_data_no_taipei_results(mock_get):
    """篩選後若沒有任何臺北市測站,應該回傳空清單,不噴例外。"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "records": {"Station": [{"StationId": "2", "GeoInfo": {"CountyName": "新北市"}}]}
    }
    mock_get.return_value = mock_response

    result = fetch_raw_data()

    assert result == []
