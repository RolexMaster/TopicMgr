from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from .memory_records import ingest, list_latest

router = APIRouter()

async def _collect(request: Request) -> dict:
    d = dict(request.query_params)
    if request.headers.get("content-type","").startswith("application/json"):
        body = await request.json()
        if isinstance(body, dict): d.update(body)
    elif request.method == "POST":
        form = await request.form()
        d.update(dict(form))
    return d

@router.api_route("/ingest", methods=["GET","POST"])
async def api_ingest(request: Request):
    if not ingest(await _collect(request)):
        raise HTTPException(400, "missing id/lat/lon")
    return PlainTextResponse("OK")

@router.get("/data")
async def api_data(limit: int = 100):
    return JSONResponse(list_latest(limit))
