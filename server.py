#!/usr/bin/env python3
"""
Yjs + pycrdt-websocket 통합 서버
FastAPI와 pycrdt-websocket을 하나의 프로세스에서 실행합니다.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from pycrdt import Doc
from pycrdt_websocket import WebsocketServer, YRoom

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 디렉토리 설정
# 기본 설정
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Azure App Service 환경 디버깅
print(f"Current working directory: {os.getcwd()}")
print(f"Script location: {__file__}")
print(f"BASE_DIR: {BASE_DIR}")
print(f"Directory contents: {list(BASE_DIR.glob('*'))}")

# static 디렉토리 생성
STATIC_DIR = BASE_DIR / "static"
try:
    STATIC_DIR.mkdir(exist_ok=True)
    print(f"✅ Static directory created/verified: {STATIC_DIR}")
except Exception as e:
    print(f"⚠️ Warning: Could not create static directory: {e}")
    # 대체 경로 시도
    STATIC_DIR = Path("/tmp/static")
    STATIC_DIR.mkdir(exist_ok=True)
    print(f"✅ Using alternative static directory: {STATIC_DIR}")

# FastAPI 앱 설정
app = FastAPI(title="Yjs + pycrdt-websocket 협업 시스템")

# 정적 파일 및 템플릿 설정
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    print(f"✅ Static files mounted from: {STATIC_DIR}")
else:
    print("⚠️ Warning: Static directory not found, skipping static file mounting")
    
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class FileBackedYRoom(YRoom):
    """파일 저장을 지원하는 YRoom"""
    
    def __init__(self, room_name: str):
        super().__init__(ready=False)
        self.room_name = room_name
        self.file_path = DATA_DIR / f"{room_name}.ys"
        self._save_task = None
        logger.info(f"Creating room: {room_name}")
        
    async def on_connect(self) -> None:
        """클라이언트 연결 시 호출"""
        # 기존 파일이 있으면 로드
        if self.file_path.exists():
            try:
                with open(self.file_path, "rb") as f:
                    state = f.read()
                    if state:
                        self.ydoc.apply_update(state)
                        logger.info(f"Loaded room '{self.room_name}' from {self.file_path}")
            except Exception as e:
                logger.error(f"Error loading room '{self.room_name}': {e}")
        
        # 자동 저장 시작
        self._save_task = asyncio.create_task(self._auto_save())
        self.ready = True
        
    async def on_disconnect(self) -> None:
        """클라이언트 연결 해제 시 호출"""
        # 자동 저장 중지
        if self._save_task:
            self._save_task.cancel()
            try:
                await self._save_task
            except asyncio.CancelledError:
                pass
        
        # 최종 저장
        await self._save_document()
        
    async def _auto_save(self):
        """주기적으로 문서 저장"""
        try:
            while True:
                await asyncio.sleep(5)  # 5초마다 저장
                await self._save_document()
        except asyncio.CancelledError:
            pass
            
    async def _save_document(self):
        """문서를 파일로 저장"""
        try:
            state = self.ydoc.get_state()
            if state:
                with open(self.file_path, "wb") as f:
                    f.write(state)
                logger.debug(f"Saved room '{self.room_name}' to {self.file_path}")
        except Exception as e:
            logger.error(f"Error saving room '{self.room_name}': {e}")


class CRDTWebSocketServer(WebsocketServer):
    """파일 저장을 지원하는 WebSocket 서버"""
    
    def get_room(self, room_name: str) -> FileBackedYRoom:
        """room 인스턴스 생성 또는 반환"""
        if room_name not in self.rooms:
            self.rooms[room_name] = FileBackedYRoom(room_name)
        return self.rooms[room_name]


# 전역 WebSocket 서버 인스턴스
websocket_server = CRDTWebSocketServer(
    auto_clean_rooms=False
)


@app.get("/", response_class=HTMLResponse)
@app.get("/index", response_class=HTMLResponse)
async def index():
    """단순 Hello World 페이지"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Hello World</title>
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
        <h1>Hello, World!</h1>
        <div class="link-container">
            <a href="/crdt">CRDT 협업 문서로 이동</a>
        </div>
    </body>
    </html>
    """


@app.get("/crdt", response_class=HTMLResponse)
async def crdt_page(request: Request, room: Optional[str] = None):
    """CRDT 협업 문서 페이지"""
    ws_port = int(os.environ.get('WEBSOCKET_PORT', 8765))
    return templates.TemplateResponse(
        "crdt.html",
        {
            "request": request,
            "room": room,
            "websocket_host": request.url.hostname or "localhost",
            "websocket_port": ws_port
        }
    )


async def start_servers():
    """서버들을 시작하는 메인 함수"""
    # Azure 환경 변수에서 포트 가져오기
    http_port = int(os.environ.get('PORT', 8000))
    ws_port = int(os.environ.get('WEBSOCKET_PORT', 8765))
    
    # WebSocket 서버 시작을 위한 핸들러
    async def websocket_handler(websocket, path):
        await websocket_server.serve(websocket)
    
    # 표준 websockets 라이브러리로 서버 시작
    import websockets
    websocket_server_instance = await websockets.serve(websocket_handler, "0.0.0.0", ws_port)
    
    # FastAPI 서버 설정
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=http_port,
        log_level="info",
        access_log=True
    )
    server = uvicorn.Server(config)
    
    # 시작 메시지
    print("\n" + "="*60)
    print("🚀 Yjs + pycrdt-websocket 협업 시스템 시작")
    print("="*60)
    print(f"📄 FastAPI 서버: http://localhost:{http_port}")
    print(f"🔌 WebSocket 서버: ws://localhost:{ws_port}")
    print(f"✏️  CRDT 편집기: http://localhost:{http_port}/crdt")
    print("="*60)
    print("종료하려면 Ctrl+C를 누르세요.\n")
    
    try:
        # FastAPI 서버 시작
        await server.serve()
    except KeyboardInterrupt:
        logger.info("Shutting down servers...")
    finally:
        # WebSocket 서버 정리
        websocket_task.cancel()
        try:
            await websocket_task
        except asyncio.CancelledError:
            pass
        
        # 모든 room 저장
        for room_name, room in websocket_server.rooms.items():
            if hasattr(room, '_save_document'):
                await room._save_document()
        
        logger.info("Servers stopped.")


if __name__ == "__main__":
    asyncio.run(start_servers())