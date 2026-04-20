# app/services/ws_service.py

from typing import Dict, List, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import json


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
        await websocket.accept()

        if user_id not in self.active_connections:
            self.active_connections[user_id] = []

        self.active_connections[user_id].append(websocket)

    # -------------------------
    # DISCONNECT
    # -------------------------
    def disconnect(self, user_id: str, websocket: WebSocket):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)

            if len(self.active_connections[user_id]) == 0:
                del self.active_connections[user_id]

    # -------------------------
    # SEND TO USER
    # -------------------------
    async def send_to_user(self, user_id: str, message: Dict[str, Any]):
        if user_id not in self.active_connections:
            return

        dead_connections = []

        for connection in self.active_connections[user_id]:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                dead_connections.append(connection)

        for conn in dead_connections:
            self.active_connections[user_id].remove(conn)

    # -------------------------
    # BROADCAST
    # -------------------------
    async def broadcast(self, message: Dict[str, Any]):
        dead_map = []

        for user_id, connections in self.active_connections.items():
            for connection in connections:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception:
                    dead_map.append((user_id, connection))

        for user_id, conn in dead_map:
            if user_id in self.active_connections:
                if conn in self.active_connections[user_id]:
                    self.active_connections[user_id].remove(conn)

    # -------------------------
    # GET STATUS
    # -------------------------
    def get_active_users(self) -> List[str]:
        return list(self.active_connections.keys())


# =========================
# 🌐 SINGLETON INSTANCE
# =========================

ws_manager = ConnectionManager()