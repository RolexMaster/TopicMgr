## Fix WebSocket connection error by restoring room name path parameter

### Problem

The WebSocket connection was failing with error code 1006 because the server endpoint was not properly handling room names in the URL path.

### Root Cause Analysis

#### How y-websocket Works
The y-websocket library automatically appends the room name to the WebSocket URL:
- Client code: `new WebsocketProvider('wss://host/ws', 'hi', doc)`
- Actual connection attempt: `wss://host/ws/hi`

#### Timeline of Changes
1. **Initial state**: Server had `/ws` endpoint only → Connection failed
2. **PR #21**: Changed to `/ws/{room_name:path}` → **This was the correct fix**
3. **PR #22**: Reverted back to `/ws` with incorrect assumption that "room name is sent as part of WebSocket protocol messages" → **This caused the issue to reappear**

#### Why PR #22 Was Wrong
PR #22's assumption was incorrect. The y-websocket library does NOT send room names through protocol messages. It appends them to the URL path, which is standard behavior for y-websocket/yjs ecosystem.

### Solution

Restore the correct endpoint pattern from PR #21:
```python
@app.websocket("/ws/{room_name:path}")
async def websocket_endpoint(websocket: WebSocket, room_name: str):
    # Set the path for pycrdt-websocket to identify the room
    bridge.path = f"/{room_name}"
```

### Key Changes
1. Use `{room_name:path}` pattern to capture room names from URL
2. Set `bridge.path` to pass room information to pycrdt-websocket
3. Add logging for room-specific connections and disconnections

### Error Logs Before Fix
```
WebSocket connection to 'wss://topicmgr.azurewebsites.net/ws/hi' failed
WebSocket 연결 에러: Event {isTrusted: true, type: 'error', target: WebSocket...}
WebSocket 연결이 닫혔습니다: CloseEvent {isTrusted: true, wasClean: false, code: 1006, reason: ''...}
```

### Testing
- Verified that client can connect to `/ws/hi` endpoint
- Confirmed pycrdt-websocket correctly identifies rooms
- Tested with Azure App Service WebSocket proxy

### Technical Details

The issue stems from a misunderstanding of how y-websocket and pycrdt-websocket interact:

1. **y-websocket (client side)**:
   - When you create `new WebsocketProvider(url, roomName, doc)`, it concatenates `url + '/' + roomName`
   - This is hardcoded behavior in the y-websocket library

2. **pycrdt-websocket (server side)**:
   - Expects to identify rooms from the WebSocket connection's path
   - The `WebSocketBridge.path` attribute is used to determine which room the connection belongs to

3. **FastAPI WebSocket routing**:
   - Must use `{room_name:path}` to capture the room name from the URL
   - Without this, FastAPI returns 404 for `/ws/roomname` requests

### Note
This PR essentially reverts the incorrect changes from PR #22 and restores the correct solution from PR #21.