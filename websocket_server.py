import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

from pycrdt import Doc
from pycrdt_websocket import WebsocketServer, YRoom

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 데이터 디렉토리 설정
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


class FileBackedYRoom(YRoom):
    """파일 저장을 지원하는 YRoom"""
    
    def __init__(self, room_name: str):
        super().__init__(ready=False)
        self.room_name = room_name
        self.file_path = DATA_DIR / f"{room_name}.ys"
        self._task = None
        
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
        
        # 문서 변경 감지 설정
        self._task = asyncio.create_task(self._watch_changes())
        self.ready = True
        
    async def on_disconnect(self) -> None:
        """클라이언트 연결 해제 시 호출"""
        # 변경 감지 중지
        if self._task:
            self._task.cancel()
        
        # 문서 저장
        await self._save_document()
        
    async def _watch_changes(self):
        """문서 변경 감지 및 자동 저장"""
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
                logger.info(f"Saved room '{self.room_name}' to {self.file_path}")
        except Exception as e:
            logger.error(f"Error saving room '{self.room_name}': {e}")


class CRDTWebSocketServer(WebsocketServer):
    """파일 저장을 지원하는 WebSocket 서버"""
    
    def get_room(self, room_name: str) -> FileBackedYRoom:
        """room 인스턴스 생성 또는 반환"""
        if room_name not in self.rooms:
            self.rooms[room_name] = FileBackedYRoom(room_name)
        return self.rooms[room_name]


async def main():
    """WebSocket 서버 실행"""
    # Azure 환경 변수에서 포트 가져오기
    ws_port = int(os.environ.get('WEBSOCKET_PORT', 8765))
    
    server = CRDTWebSocketServer(
        auto_clean_rooms=False
    )
    
    logger.info(f"Starting CRDT WebSocket server on port {ws_port}...")
    
    try:
        await server.start_websocket_server(host="0.0.0.0", port=ws_port)
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        # 모든 room 저장
        for room_name, room in server.rooms.items():
            if hasattr(room, '_save_document'):
                await room._save_document()
    finally:
        logger.info("Server stopped.")


if __name__ == "__main__":
    asyncio.run(main())