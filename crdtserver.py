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
from pycrdt import Text, Map  # ← 추가

# 경로 설정
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 파일 상단 임포트들 아래 어딘가에 추가
# 맨 위 import 아래 어딘가에 추가
class LoggingFileYStore(FileYStore):
    def __init__(self, path: str, room_name: str):
        super().__init__(path)
        self._room = room_name
        self._path = path

    async def write(self, update: bytes):
        await super().write(update)
        logger.info(f"[ystore] wrote {len(update)} bytes for room='{self._room}' -> {self._path}")


def log_room_preview(key: str, room: YRoom):
    """문서의 상태를 안전하게 덤프: 업데이트 바이트, 루트 키/타입, notes/트리 일부"""
    doc = room.ydoc

    def _preview(s: str, n=120):
        try:
            return (s[:n] + "…") if len(s) > n else s
        except Exception:
            return "<preview error>"

    # 1) 전체 상태 바이트 크기 (예외 메시지까지 로깅)
    try:
        update_bytes = len(doc.encode_state_as_update())
    except Exception as e:
        logger.info(f"[dump] encode_state_as_update failed: {e}")
        update_bytes = -1



    # 2) 루트 키 목록 & 타입명 (있으면)
    keys = []
    try:
        # Doc이 매핑 프로토콜을 구현하면 이터레이션/키 조회 가능
        # 일부 버전에선 list(doc) 또는 doc.keys()가 동작
        try:
            iterable = list(doc)
        except Exception:
            iterable = list(doc.keys())  # fallback
        for k in iterable:
            try:
                v = doc[k]
                tname = type(v).__name__
                keys.append(f"{k}:{tname}")
            except Exception as e:
                keys.append(f"{k}:<read error {e}>")
    except Exception as e:
        keys = [f"<keys read error: {e}>"]

    # 3) notes 내용 시도 (duck-typing)
    notes_str = ""
    try:
        obj = doc["notes"]
        if hasattr(obj, "to_string"):
            notes_str = obj.to_string() or ""
        elif hasattr(obj, "to_py"):
            # 어떤 버전에선 to_py가 문자열 반환
            tmp = obj.to_py()
            notes_str = tmp if isinstance(tmp, str) else ""
        else:
            # 마지막 수단
            notes_str = str(obj) or ""
    except Exception:
        pass

    # 4) treeData 문자열 시도 (Map → dict 변환 뒤 'treeData' 키)
    tree_str = ""
    try:
        obj = doc["treeData"]
        data = {}
        if hasattr(obj, "to_py"):
            data = obj.to_py() or {}
        elif hasattr(obj, "to_json"):
            data = obj.to_json() or {}
        # 클라이언트가 ymap.set('treeData', JSON.stringify(...))로 넣음
        val = data.get("treeData", "")
        if isinstance(val, str):
            tree_str = val
        else:
            # 혹시 구조가 dict인 경우도 프리뷰
            tree_str = str(val) if val else ""
    except Exception:
        pass

    logger.info(
        "[dump] room='%s' update_bytes=%s keys=%s notes(len=%d)='%s' treeDataStr(len=%d)='%s'",
        key, update_bytes, keys, len(notes_str), _preview(notes_str), len(tree_str), _preview(tree_str)
    )



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
        #ystore = FileYStore(str(DATA_DIR / f"{key}.ystore"))
        ystore = LoggingFileYStore(str(DATA_DIR / f"{key}.ystore"), room_name=key)
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
        #ystore = FileYStore(str(file))
        ystore = LoggingFileYStore(str(file), room_name=key)
        room = YRoom(ready=False, ystore=ystore, log=logger)
        try:
            await ystore.apply_updates(room.ydoc)
            logger.info(f"[preload] restored room key='{key}' from {file.name}")
             # 🔽 복원 직후 실제 내용 미리보기 로그
            log_room_preview(key, room)
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

    
