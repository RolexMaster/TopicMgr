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

#기본 설정

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

#로깅 설정

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#FastAPI 앱

app = FastAPI(title="Yjs + pycrdt-websocket 통합 서버")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

#YRoom 정의

class FileBackedYRoom(YRoom):
    def __init__(self, room_name: str):
        super().__init__(ready=False)
        self.room_name = room_name
        self.file_path = DATA_DIR / f"{room_name}.ys"
        self._save_task = None
        logger.info(f"Room created: {room_name}")

async def on_connect(self):
    if self.file_path.exists():
        try:
            with open(self.file_path, "rb") as f:
                state = f.read()
                if state:
                    self.ydoc.apply_update(state)
                    logger.info(f"Loaded {self.room_name} from disk")
        except Exception as e:
            logger.error(f"Failed to load room {self.room_name}: {e}")
    self._save_task = asyncio.create_task(self._auto_save())
    self.ready = True

async def on_disconnect(self):
    if self._save_task:
        self._save_task.cancel()
        try:
            await self._save_task
        except asyncio.CancelledError:
            pass
    await self._save_document()

async def _auto_save(self):
    while True:
        await asyncio.sleep(5)
        await self._save_document()

async def _save_document(self):
    try:
        state = self.ydoc.get_state()
        if state:
            with open(self.file_path, "wb") as f:
                f.write(state)
    except Exception as e:
        logger.error(f"Failed to save room {self.room_name}: {e}")

#서버 인스턴스
# 커스텀 WebsocketServer 정의
class CustomWebsocketServer(WebsocketServer):
    def get_room(self, room_name: str) -> YRoom:
        if room_name not in self.rooms:
            self.rooms[room_name] = FileBackedYRoom(room_name)
        return self.rooms[room_name]
    async def serve_websocket(self, websocket: WebSocket, path: str):
        # 1) WebSocket 연결 성립
        await websocket.accept()

        # 2) path로부터 방 이름(room_name) 추출
        room_name = path.lstrip("/")

        try:
            while True:
                # 3) 클라이언트 메시지 수신
                event = await websocket.receive()
                # 텍스트 메시지가 왔을 때만 사용
                if event["type"] == "websocket.receive" and "text" in event:
                    text = event["text"]
                    if text:  # 빈 문자열 필터
                        await websocket.send_text(f"[{room_name}] Echo: {text}")

                # 바이너리 메시지는 따로 필요하면 처리
                elif event["type"] == "websocket.receive" and "bytes" in event:
                    data = event["bytes"]
                    # 예: 바이너리 무시 또는 별도 로직
                    continue

                # 클라이언트 정상 종료
                elif event["type"] == "websocket.disconnect":
                    break

                # 4) 처리 로직 (방 이름을 이용한 컨텍스트 추가 가능)
                response = f"[{room_name}] Echo: {text}"

                # 5) 클라이언트로 응답
                await websocket.send_text(response)
        except WebSocketDisconnect:
            # 연결 종료 시 정리 작업
            print(f"WebSocket disconnected from {room_name}")

# 서버 인스턴스 생성
websocket_server = CustomWebsocketServer()

#FastAPI 라우트

@app.get("/", response_class=HTMLResponse)
@app.get("/index", response_class=HTMLResponse)
async def index():
    """단순 Hello World 페이지"""
    return """
    Hello
    """

@app.get("/crdt")
async def crdt_page(request: Request, room: Optional[str] = None):
    return templates.TemplateResponse("crdt.html", {
        "request": request,
        "room_name": room,
        "websocket_host": request.url.hostname or "localhost",
        "websocket_port": request.url.port or 8000
    })

@app.websocket("/ws/{room_name:path}")
async def websocket_endpoint(websocket: WebSocket, room_name: str):
    try:
        await websocket_server.serve_websocket(websocket, f"/{room_name}")
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from {room_name}")
    except Exception as e:
        logger.error(f"WebSocket error in {room_name}: {e}")

#메인 실행

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False, log_level="info")

