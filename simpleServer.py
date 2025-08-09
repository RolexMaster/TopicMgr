# simpleServer.py
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Tuple, Optional, Callable, Any

from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import FileResponse

from pycrdt_websocket import WebsocketServer
from pycrdt_websocket.yroom import YRoom
from pycrdt import Doc, Text  # 누적 디코딩 및 통계 계산용

# -------------------------
# 경로/로깅
# -------------------------
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data" / "rooms"   # 방별 스냅샷 저장 위치
DATA_DIR.mkdir(parents=True, exist_ok=True)

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("yws")
logger.setLevel(logging.DEBUG)  # 디버깅 중엔 DEBUG, 안정화되면 INFO

# ✅ 서버 준비 플래그 (로드 끝나기 전 접속 차단용)
APP_READY = asyncio.Event()

# -------------------------
# y-websocket 프레임 요약 파서
# -------------------------
def read_varuint(buf: bytes, pos: int) -> Tuple[int, int]:
    res = 0
    shift = 0
    while True:
        b = buf[pos]
        pos += 1
        res |= (b & 0x7F) << shift
        if (b & 0x80) == 0:
            break
        shift += 7
    return res, pos

def read_varuint8array(buf: bytes, pos: int) -> Tuple[bytes, int]:
    length, pos = read_varuint(buf, pos)
    return buf[pos:pos + length], pos + length

SYNC, AWARENESS, AUTH = 0, 1, 2
SYNC_STEP1, SYNC_STEP2, SYNC_UPDATE = 0, 1, 2

def parse_ws_frame(frame: bytes) -> dict:
    try:
        pos = 0
        msg_type, pos = read_varuint(frame, pos)
        if msg_type == SYNC:
            sub, pos = read_varuint(frame, pos)
            if sub == SYNC_STEP1:
                sv, pos = read_varuint8array(frame, pos)
                return {"type": "sync", "sub": "step1", "state_vector_len": len(sv)}
            elif sub == SYNC_STEP2:
                upd, pos = read_varuint8array(frame, pos)
                return {"type": "sync", "sub": "step2", "update_len": len(upd), "update": upd}
            elif sub == SYNC_UPDATE:
                upd, pos = read_varuint8array(frame, pos)
                return {"type": "sync", "sub": "update", "update_len": len(upd), "update": upd}
            else:
                return {"type": "sync", "sub": f"unknown({sub})"}
        elif msg_type == AWARENESS:
            payload, pos = read_varuint8array(frame, pos)
            return {"type": "awareness", "payload_len": len(payload), "payload_head_hex": payload[:32].hex()}
        elif msg_type == AUTH:
            payload, pos = read_varuint8array(frame, pos)
            return {"type": "auth", "payload_len": len(payload)}
        else:
            return {"type": f"unknown({msg_type})"}
    except Exception as e:
        try:
            head_hex = (bytes(frame)[:32]).hex()
        except Exception:
            head_hex = "<unavailable>"
        try:
            l = len(frame)
        except Exception:
            l = None
        return {"type": "parse_error", "error": str(e), "head_hex": head_hex, "len": l}

# -------------------------
# 룸별 디버그 Doc/Text (누적 상태 & delta 확인)
# -------------------------
_debug_docs: dict[str, tuple[Doc, Text]] = {}

def _get_debug_ytext(room: str) -> tuple[Doc, Text]:
    st = _debug_docs.get(room)
    if st is None:
        d = Doc()
        d["xml"] = Text()
        _debug_docs[room] = (d, d["xml"])
    return _debug_docs[room]

def humanize_update_room(room: str, update_bytes: bytes) -> list[dict]:
    """룸별 Doc에 업데이트 누적 적용하면서 delta 반환 (디버그 전용 Doc 사용)"""
    doc, yxml = _get_debug_ytext(room)
    deltas: list[dict] = []
    def on_text(ev):
        deltas.extend(ev.delta)
    yxml.observe(on_text)
    try:
        doc.apply_update(update_bytes)
    finally:
        try:
            yxml.unobserve(on_text)
        except Exception:
            pass
    return deltas

def get_debug_tail(room: str, n: int = 120) -> str:
    """현재 누적 상태 꼬리 n글자 (사람 확인용) — 디버그 Doc 기준"""
    _, yxml = _get_debug_ytext(room)
    try:
        s = str(yxml)  # Text.__str__ 트랜잭션으로 안전히 문자열화
    except Exception:
        s = ""
    return s[-n:]

# -------------------------
# 간단 영속화: 파일 저장/로드
# -------------------------
def _room_to_filename(room: str) -> Path:
    safe = room.replace("/", "__")
    return DATA_DIR / f"{safe}.bin"

def save_room_snapshot(room: str) -> None:
    """디버그 Doc의 전체 스냅샷을 파일로 저장 (atomic)"""
    doc, _ = _get_debug_ytext(room)
    empty_sv = Doc().get_state()
    full_update = doc.get_update(empty_sv)
    tmp = _room_to_filename(room).with_suffix(".bin.tmp")
    dst = _room_to_filename(room)
    try:
        tmp.write_bytes(full_update)
        os.replace(tmp, dst)  # atomic
        logger.debug("PERSIST room=%s wrote %s bytes -> %s", room, len(full_update), dst.name)
    except Exception as e:
        logger.warning("PERSIST room=%s failed: %s", room, e)
        try:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
        except Exception:
            pass

def load_room_snapshot_bytes(room: str) -> Optional[bytes]:
    """스냅샷 파일을 읽어서 raw bytes 반환. 없으면 None."""
    f = _room_to_filename(room)
    if not f.exists():
        return None
    try:
        return f.read_bytes()
    except Exception as e:
        logger.warning("READ room=%s failed: %s", room, e)
        return None

def load_room_snapshot_into_memory(room: str) -> bool:
    """파일이 있으면 디버그 Doc에 적용 (디버그용 상태 누적)."""
    data = load_room_snapshot_bytes(room)
    if data is None:
        return False
    try:
        doc, _ = _get_debug_ytext(room)
        doc.apply_update(data)
        tail = get_debug_tail(room, 120)
        logger.info("LOAD room=%s bytes=%s tail=%r", room, len(data), tail)
        return True
    except Exception as e:
        logger.warning("LOAD room=%s failed: %s", room, e)
        return False

# -------------------------
# WebSocket server (라이브 룸 선생성 지원)
# -------------------------
ws_server = WebsocketServer()

def precreate_live_room_from_bytes(room: str, update: bytes) -> None:
    """스냅샷 바이트로 라이브 룸을 미리 만들어 등록."""
    if room in ws_server.rooms:
        return
    try:
        yroom = YRoom()                    # 빈 ydoc 포함
        yroom.ydoc.apply_update(update)    # 스냅샷 주입
        ws_server.rooms[room] = yroom      # 키는 WSAdapter.path와 동일해야 함: room
        logger.info("PRECREATE room=%s bytes=%d", room, len(update))
    except Exception as e:
        logger.warning("PRECREATE room=%s failed: %s", room, e)

def ensure_live_room_preloaded(room: str) -> bool:
    """
    라이브 룸이 없으면 디스크 스냅샷을 읽어 즉시 PRECREATE.
    (ws 진입 시 세이프가드)
    """
    if room in ws_server.rooms:
        return True
    data = load_room_snapshot_bytes(room)
    if not data:
        logger.debug("ENSURE room=%s no snapshot on disk", room)
        return False
    precreate_live_room_from_bytes(room, data)
    return True

def preload_all_rooms_from_disk() -> None:
    """파일 → 디버그 Doc 누적 + 라이브 룸 선생성(즉시 동기화용)."""
    for f in DATA_DIR.glob("*.bin"):
        room = f.stem.replace("__", "/")
        try:
            data = f.read_bytes()
            # 1) 디버그 Doc 누적
            doc, _ = _get_debug_ytext(room)
            doc.apply_update(data)
            tail = get_debug_tail(room, 120)
            logger.info("LOAD room=%s bytes=%d tail=%r", room, len(data), tail)
            # 2) 라이브 룸 선생성
            precreate_live_room_from_bytes(room, data)
        except Exception as e:
            logger.warning("LOAD room=%s failed: %s", room, e)

# -------------------------
# FastAPI (lifespan)
# -------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1) 서버 백그라운드 태스크 먼저 띄우고
    task_server = asyncio.create_task(ws_server.start())
    # 2) 아주 짧게 양보해 내부 초기화 기회를 준 뒤
    await asyncio.sleep(0.05)
    # 3) 이제 디스크에서 선로딩 + 라이브 룸 주입
    preload_all_rooms_from_disk()
    # 4) 준비 완료
    APP_READY.set()
    try:
        yield
    finally:
        await ws_server.stop()
        await task_server

app = FastAPI(title="Yjs WebSocket (pycrdt-websocket)", lifespan=lifespan)

@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "simpleClient.html")

# (선택) 준비 상태 확인용
@app.get("/ready")
def ready():
    return {"ready": APP_READY.is_set()}

@app.get("/sizes/{room}")
async def sizes(room: str):
    """
    파일로부터 미리 로드된 디버그 Doc 기준으로 상태 크기/꼬리 반환.
    (라이브 ydoc은 다른 스레드에서 돌 수 있으므로 직접 접근하지 않음)
    """
    _ = load_room_snapshot_into_memory(room)  # 혹시 비어있으면 1회성 로드
    doc, yxml = _get_debug_ytext(room)
    text = str(yxml)  # 안전한 문자열화
    empty_sv = Doc().get_state()
    full_update = doc.get_update(empty_sv)
    return {
        "room": room,
        "text_chars": len(text),
        "text_utf8_bytes": len(text.encode("utf-8")),
        "bytes_full_update": len(full_update),
        "tail": text[-200:],
    }

# -------------------------
# Starlette WebSocket -> pycrdt_websocket 어댑터
# -------------------------
class WSAdapter:
    """
    send(bytes), recv()->bytes, path, close() 제공
    + async iterator 규약(__aiter__/__anext__)
    + (옵션) parse_fn(frame)->dict, delta_fn(update)->list 로깅
    """
    def __init__(
        self,
        ws: WebSocket,
        room: str,
        logger: Optional[logging.Logger] = None,
        *,
        log_wire: bool = False,
        log_delta: bool = False,
        parse_fn: Optional[Callable[[bytes], dict]] = None,
        delta_fn: Optional[Callable[[bytes], list]] = None,
    ) -> None:
        self._send_asgi = ws.send
        self._recv_asgi = ws.receive
        self._close_asgi = ws.close
        self._ws = ws

        self.room = room
        # '/ws/<room>' 대신 'room' 하나로 고정(키 혼란 방지)
        self.path = room

        self.logger = logger or logging.getLogger("yws")
        self.log_wire = log_wire
        self.log_delta = log_delta
        self.parse_fn = parse_fn
        self.delta_fn = delta_fn

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        try:
            data = await self.recv()
            return data
        except Exception:
            raise StopAsyncIteration

    async def send(self, data: Any) -> None:
        if isinstance(data, memoryview):
            data = data.tobytes()
        elif isinstance(data, bytearray):
            data = bytes(data)
        elif not isinstance(data, (bytes,)):
            data = bytes(str(data), "utf-8")
        if self.log_wire and self.parse_fn:
            try:
                info = self.parse_fn(data)
                self.logger.debug("TX room=%s %s", self.room, info)
            except Exception as e:
                self.logger.debug("TX room=%s parse_err=%s len=%s", self.room, e, len(data))
        await self._send_asgi({"type": "websocket.send", "bytes": data})

    async def recv(self) -> bytes:
        while True:
            evt = await self._recv_asgi()
            t = evt["type"]
            if t == "websocket.receive":
                b = evt.get("bytes")
                if b is None:
                    b = evt.get("text", "").encode("utf-8")
                if self.log_wire and self.parse_fn:
                    try:
                        info = self.parse_fn(b)
                        if self.log_delta and self.delta_fn and info.get("type") == "sync" \
                           and info.get("sub") in ("update", "step2") and "update" in info:
                            try:
                                deltas = self.delta_fn(info["update"])
                                self.logger.info(
                                    "RX room=%s %s DELTA=%s",
                                    self.room, f'{info["type"]}/{info["sub"]}', deltas
                                )
                                try:
                                    tail = get_debug_tail(self.room, 120)
                                    self.logger.info("STATE room=%s tail=%r", self.room, tail)
                                except Exception:
                                    pass
                            except Exception as e:
                                self.logger.warning(
                                    "RX room=%s delta_fail=%s ulen=%s",
                                    self.room, e, info.get("update_len")
                                )
                            # 변경 시에만 스냅샷 저장
                            try:
                                should_persist = False
                                if info.get("sub") == "update":
                                    should_persist = True
                                elif info.get("sub") == "step2":
                                    should_persist = bool(info.get("update_len", 0) > 0 and deltas)
                                if should_persist:
                                    save_room_snapshot(self.room)
                            except Exception as e:
                                self.logger.debug("PERSIST-SKIP room=%s reason=%s", self.room, e)
                        else:
                            self.logger.debug("RX room=%s %s", self.room, info)
                    except Exception as e:
                        self.logger.debug("RX room=%s parse_err=%s len=%s", self.room, e, len(b))
                return b
            if t == "websocket.disconnect":
                code = evt.get("code")
                self.logger.info("WS DISCONNECT room=%s code=%s", self.room, code)
                raise RuntimeError(f"disconnect {code}")
            self.logger.debug("WS EVENT room=%s type=%s (ignored)", self.room, t)

    async def close(self) -> None:
        try:
            await self._send_asgi({"type": "websocket.close"})
        except Exception:
            pass

# -------------------------
# WebSocket 엔드포인트
# -------------------------
@app.websocket("/ws/{room:path}")
async def ws_endpoint(ws: WebSocket, room: str):
    # 🔐 준비될 때까지는 접속 거절(최대 10초 대기 후 1013)
    if not APP_READY.is_set():
        try:
            await asyncio.wait_for(APP_READY.wait(), timeout=10)
        except asyncio.TimeoutError:
            logger.warning("WS REFUSE room=%s reason=server_not_ready code=1013", room)
            await ws.close(code=1013)  # Try Again Later
            return

    # 접속 직전, 라이브 룸 보장(디스크 스냅샷이 있으면 즉시 주입)
    if ensure_live_room_preloaded(room):
        logger.debug("ENSURE OK room=%s (live room present before accept)", room)
    else:
        logger.debug("ENSURE SKIP room=%s (no snapshot found)", room)

    await ws.accept()

    adapter = WSAdapter(
        ws, room, logger,
        log_wire=True,
        log_delta=True,
        parse_fn=parse_ws_frame,
        # 룸별 누적 디코딩을 위해 room 캡처 (디버그 Doc 사용)
        delta_fn=lambda upd, r=room: humanize_update_room(r, upd),
    )
    try:
        await ws_server.serve(adapter)
    except Exception as e:
        logger.exception("serve() aborted room=%s: %s", room, e)
    finally:
        await adapter.close()
        logger.info("WS CLOSE room=%s", room)

# -------------------------
# main
# -------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("simpleServer:app", host="0.0.0.0", port=port, log_level=LOG_LEVEL.lower())
