from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from db_queries import (
    get_all_stations_with_mapping,
    get_latest_aqi,
    get_mapped_rain_site,
    get_latest_rainfall,
    get_aqi_history,
    get_data_quality_issues,
)

app = FastAPI()


@app.get("/")
def read_root():
    return {"status": "ok", "message": "空氣品質資料查詢 API 運作中"}


@app.get("/stations")
def read_stations():
    """查詢所有AQI測站清單,並附上最近的雨量站與距離。"""
    rows = get_all_stations_with_mapping()
    stations = []
    for row in rows:
        stations.append({
            "site_id": row[0],
            "site_name": row[1],
            "county": row[2],
            "latitude": float(row[3]) if row[3] is not None else None,
            "longitude": float(row[4]) if row[4] is not None else None,
            "nearest_rain_site_id": row[5],
            "distance_km": float(row[6]) if row[6] is not None else None,
            "nearest_rain_site_name": row[7],
        })
    return {"count": len(stations), "stations": stations}


@app.get("/stations/{site_id}/latest")
def read_latest(site_id: str):
    """查詢某測站最新的AQI資料,若有配對成功的雨量站,一併附上其最新雨量資料。"""
    aqi_row = get_latest_aqi(site_id)
    if aqi_row is None:
        raise HTTPException(status_code=404, detail=f"找不到測站 {site_id} 的AQI資料")

    result = {
        "site_id": aqi_row[0],
        "publish_time": aqi_row[1],
        "aqi": aqi_row[2],
        "status": aqi_row[3],
        "pm2_5": float(aqi_row[4]) if aqi_row[4] is not None else None,
        "pm10": float(aqi_row[5]) if aqi_row[5] is not None else None,
        "o3": float(aqi_row[6]) if aqi_row[6] is not None else None,
        "co": float(aqi_row[7]) if aqi_row[7] is not None else None,
        "so2": float(aqi_row[8]) if aqi_row[8] is not None else None,
        "no2": float(aqi_row[9]) if aqi_row[9] is not None else None,
        "rainfall": None,
    }

    rain_site_id = get_mapped_rain_site(site_id)
    if rain_site_id:
        rain_row = get_latest_rainfall(rain_site_id)
        if rain_row:
            result["rainfall"] = {
                "site_id": rain_row[0],
                "obs_time": rain_row[1],
                "precipitation": float(rain_row[2]) if rain_row[2] is not None else None,
            }

    return result


@app.get("/stations/{site_id}/history")
def read_history(
    site_id: str,
    start: str = Query(..., description="開始時間,格式 YYYY-MM-DD HH:MM:SS"),
    end: str = Query(..., description="結束時間,格式 YYYY-MM-DD HH:MM:SS"),
):
    """查詢某測站在指定時間區間內的AQI歷史資料。"""
    try:
        datetime.fromisoformat(start)
        datetime.fromisoformat(end)
    except ValueError:
        raise HTTPException(status_code=400, detail="時間格式錯誤,請使用 YYYY-MM-DD HH:MM:SS")

    rows = get_aqi_history(site_id, start, end)
    history = []
    for row in rows:
        history.append({
            "site_id": row[0],
            "publish_time": row[1],
            "aqi": row[2],
            "status": row[3],
            "pm2_5": float(row[4]) if row[4] is not None else None,
            "pm10": float(row[5]) if row[5] is not None else None,
        })
    return {"count": len(history), "history": history}


@app.get("/data-quality-issues")
def read_data_quality_issues(
    data_source: str = Query(None, description="篩選來源:'aqi' 或 'rainfall',不填則回傳全部"),
    limit: int = 100,
):
    """查詢資料品質異常紀錄。"""
    rows = get_data_quality_issues(data_source, limit)
    issues = []
    for row in rows:
        issues.append({
            "id": row[0],
            "data_source": row[1],
            "site_id": row[2],
            "field_name": row[3],
            "issue_type": row[4],
            "raw_value": row[5],
            "detected_at": row[6],
        })
    return {"count": len(issues), "issues": issues}
