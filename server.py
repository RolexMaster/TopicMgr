import asyncio
import logging
import os
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from pycrdt_websocket import WebsocketServer, YRoom
from contextlib import asynccontextmanager
from types import MethodType
from pycrdt_websocket.ystore import FileYStore

# ===== 기본 경로 설정 =====
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR_ENV = os.environ.get("DATA_DIR")
if DATA_DIR_ENV:
    DATA_DIR = Path(DATA_DIR_ENV)
elif os.environ.get("WEBSITE_INSTANCE_ID") or os.environ.get("WEBSITE_SITE_NAME"):
    DATA_DIR = Path("/home/data")
else:
    DATA_DIR = BASE_DIR / "data"

STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# ===== 로깅 =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== FastAPI =====
app = FastAPI(title="Yjs + pycrdt-websocket 통합 서버")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ===== 커스텀 YRoom (자동 저장/로드) =====
class FileBackedYRoom(YRoom):
    def __init__(self, room_name: str):
        super().__init__(ready=False)
        self.room_name = room_name
        self.file_path = DATA_DIR / f"{room_name}.ys"
        logger.info(f"Room created: {room_name}")

    async def load_from_disk(self):
        """저장된 CRDT 문서 로드"""
        if self.file_path.exists():
            try:
                with open(self.file_path, "rb") as f:
                    update_data = f.read()
                    if update_data:
                        self.ydoc.apply_update(update_data)
                        logger.info(f"Loaded room '{self.room_name}' from disk")
            except Exception as e:
                logger.error(f"Failed to load room {self.room_name}: {e}")

    async def save_to_disk(self):
        """CRDT 문서 저장"""
        try:
            update_data = self.ydoc.encode_state_as_update()
            with open(self.file_path, "wb") as f:
                f.write(update_data)
            logger.debug(f"Saved room '{self.room_name}' to disk ({len(update_data)} bytes)")
        except Exception as e:
            logger.error(f"Failed to save room {self.room_name}: {e}")

# ===== WebSocket 서버 인스턴스 =====
websocket_server = WebsocketServer(auto_clean_rooms=False)

# ===== 커스텀 get_room (파일 기반 로드) =====
async def _custom_get_room(self: WebsocketServer, name: str) -> YRoom:
    if name not in self.rooms:
        room = FileBackedYRoom(name)
        await room.load_from_disk()
        room.ready = True
        self.rooms[name] = room
        await self.start_room(room)
    return self.rooms[name]

websocket_server.get_room = MethodType(_custom_get_room, websocket_server)

# ===== FastAPI lifespan =====
@asynccontextmanager
async def lifespan(app: FastAPI):
    bg_task = asyncio.create_task(websocket_server.start())
    yield
    # 서버 종료 시 모든 룸 저장
    for room in websocket_server.rooms.values():
        if isinstance(room, FileBackedYRoom):
            await room.save_to_disk()
    await websocket_server.stop()
    await bg_task

# lifespan 적용
app = FastAPI(lifespan=lifespan)

# ===== 라우트 =====
@app.get("/", response_class=HTMLResponse)
async def index():
    return "<h1>Yjs + pycrdt-websocket 서버 실행 중</h1>"

@app.websocket("/ws/{room_name:path}")
async def websocket_endpoint(websocket: WebSocket, room_name: str):
    async def _send(data):
        await websocket.send_bytes(data)

    async def _recv():
        message = await websocket.receive()
        return message.get("bytes")

    websocket.send = _send
    websocket.recv = _recv
    websocket.path = websocket.scope["path"]

    try:
        await websocket_server.serve(websocket)
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from room: {room_name}")
    except Exception:
        logger.exception(f"WebSocket error in room: {room_name}")

# ===== 실행 =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False, log_level="info")
