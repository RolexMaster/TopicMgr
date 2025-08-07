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

# 기본 설정
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
DATA_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱
app = FastAPI(title="Yjs + pycrdt-websocket 통합 서버")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# YRoom 정의
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


# CRDT 서버 인스턴스
# 수정할 코드 1
websocket_server = WebsocketServer(rooms_factory=FileBackedYRoom, auto_clean_rooms=False)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # start()를 백그라운드 태스크로 실행
    bg_task = asyncio.create_task(websocket_server.start())
    # yield 이후에 클라이언트 요청을 받음
    yield
    # 앱 종료 시 서버 정리
    await websocket_server.close()
    # start() 태스크도 정리
    await bg_task

# FastAPI에 lifespan 파라미터 전달
app = FastAPI(lifespan=lifespan)

# FastAPI 라우트
@app.get("/", response_class=HTMLResponse)
@app.get("/index", response_class=HTMLResponse)
async def index():
    """메인 페이지"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>CRDT XML 협업 편집기</title>
        <meta charset="utf-8">
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            h1 {
                color: #333;
                text-align: center;
            }
            .description {
                text-align: center;
                color: #666;
                margin: 20px 0;
                line-height: 1.6;
            }
            .features {
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                margin: 30px 0;
            }
            .features h2 {
                color: #2c3e50;
                margin-bottom: 20px;
            }
            .features ul {
                list-style: none;
                padding: 0;
            }
            .features li {
                padding: 10px 0;
                padding-left: 30px;
                position: relative;
            }
            .features li:before {
                content: "✓";
                position: absolute;
                left: 0;
                color: #27ae60;
                font-weight: bold;
            }
            .link-container {
                text-align: center;
                margin-top: 30px;
            }
            a {
                display: inline-block;
                padding: 12px 24px;
                background-color: #3498db;
                color: white;
                text-decoration: none;
                border-radius: 6px;
                font-weight: 600;
                transition: background-color 0.3s;
            }
            a:hover {
                background-color: #2980b9;
            }
        </style>
    </head>
    <body>
        <h1>CRDT XML 협업 편집기</h1>
        <p class="description">
            Yjs와 pycrdt-websocket을 기반으로 한 실시간 XML 문서 협업 편집 시스템입니다.<br>
            여러 사용자가 동시에 XML 문서를 편집하고 실시간으로 동기화할 수 있습니다.
        </p>
        
        <div class="features">
            <h2>주요 기능</h2>
            <ul>
                <li>실시간 다중 사용자 XML 편집</li>
                <li>CRDT 기반 충돌 없는 동기화</li>
                <li>XML 구문 검증 및 포맷팅</li>
                <li>XML 파일 업로드/다운로드</li>
                <li>자동 저장 및 복구</li>
                <li>룸 기반 협업 공간</li>
            </ul>
        </div>
        
        <div class="link-container">
            <a href="/crdt">XML 편집기 시작하기</a>
        </div>
    </body>
    </html>
    """

@app.get("/crdt")
async def crdt_page(request: Request, room: Optional[str] = None):
    return templates.TemplateResponse("crdt.html", {
        "request": request,
        "room_name": room,
        "websocket_host": request.url.hostname or "localhost",
        "websocket_port": request.url.port or 8000
    })

# 수정할 코드 2
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


# 메인 실행
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False, log_level="info")
