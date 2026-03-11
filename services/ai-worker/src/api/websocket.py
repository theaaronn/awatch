import asyncio
import json
import logging
import time
import uuid
from collections import deque
from typing import Dict, List

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self, buffer_size: int = 100):
        self.active_connections: Dict[str, WebSocket] = {}
        self.alert_buffer: deque = deque(maxlen=buffer_size)
        self.heartbeat_interval = 30
        self.heartbeat_tasks: Dict[str, asyncio.Task] = {}
        self._api_keys: List[str] = []

    def set_api_keys(self, api_keys: List[str]) -> None:
        self._api_keys = api_keys

    async def connect(self, client_id: str, websocket: WebSocket, api_key: str) -> bool:
        if api_key not in self._api_keys:
            await websocket.close(code=4001, reason="Invalid API key")
            return False

        await websocket.accept()
        self.active_connections[client_id] = websocket
        await self.send_buffered_alerts(websocket)
        self.heartbeat_tasks[client_id] = asyncio.create_task(
            self.heartbeat(client_id, websocket)
        )
        return True

    def disconnect(self, client_id: str) -> None:
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.heartbeat_tasks:
            self.heartbeat_tasks[client_id].cancel()
            del self.heartbeat_tasks[client_id]
        logger.info(f"Client {client_id} disconnected")

    async def send_alert(self, alert: Dict) -> None:
        message = {
            "type": "alert",
            "data": alert,
            "timestamp": int(time.time()),
        }
        self.alert_buffer.append(message)
        await self.broadcast(message)

    async def broadcast(self, message: Dict) -> None:
        if not self.active_connections:
            return

        message_json = json.dumps(message)
        disconnected = []

        for client_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(message_json)
            except WebSocketDisconnect:
                disconnected.append(client_id)
            except Exception as e:
                logger.error(f"Error sending to client {client_id}: {e}")
                disconnected.append(client_id)

        for client_id in disconnected:
            self.disconnect(client_id)

    async def send_buffered_alerts(self, websocket: WebSocket) -> None:
        if not self.alert_buffer:
            return

        buffered_message = {
            "type": "buffered_alerts",
            "alerts": list(self.alert_buffer),
            "timestamp": int(time.time()),
        }
        await websocket.send_text(json.dumps(buffered_message))

    async def heartbeat(self, client_id: str, websocket: WebSocket) -> None:
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval)
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
        except asyncio.CancelledError:
            pass
        finally:
            self.disconnect(client_id)

    def get_connection_count(self) -> int:
        return len(self.active_connections)


manager = ConnectionManager()
