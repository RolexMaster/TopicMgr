import asyncio
import logging
import os
import re  # ← 추가
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from pycrdt_websocket import WebsocketServer, YRoom
from contextlib import asynccontextmanager
from types import MethodType
from pycrdt_websocket import WebsocketServer, YRoom
from pycrdt_websocket.ystore import FileYStore, YDocNotFound


# 경로 설정
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# room 이름을 파일명으로 안전하게 변환
def safe_room_id(name: str) -> str:
    s = name.strip().lstrip('/')         # 선행 슬래시 제거
    s = s.replace('\\', '/').replace('/', '__')  # 경로 구분자는 __로
    s = re.sub(r'[^A-Za-z0-9._-]+', '_', s)     # 허용문자 외 _
    return s[:128] or 'room'

# 파일 저장형 YRoom
class FileBackedYRoom(YRoom):
    def __init__(self, room_name: str):
        super().__init__(ready=False)
        self.room_name = room_name
        self.file_path = DATA_DIR / f"{room_name}.ys"

    async def load_from_disk(self):
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
        try:
            update_data = self.ydoc.encode_state_as_update()
            with open(self.file_path, "wb") as f:
                f.write(update_data)
            logger.debug(f"Saved room '{self.room_name}' to disk")
            print(f"Saved room '{self.room_name}' to disk")

        except Exception as e:
            logger.error(f"Failed to save room {self.room_name}: {e}")

# WebSocket 서버
websocket_server = WebsocketServer(auto_clean_rooms=False)

# 파일 기반 get_room
async def _custom_get_room(self: WebsocketServer, name: str) -> YRoom:
    key = safe_room_id(name)  # 내부 키도 안전값으로 통일
    if key not in self.rooms:
        ystore = FileYStore(str(DATA_DIR / f"{key}.ystore"))
        room = YRoom(ready=True, ystore=ystore, log=logger)
        self.rooms[key] = room
        await self.start_room(room)
        logger.info(f"get_room: name='{name}' -> key='{key}' (persist {key}.ystore)")
    return self.rooms[key]

async def preload_rooms():
    """서버 부팅 시 data/*.ystore 전부 메모리로 복원"""
    count = 0
    for file in DATA_DIR.glob("*.ystore"):
        key = file.stem  # 이미 safe id
        ystore = FileYStore(str(file))
        room = YRoom(ready=False, ystore=ystore, log=logger)
        try:
            await ystore.apply_updates(room.ydoc)
            logger.info(f"[preload] restored room key='{key}' from {file.name}")
        except YDocNotFound:
            logger.info(f"[preload] no previous updates for key='{key}'")
        room.ready = True
        websocket_server.rooms[key] = room  # 내부 키는 safe와 일치
        await websocket_server.start_room(room)
        count += 1
    logger.info(f"[preload] loaded {count} room(s)")


websocket_server.get_room = MethodType(_custom_get_room, websocket_server)

# FastAPI 앱
# 교체 (복붙)
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with websocket_server:
        # 서버 부팅 시 한 번만 모든 방 프리로드
        await preload_rooms()
        yield
        # 종료 시 별도 저장 불필요(FileYStore가 변경마다 append 저장함)


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 기본 페이지
@app.get("/", response_class=HTMLResponse)
async def index():
    with open(STATIC_DIR / "client.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

# WebSocket 엔드포인트
# 교체 (복붙)
@app.websocket("/ws/{room_name:path}")
async def websocket_endpoint(websocket: WebSocket, room_name: str):
    await websocket.accept()

    class WSAdapter:
        def __init__(self, ws: WebSocket):
            self._ws = ws
            #self.path = ws.scope.get("path", f"/ws/{room_name}")
            # WebsocketServer는 path 전체를 room 식별자로 씁니다.
            # FastAPI 라우트 prefix(/ws)를 제거해 순수 room만 전달
            self.path = f"/{room_name}"


        async def send(self, data: bytes):
            await self._ws.send_bytes(data)

        async def recv(self) -> bytes:
            msg = await self._ws.receive()
            # y-websocket은 바이너리 사용. 텍스트면 UTF-8 변환
            if msg.get("bytes") is not None:
                return msg["bytes"]
            if msg.get("text") is not None:
                return msg["text"].encode("utf-8")
            raise WebSocketDisconnect

        async def close(self, code: int = 1000):
            await self._ws.close(code=code)

    try:
        await websocket_server.serve(WSAdapter(websocket))
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from room: {room_name}")
    except Exception:
        logger.exception(f"WebSocket error in room: {room_name}")


if __name__ == "__main__":
    uvicorn.run("crdtserver:app", host="0.0.0.0", port=8000, reload=False)
    #uvicorn.run("crdtserver:app", host="0.0.0.0", port=8000, reload=False, log_level="debug")

    
