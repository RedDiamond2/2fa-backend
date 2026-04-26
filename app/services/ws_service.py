# app/services/ws_service.py

from typing import Dict, List, Any
from fastapi import WebSocket
import json
import logging


logger = logging.getLogger("ws_service")


# =========================
# ⚡ WS CONNECTION MANAGER
# =========================


class ConnectionManager:
    def __init__(self):
        # active connections: {user_id: [websocket, ...]}
        self.active_connections: Dict[str, List[WebSocket]] = {}

    # -------------------------
    # CONNECT
    # -------------------------
    async def connect(self, user_id: str, websocket: WebSocket):
        try:
            await websocket.accept()

            if not user_id:
                return

            if user_id not in self.active_connections:
                self.active_connections[user_id] = []

            if websocket not in self.active_connections[user_id]:
                self.active_connections[user_id].append(websocket)

        except Exception as e:
            logger.warning(f"[WS][CONNECT] error user_id={user_id}: {e}")

    # -------------------------
    # DISCONNECT
    # -------------------------
    def disconnect(self, user_id: str, websocket: WebSocket):
        try:
            if user_id in self.active_connections:
                if websocket in self.active_connections[user_id]:
                    self.active_connections[user_id].remove(websocket)

                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]

        except Exception as e:
            logger.warning(f"[WS][DISCONNECT] error user_id={user_id}: {e}")

    # -------------------------
    # SEND TO USER
    # -------------------------
    async def send_to_user(self, user_id: str, message: Dict[str, Any]):
        if not user_id or user_id not in self.active_connections:
            return

        dead_connections: List[WebSocket] = []

        payload = self._safe_json(message)

        for connection in self.active_connections.get(user_id, []):
            try:
                await connection.send_text(payload)
            except Exception:
                dead_connections.append(connection)

        # cleanup dead connections
        for conn in dead_connections:
            try:
                self.active_connections[user_id].remove(conn)
            except Exception:
                pass

        if user_id in self.active_connections and not self.active_connections[user_id]:
            del self.active_connections[user_id]

    # -------------------------
    # BROADCAST
    # -------------------------
    async def broadcast(self, message: Dict[str, Any]):
        dead_map: List[tuple[str, WebSocket]] = []
        payload = self._safe_json(message)

        for user_id, connections in list(self.active_connections.items()):
            for connection in connections:
                try:
                    await connection.send_text(payload)
                except Exception:
                    dead_map.append((user_id, connection))

        # cleanup
        for user_id, conn in dead_map:
            try:
                if user_id in self.active_connections:
                    if conn in self.active_connections[user_id]:
                        self.active_connections[user_id].remove(conn)

                    if not self.active_connections[user_id]:
                        del self.active_connections[user_id]
            except Exception:
                pass

    # -------------------------
    # GET STATUS
    # -------------------------
    def get_active_users(self) -> List[str]:
        return list(self.active_connections.keys())

    # -------------------------
    # SAFE JSON SERIALIZER
    # -------------------------
    def _safe_json(self, message: Dict[str, Any]) -> str:
        try:
            return json.dumps(message, ensure_ascii=False, default=str)
        except Exception:
            return json.dumps({"error": "invalid_ws_message"})


# =========================
# 🌐 SINGLETON INSTANCE
# =========================

ws_manager = ConnectionManager()
