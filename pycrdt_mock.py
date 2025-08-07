"""
Mock implementation of pycrdt for debugging WebSocket connection issues.
This is a minimal implementation to allow the server to run without the actual pycrdt library.
"""

import json
import asyncio
from typing import Dict, Any, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class Doc:
    """Mock implementation of pycrdt.Doc"""
    def __init__(self):
        self._data = {}
        self._version = 0
        self._observers = []
    
    def get_map(self, name: str):
        """Get a map object"""
        if name not in self._data:
            self._data[name] = YMap(name, self)
        return self._data[name]
    
    def get_array(self, name: str):
        """Get an array object"""
        if name not in self._data:
            self._data[name] = YArray(name, self)
        return self._data[name]
    
    def observe(self, callback):
        """Add an observer"""
        self._observers.append(callback)
    
    def notify_change(self):
        """Notify all observers of changes"""
        self._version += 1
        for observer in self._observers:
            observer(None)


class YMap:
    """Mock implementation of Y.Map"""
    def __init__(self, name: str, doc: Doc):
        self.name = name
        self.doc = doc
        self._data = {}
    
    def set(self, key: str, value: Any):
        self._data[key] = value
        self.doc.notify_change()
    
    def get(self, key: str, default=None):
        return self._data.get(key, default)
    
    def to_json(self):
        return dict(self._data)


class YArray:
    """Mock implementation of Y.Array"""
    def __init__(self, name: str, doc: Doc):
        self.name = name
        self.doc = doc
        self._data = []
    
    def append(self, item: Any):
        self._data.append(item)
        self.doc.notify_change()
    
    def insert(self, index: int, item: Any):
        self._data.insert(index, item)
        self.doc.notify_change()
    
    def delete(self, index: int, length: int = 1):
        for _ in range(length):
            if index < len(self._data):
                self._data.pop(index)
        self.doc.notify_change()
    
    def to_json(self):
        return list(self._data)
    
    def __len__(self):
        return len(self._data)
    
    def __getitem__(self, index):
        return self._data[index]


class YRoom:
    """Mock implementation of YRoom"""
    def __init__(self, name: str = "", doc: Optional[Doc] = None):
        self.name = name
        self.ydoc = doc or Doc()
        self.clients = set()
        self._on_message_callbacks = []
    
    async def connect(self, websocket):
        """Connect a client"""
        self.clients.add(websocket)
        logger.info(f"Client connected to room {self.name}. Total clients: {len(self.clients)}")
    
    async def disconnect(self, websocket):
        """Disconnect a client"""
        self.clients.discard(websocket)
        logger.info(f"Client disconnected from room {self.name}. Total clients: {len(self.clients)}")
    
    def on_message(self, callback: Callable):
        """Register message callback"""
        self._on_message_callbacks.append(callback)
    
    async def handle_message(self, websocket, message: bytes):
        """Handle incoming message"""
        # Check if this is a y-websocket protocol message
        if len(message) > 0:
            message_type = message[0]
            
            # Y-websocket protocol message types
            SYNC_STEP1 = 0
            SYNC_STEP2 = 1
            SYNC_UPDATE = 2
            AWARENESS = 1
            
            if message_type == SYNC_STEP1:
                # Client requesting sync, send sync step 2
                logger.info(f"Received sync step 1 from client in room {self.name}")
                # Create a minimal sync step 2 response
                response = bytes([SYNC_STEP2, 0])  # Empty doc state
                await websocket.send(response)
                return
            elif message_type == SYNC_STEP2:
                # Client sync response
                logger.info(f"Received sync step 2 from client in room {self.name}")
                return
            elif message_type == SYNC_UPDATE:
                # Document update, broadcast to other clients
                logger.info(f"Received document update in room {self.name}")
            elif message_type == AWARENESS:
                # Awareness update
                logger.info(f"Received awareness update in room {self.name}")
        
        # Broadcast to all other clients
        for client in self.clients:
            if client != websocket:
                try:
                    if hasattr(client, 'client_state') and client.client_state.open:
                        await client.send(message)
                    elif hasattr(client, 'state') and client.state == 1:  # WebSocket.State.OPEN
                        await client.send(message)
                except Exception as e:
                    logger.error(f"Error broadcasting message: {e}")
        
        # Call registered callbacks
        for callback in self._on_message_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                logger.error(f"Error in message callback: {e}")


class WebsocketServer:
    """Mock implementation of WebsocketServer"""
    def __init__(self, ydoc: Optional[Doc] = None, room_name: str = ""):
        self.ydoc = ydoc or Doc()
        self.room_name = room_name
        self.rooms: Dict[str, YRoom] = {}
        logger.info(f"Mock WebsocketServer initialized for room: {room_name}")
    
    def get_room(self, name: str) -> YRoom:
        """Get or create a room"""
        if name not in self.rooms:
            self.rooms[name] = YRoom(name, Doc())
        return self.rooms[name]
    
    async def handle_websocket(self, websocket, path: str = None):
        """Handle WebSocket connection"""
        room_name = path.strip('/') if path else self.room_name
        room = self.get_room(room_name)
        
        await room.connect(websocket)
        try:
            async for message in websocket:
                if isinstance(message, bytes):
                    await room.handle_message(websocket, message)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            await room.disconnect(websocket)