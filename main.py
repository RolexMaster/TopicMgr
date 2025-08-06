import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from pycrdt_websocket import WebsocketServer

# 디렉토리 설정
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# FastAPI 앱 설정
app = FastAPI(title="Yjs + pycrdt-websocket 협업 시스템")

# 정적 파일 및 템플릿 설정
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# WebSocket 서버 인스턴스
websocket_server: Optional[WebsocketServer] = None


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
    </head>
    <body>
        <h1>Hello, World!</h1>
        <p><a href="/crdt">CRDT 협업 문서로 이동</a></p>
    </body>
    </html>
    """


@app.get("/crdt", response_class=HTMLResponse)
async def crdt_page(request: Request, room: Optional[str] = None):
    """CRDT 협업 문서 페이지"""
    return templates.TemplateResponse(
        "crdt.html",
        {
            "request": request,
            "room": room,
            "websocket_host": request.url.hostname,
            "websocket_port": 8765
        }
    )


async def start_websocket_server():
    """pycrdt-websocket 서버 시작"""
    global websocket_server
    
    # WebSocket 서버 설정
    websocket_server = WebsocketServer(
        auto_clean_rooms=False,  # room을 자동으로 정리하지 않음
        log_level="INFO"
    )
    
    # 파일 기반 저장소 설정
    async def on_shutdown():
        # 서버 종료 시 모든 문서 저장
        for room_name, room in websocket_server.rooms.items():
            file_path = DATA_DIR / f"{room_name}.ys"
            try:
                ydoc = room.ydoc
                if ydoc:
                    with open(file_path, "wb") as f:
                        f.write(ydoc.get_state())
                    print(f"Saved room '{room_name}' to {file_path}")
            except Exception as e:
                print(f"Error saving room '{room_name}': {e}")
    
    websocket_server.on_shutdown = on_shutdown
    
    # 기존 파일 로드
    for ys_file in DATA_DIR.glob("*.ys"):
        room_name = ys_file.stem
        try:
            # 파일에서 문서 로드는 클라이언트 연결 시 자동으로 처리됨
            print(f"Found saved room: {room_name}")
        except Exception as e:
            print(f"Error loading room '{room_name}': {e}")
    
    # WebSocket 서버 시작
    try:
        print("Starting WebSocket server on port 8765...")
        await websocket_server.start_websocket_server(host="0.0.0.0", port=8765)
    except Exception as e:
        print(f"WebSocket server error: {e}")
        raise


async def shutdown_handler():
    """종료 처리"""
    print("\nShutting down servers...")
    if websocket_server and hasattr(websocket_server, 'on_shutdown'):
        await websocket_server.on_shutdown()
    print("Servers stopped.")


def signal_handler(sig, frame):
    """시그널 핸들러"""
    print("\nReceived interrupt signal. Shutting down...")
    asyncio.create_task(shutdown_handler())
    sys.exit(0)


async def main():
    """메인 실행 함수"""
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # WebSocket 서버 시작
    websocket_task = asyncio.create_task(start_websocket_server())
    
    # FastAPI 서버 설정
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False
    )
    server = uvicorn.Server(config)
    
    # 두 서버 동시 실행
    try:
        print("Starting FastAPI server on port 8000...")
        await server.serve()
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        await shutdown_handler()
        websocket_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())