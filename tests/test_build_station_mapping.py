import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from build_station_mapping import haversine_distance, find_nearest_rain_station


def test_haversine_distance_same_point():
    """同一個點的距離應該是 0。"""
    d = haversine_distance(25.0, 121.5, 25.0, 121.5)
    assert d == 0


def test_haversine_distance_known_value():
    """用兩個已知座標驗證距離計算大致正確(允許誤差範圍)。"""
    # 台北市政府 vs 台北車站,實際距離約 4.8 公里
    d = haversine_distance(25.0375, 121.5637, 25.0478, 121.5170)
    assert 4.0 < d < 5.5


def test_find_nearest_rain_station_normal():
    """應該正確找出最近的雨量站。"""
    aqi_station = {"latitude": 25.0, "longitude": 121.5}
    rain_stations = [
        {"site_id": "近", "latitude": 25.001, "longitude": 121.501},
        {"site_id": "遠", "latitude": 25.5, "longitude": 122.0},
    ]
    result = find_nearest_rain_station(aqi_station, rain_stations)
    assert result["rain_site_id"] == "近"


def test_find_nearest_rain_station_too_far():
    """所有雨量站都超過門檻距離時,應該回傳 None。"""
    aqi_station = {"latitude": 25.0, "longitude": 121.5}
    rain_stations = [{"site_id": "遠", "latitude": 30.0, "longitude": 125.0}]
    result = find_nearest_rain_station(aqi_station, rain_stations)
    assert result is None


def test_find_nearest_rain_station_skips_missing_coords():
    """雨量站清單中缺經緯度的測站應該被跳過,不影響配對結果。"""
    aqi_station = {"latitude": 25.0, "longitude": 121.5}
    rain_stations = [
        {"site_id": "缺座標", "latitude": None, "longitude": None},
        {"site_id": "正常", "latitude": 25.001, "longitude": 121.501},
    ]
    result = find_nearest_rain_station(aqi_station, rain_stations)
    assert result["rain_site_id"] == "正常"


def test_find_nearest_rain_station_empty_list():
    """雨量站清單是空的時候,應該回傳 None,不能噴例外。"""
    aqi_station = {"latitude": 25.0, "longitude": 121.5}
    result = find_nearest_rain_station(aqi_station, [])
    assert result is None


def test_find_nearest_rain_station_missing_aqi_coords():
    """空氣品質測站缺經緯度時,應該安全回傳 None,不噴例外(修 bug 後的驗證)。"""
    aqi_station = {"site_id": "1", "site_name": "測站A", "latitude": None, "longitude": None}
    rain_stations = [{"site_id": "R1", "latitude": 25.0, "longitude": 121.5}]
    result = find_nearest_rain_station(aqi_station, rain_stations)
    assert result is None
