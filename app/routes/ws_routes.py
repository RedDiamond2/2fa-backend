# app/routes/ws_routes.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional, Dict, Any
import logging

from app.services.ws_service import ws_manager
from app.services.usage_service import log_event

router = APIRouter(prefix="/ws", tags=["WebSocket"])

logger = logging.getLogger("ws_routes")


# =========================
# 🧠 SAFE SEND
# =========================
async def _safe_send(websocket: WebSocket, payload: Dict[str, Any]):
    try:
        await websocket.send_json(payload)
    except Exception as e:
        logger.error(f"WS send error: {str(e)}")


# =========================
# 🧠 SAFE RECEIVE
# =========================
async def _safe_receive(websocket: WebSocket) -> Optional[Dict[str, Any]]:
    try:
        data = await websocket.receive_json()
        if not isinstance(data, dict):
            return None
        return data
    except Exception as e:
        logger.warning(f"WS receive error: {str(e)}")
        return None


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

        await _safe_send(
            websocket,
            {
                "event": "connected",
                "user_id": user_id,
            },
        )

        # =========================
        # 🔁 MESSAGE LOOP
        # =========================
        while True:
            data = await _safe_receive(websocket)

            if not data:
                await _safe_send(
                    websocket, {"event": "error", "message": "Invalid or empty payload"}
                )
                continue

            await log_event(
                event="ws_message",
                user_id=user_id,
                meta={"data": data},
            )

            event_type = data.get("event")

            if not event_type:
                await _safe_send(
                    websocket, {"event": "error", "message": "Missing event field"}
                )
                continue

            try:
                await ws_manager.handle_event(user_id, data)
            except Exception as e:
                logger.error(f"WS event handler crash: {str(e)}", exc_info=True)

                await _safe_send(
                    websocket,
                    {"event": "error", "message": "Internal event handling error"},
                )

    except WebSocketDisconnect:
        await ws_manager.disconnect(user_id)

        await log_event(
            event="ws_disconnect",
            user_id=user_id,
            meta={},
        )

    except Exception as e:
        logger.error(f"WS fatal error: {str(e)}", exc_info=True)

        try:
            await ws_manager.disconnect(user_id)
        except Exception:
            pass

        await log_event(
            event="ws_error",
            user_id=user_id,
            meta={"error": str(e)},
        )
