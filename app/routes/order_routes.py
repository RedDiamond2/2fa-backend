# app/routes/order_routes.py

import uuid
import hashlib
import threading
import logging
import json
import os
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.parser_service import parse_conversation
from app.services.order_service import create_order_from_parsed
from app.services.response_formatter import format_order_for_frontend
from app.services.usage_service import log_event
from app.services.learning_service import store_learning_case, get_learning_cases


logger = logging.getLogger("order_routes")

if not logger.handlers:
    logger.setLevel(logging.INFO)
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    file_handler = logging.FileHandler(
        os.path.join(log_dir, "order_pipeline.log"), encoding="utf-8"
    )
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

router = APIRouter()


# =========================================================
# LOGGING
# =========================================================
def log_step(title: str, data: Any, trace_id: str):
    try:
        logger.info(
            json.dumps(
                {"trace_id": trace_id, "step": title, "data": data},
                ensure_ascii=False,
                default=str,
            )
        )
    except Exception:
        pass


# =========================================================
# IDEMPOTENCY
# =========================================================
IDEMPOTENCY_STORE: Dict[str, Any] = {}
IDEMPOTENCY_LOCK = threading.Lock()
IDEMPOTENCY_TTL_SECONDS = 300


def generate_idempotency_key(messages: List[str], conversation_id: str) -> str:
    raw = f"{conversation_id}|{'|'.join(messages)}"
    return hashlib.sha256(raw.encode()).hexdigest()


def clean_idempotency_store():
    now = datetime.now()
    with IDEMPOTENCY_LOCK:
        expired = [
            k
            for k, v in IDEMPOTENCY_STORE.items()
            if now - v["time"] > timedelta(seconds=IDEMPOTENCY_TTL_SECONDS)
        ]
        for k in expired:
            del IDEMPOTENCY_STORE[k]


# =========================================================
# SCHEMAS
# =========================================================
class ChatInput(BaseModel):
    messages: List[str]
    conversation_id: Optional[str] = "default"


class FeedbackInput(BaseModel):
    raw_message: str
    parsed: dict
    corrected: dict
    confidence: float


# =========================================================
# UTILS
# =========================================================
def _safe_text(value: Any) -> str:
    return "" if value is None else str(value)


def _normalize_messages(messages: Any) -> List[str]:
    if not isinstance(messages, list):
        return []

    out: List[str] = []
    for m in messages:
        t = _safe_text(m).strip()
        if t:
            out.append(t)
    return out


def _extract_order(parsed: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(parsed, dict):
        return {}

    if parsed.get("multi_orders") is True and isinstance(parsed.get("orders"), list):
        orders = [o for o in parsed.get("orders", []) if isinstance(o, dict)]
        return orders[0] if orders else {}

    if isinstance(parsed.get("order"), dict):
        return parsed["order"]

    if isinstance(parsed.get("orders"), list):
        orders = [o for o in parsed.get("orders", []) if isinstance(o, dict)]
        return orders[0] if orders else {}

    return parsed


# =========================================================
# PARSER ONLY PIPELINE (ORCHESTRATION ONLY)
# =========================================================
async def _parse_only_pipeline(order_input: Dict[str, Any]) -> Dict[str, Any]:
    messages = _normalize_messages(order_input.get("messages") or [])
    conversation_id = (
        _safe_text(order_input.get("conversation_id")).strip() or "default"
    )
    trace_id = _safe_text(order_input.get("trace_id")).strip() or str(uuid.uuid4())
    temp_id = _safe_text(order_input.get("temp_id")).strip() or None

    if not messages:
        raise ValueError("messages are required")

    parser_result = await parse_conversation(
        messages=messages,
        conversation_id=conversation_id,
        trace_id=trace_id,
    )

    order = _extract_order(parser_result)

    if not order:
        raise ValueError("parser returned empty order")

    # ORCHESTRATION ONLY META ENRICHMENT (NO DECISION LOGIC)
    order["conversation_id"] = conversation_id
    order["messages"] = messages
    order["raw_message"] = "\n".join(messages)
    order["temp_id"] = temp_id or trace_id
    order["trace_id"] = trace_id

    return order


# =========================================================
# PIPELINE
# =========================================================
async def run_single_order_pipeline(order_input: Dict[str, Any]) -> Dict[str, Any]:
    messages = _normalize_messages(order_input.get("messages") or [])

    parsed = await _parse_only_pipeline(order_input)

    trace_id = (
        _safe_text(order_input.get("trace_id")).strip()
        or parsed.get("temp_id")
        or str(uuid.uuid4())
    )

    created = create_order_from_parsed(
        data=parsed,
        decision_data=parsed.get("meta", {}),
        trace_id=trace_id,
    )

    if isinstance(created, dict) and created.get("status") == "error":
        return created

    clean_order = (
        created["order"]
        if isinstance(created, dict) and "order" in created
        else created
    )
    formatted = format_order_for_frontend(clean_order)

    response_payload = {
        "success": True,
        "mode": "single",
        "orders": [formatted],
    }

    log_step("ORDER_CREATED", formatted, trace_id)
    return response_payload


async def run_bulk_order_pipeline(list_of_orders: List[Dict[str, Any]]):
    tasks = [run_single_order_pipeline(o) for o in list_of_orders]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = []
    for r in results:
        if isinstance(r, Exception):
            output.append({"success": False, "error": str(r)})
        else:
            output.append(r)

    return output


async def run_pipeline(
    messages: List[str],
    conversation_id: str,
    trace_id: str,
    client_temp_id: Optional[str] = None,
):
    return await run_single_order_pipeline(
        {
            "messages": messages,
            "conversation_id": conversation_id,
            "trace_id": trace_id,
            "temp_id": client_temp_id,
        }
    )


# =========================================================
# ROUTES
# =========================================================
@router.post("/orders/from-chat")
async def create_order_from_chat(data: ChatInput):
    trace_id = str(uuid.uuid4())
    clean_idempotency_store()

    key = generate_idempotency_key(data.messages, data.conversation_id)

    with IDEMPOTENCY_LOCK:
        if key in IDEMPOTENCY_STORE:
            cached = IDEMPOTENCY_STORE[key]["response"]
            cached["idempotent"] = True
            return cached

    try:
        result = await run_single_order_pipeline(
            {
                "messages": data.messages,
                "conversation_id": data.conversation_id,
                "trace_id": trace_id,
            }
        )

        with IDEMPOTENCY_LOCK:
            IDEMPOTENCY_STORE[key] = {"response": result, "time": datetime.now()}

        log_step("FINAL_RESPONSE", result, trace_id)
        return result

    except Exception:
        logger.error("PIPELINE_ERROR", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error")


@router.post("/orders/from-chat-bulk")
async def from_chat_bulk(payload: dict):
    raw_messages = payload.get("messages", [])
    conversation_id = _safe_text(payload.get("conversation_id")).strip() or "default"

    if not isinstance(raw_messages, list) or not raw_messages:
        raise HTTPException(status_code=400, detail="Messages required")

    inputs = []
    for msg in raw_messages:
        if isinstance(msg, dict):
            content = _safe_text(msg.get("content")).strip()
        else:
            content = _safe_text(msg).strip()

        if not content:
            continue

        inputs.append(
            {
                "messages": [content],
                "conversation_id": conversation_id,
                "temp_id": str(uuid.uuid4()),
            }
        )

    results = await run_bulk_order_pipeline(inputs)

    return {
        "success": True,
        "mode": "bulk",
        "orders": results,
    }


@router.post("/orders/debug-parse")
async def debug_parse(data: ChatInput):
    trace_id = str(uuid.uuid4())
    parsed = await _parse_only_pipeline(
        {
            "messages": data.messages,
            "conversation_id": data.conversation_id,
            "trace_id": trace_id,
        }
    )
    return {"success": True, "parsed": parsed}


# =========================================================
# LEARNING
# =========================================================
@router.post("/learning/feedback")
def submit_feedback(data: FeedbackInput):
    case = store_learning_case(
        data.raw_message,
        data.parsed,
        data.corrected,
        data.confidence,
    )

    log_event(
        event="learning_stored",
        trace_id=str(uuid.uuid4()),
        status="ok",
        meta={"raw": data.raw_message},
    )

    return {"success": True, "case": case}


@router.get("/learning/cases")
def list_learning_cases():
    cases = get_learning_cases()
    return {"count": len(cases), "data": cases}
