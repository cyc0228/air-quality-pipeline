import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_quality_check import check_aqi_value, check_rainfall_value


def test_check_aqi_value_normal():
    """正常範圍內的 AQI 整數,不應該被判定為異常。"""
    assert check_aqi_value(35) is None
    assert check_aqi_value(0) is None
    assert check_aqi_value(500) is None  # 剛好等於上限,不算超過


def test_check_aqi_value_none():
    """None 代表缺值,已經在清洗階段處理過,這裡不重複判定為異常。"""
    assert check_aqi_value(None) is None


def test_check_aqi_value_negative():
    """負數 AQI 在定義上不可能存在,應該被判定為異常。"""
    assert check_aqi_value(-10) == "negative_value"


def test_check_aqi_value_exceeds_max():
    """超過官方定義上限(500)的 AQI,應該被判定為異常。"""
    assert check_aqi_value(501) == "exceeds_max"
    assert check_aqi_value(9999) == "exceeds_max"


def test_check_aqi_value_not_integer():
    """AQI 本身應為整數,若為浮點數代表格式跑掉,應該被判定為異常。"""
    assert check_aqi_value(35.5) == "not_integer"


def test_check_rainfall_value_normal():
    """正常範圍內的雨量,不應該被判定為異常。"""
    assert check_rainfall_value(0.0) is None
    assert check_rainfall_value(5.5) is None
    assert check_rainfall_value(200.0) is None  # 剛好等於上限,不算超過


def test_check_rainfall_value_none():
    """None 代表缺值,已經在清洗階段處理過,這裡不重複判定為異常。"""
    assert check_rainfall_value(None) is None


def test_check_rainfall_value_negative():
    """負數雨量在物理上不可能存在,應該被判定為異常。"""
    assert check_rainfall_value(-5.0) == "negative_value"


def test_check_rainfall_value_exceeds_max():
    """超過保底異常門檻(200mm)的雨量,應該被判定為異常。"""
    assert check_rainfall_value(500.0) == "exceeds_max"
