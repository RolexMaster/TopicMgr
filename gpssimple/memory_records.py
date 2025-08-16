# gpssimple/memory_records.py
from threading import RLock
from datetime import datetime

_records: list[dict] = []   # 서버 재시작 시 초기화
_lock = RLock()

def _f(v):
    try: return float(v)
    except: return None

def add(payload: dict) -> bool:
    """필수: id, lat, lon"""
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
    return True

def latest() -> dict | None:
    with _lock:
        return _records[-1] if _records else None

def recent(limit: int = 100) -> list[dict]:
    if limit <= 0: limit = 100
    with _lock:
        return list(reversed(_records[-limit:]))  # 최신순
