# app/routes/ws_routes.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional

from app.services.ws_service import ws_manager
from app.services.usage_service import log_event

router = APIRouter(prefix="/ws", tags=["WebSocket"])


# =========================
# ⚡ MAIN WEBSOCKET ENDPOINT
# =========================
@router.websocket("/connect")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: Optional[str] = Query(None),
    fingerprint: Optional[str] = Query(None),
):
    if not user_id:
        await websocket.close(code=1008)
        return

    await ws_manager.connect(user_id, websocket)

    try:
        await log_event(
            event="ws_connect",
            user_id=user_id,
            meta={
                "fingerprint": fingerprint,
            },
        )

        # =========================
        # 🔁 MESSAGE LOOP
        # =========================
        while True:
            data = await websocket.receive_json()

            await log_event(
                event="ws_message",
                user_id=user_id,
                meta={"data": data},
            )

            # 🔥 EVENT ROUTING (forward to manager)
            if isinstance(data, dict) and "event" in data:
                await ws_manager.handle_event(user_id, data)
            else:
                await ws_manager.send_personal(user_id, {
                    "event": "error",
                    "message": "Invalid event format",
                })

    except WebSocketDisconnect:
        await ws_manager.disconnect(user_id)

        await log_event(
            event="ws_disconnect",
            user_id=user_id,
            meta={},
        )