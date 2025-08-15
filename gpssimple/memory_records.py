from threading import RLock
from datetime import datetime
import os

_records = []           # [{...}, ...] 최근 것이 뒤에 append
_lock = RLock()
MAX_RECORDS = int(os.getenv("GPS_MAX_RECORDS", "0"))  # 0=무제한

def _f(v):
    try: return float(v)
    except: return None

def ingest(payload: dict) -> bool:
    """id/lat/lon 필수. 들어오면 records 에 그대로 append."""
    did = payload.get("id") or payload.get("deviceId") or payload.get("device")
    lat = _f(payload.get("lat") or payload.get("latitude"))
    lon = _f(payload.get("lon") or payload.get("lng") or payload.get("longitude"))
    if not did or lat is None or lon is None:
        return False
    item = {
        "device_id": did,
        "lat": lat, "lon": lon,
        "speed": _f(payload.get("speed") or payload.get("spd")),
        "accuracy": _f(payload.get("accuracy") or payload.get("acc")),
        "battery": _f(payload.get("battery") or payload.get("batt") or payload.get("battery_level")),
        "course": _f(payload.get("course") or payload.get("bearing") or payload.get("heading")),
        "altitude": _f(payload.get("alt") or payload.get("altitude")),
        "timestamp": payload.get("timestamp") or payload.get("time"),
        "received_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    with _lock:
        _records.append(item)
        if MAX_RECORDS > 0 and len(_records) > MAX_RECORDS:
            del _records[:-MAX_RECORDS]  # 오래된 것부터 정리
    return True

def list_latest(limit: int = 100) -> list[dict]:
    """최신순으로 최대 limit개 반환"""
    if limit <= 0: limit = 100
    with _lock:
        return list(reversed(_records[-limit:]))
