# simpleServer.py
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Tuple, Optional, Callable, Any

from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from pycrdt_websocket import WebsocketServer
from pycrdt import Doc, Text  # 누적 디코딩용

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("yws")
logger.setLevel(logging.DEBUG)  # 트러블슈팅 중엔 DEBUG, 안정화 후 INFO

# ---- y-websocket frame decoder (요약) ----
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
    return buf[pos:pos+length], pos + length

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

# ---- 룸별 누적 디코딩: DELTA & 상태 확인 ----
_debug_docs: dict[str, tuple[Doc, Text]] = {}

def _get_debug_ytext(room: str) -> tuple[Doc, Text]:
    st = _debug_docs.get(room)
    if st is None:
        d = Doc()
        d["xml"] = Text()
        _debug_docs[room] = (d, d["xml"])
    return _debug_docs[room]

def humanize_update_room(room: str, update_bytes: bytes) -> list[dict]:
    """룸별 Doc에 누적 적용해서 delta 추출"""
    doc, yxml = _get_debug_ytext(room)
    deltas: list[dict] = []

    def on_text(ev):
        deltas.extend(ev.delta)  # [{'retain':..},{'insert':'..'},{'delete':..}]

    yxml.observe(on_text)
    try:
        doc.apply_update(update_bytes)
    finally:
        try:
            yxml.unobserve(on_text)  # 구현에 따라 없을 수도 있어 안전 처리
        except Exception:
            pass
    return deltas

def get_debug_tail(room: str, n: int = 120) -> str:
    """현재 누적 상태의 꼬리 n글자(사람 확인용)"""
    _, yxml = _get_debug_ytext(room)
    try:
        s = yxml.to_string()  # 있으면 이게 가장 정확
    except Exception:
        s = str(yxml)
    return s[-n:]

# ---- WebSocket server ----
ws_server = WebsocketServer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(ws_server.start())
    try:
        yield
    finally:
        await ws_server.stop()
        await task

app = FastAPI(title="Yjs WebSocket (pycrdt-websocket)", lifespan=lifespan)

@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "simpleClient.html")

# ---- Starlette WebSocket -> pycrdt_websocket 어댑터 ----
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
        self.path = ws.scope.get("path", f"/ws/{room}")

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
                                self.logger.info("RX room=%s %s DELTA=%s",
                                                 self.room, f'{info["type"]}/{info["sub"]}', deltas)
                                # 현재 상태 꼬리 확인
                                try:
                                    tail = get_debug_tail(self.room, 120)
                                    self.logger.info("STATE room=%s tail=%r", self.room, tail)
                                except Exception:
                                    pass
                            except Exception as e:
                                self.logger.warning("RX room=%s delta_fail=%s ulen=%s",
                                                    self.room, e, info.get("update_len"))
                        else:
                            self.logger.debug("RX room=%s %s", self.room, info)
                    except Exception as e:
                        self.logger.debug("RX room=%s parse_err=%s len=%s",
                                          self.room, e, len(b))
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

@app.websocket("/ws/{room:path}")
async def ws_endpoint(ws: WebSocket, room: str):
    await ws.accept()
    adapter = WSAdapter(
        ws, room, logger,
        log_wire=True,
        log_delta=True,
        parse_fn=parse_ws_frame,
        # 룸별 누적 디코딩을 위해 람다로 room 캡처
        delta_fn=lambda upd, r=room: humanize_update_room(r, upd),
    )
    try:
        await ws_server.serve(adapter)
    except Exception as e:
        logger.exception("serve() aborted room=%s: %s", room, e)
    finally:
        await adapter.close()
        logger.info("WS CLOSE room=%s", room)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("simpleServer:app", host="0.0.0.0", port=port, log_level=LOG_LEVEL.lower())
