# gpssimple/fastapi_gps_router.py
import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse
from .memory_records import add, latest, recent

router = APIRouter()

async def _collect(request: Request) -> dict:
    d = dict(request.query_params)
    ct = request.headers.get("content-type", "")
    if ct.startswith("application/json"):
        body = await request.json()
        if isinstance(body, dict): d.update(body)
    elif request.method == "POST":
        form = await request.form()
        d.update(dict(form))
    return d

@router.api_route("/ingest", methods=["GET", "POST"])
async def ingest(request: Request):
    if not add(await _collect(request)):
        raise HTTPException(400, "missing id/lat/lon")
    return PlainTextResponse("OK")

@router.get("/latest")
async def latest_api():
    it = latest()
    return JSONResponse(it or {"error": "no data"}, status_code=200 if it else 404)

@router.get("/recent")
async def recent_api(limit: int = 100):
    return JSONResponse(recent(limit))

@router.get("/view", include_in_schema=False)
async def view_page():
    """분리된 HTML 파일을 반환합니다."""
    html_path = os.path.join(os.path.dirname(__file__), "templates", "gps_view.html")
    return FileResponse(html_path, media_type="text/html")
