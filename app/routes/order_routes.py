# app/routes/order_routes.py
import uuid
import hashlib
import re
import traceback
import threading
import logging
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# 🔥 استيراد الإعدادات والخدمات
from app.core.config import settings
from app.services.context_service import (
    build_context, 
    extract_last_known_info, 
    get_conversation_history, 
    save_conversation
)
from app.services.parser_service import parse_conversation, extract_name
from app.services.location_service import infer_location
from app.services.confidence_service import compute_confidence
from app.services.warning_service import generate_warnings
from app.services.decision_service import apply_decision
from app.services.order_service import create_order_from_parsed
from app.services.confirmation_service import generate_confirmation
from app.services.usage_service import log_event
from app.services.learning_service import store_learning_case, get_learning_cases
from app.services.queue_service import enqueue_bulk
from app.services.response_formatter import format_order_for_frontend
from app.services.identity_service import resolve_identity 

# ==========================================
# 🛡️ نظام الـ Logging الاحترافي
# ==========================================
logger = logging.getLogger("order_routes")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file_path = os.path.join(log_dir, "order_pipeline.log")
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

router = APIRouter()
    
def log_step(title: str, data: any, trace_id: str):
    """نظام تتبع مرئي للعمليات داخل الـ Logging File"""
    try:
        log_entry = {"trace_id": trace_id, "step": title, "data": data}
        logger.info(json.dumps(log_entry, ensure_ascii=False, default=str))
    except Exception as e:
        logger.error(f"Logging Error: {str(e)}")

# ==========================================
# 🛡️ GLOBAL STORES & LOCKS (Production Ready)
# ==========================================
IDEMPOTENCY_STORE = {}
IDEMPOTENCY_LOCK = threading.Lock()
IDEMPOTENCY_TTL_SECONDS = 300 

# ==========================================
# 🛠️ HELPER FUNCTIONS
# ==========================================

def generate_idempotency_key(messages: List[str], conversation_id: str) -> str:
    raw = f"{conversation_id}|{'|'.join(messages)}"
    return hashlib.sha256(raw.encode()).hexdigest()

def generate_order_fingerprint(parsed: dict) -> str:
    # ✅ FIX 6: تحسين الـ Fingerprint ليشمل name أو customer_name
    phone = str(parsed.get('phone') or "")
    name = str(parsed.get('customer_name') or parsed.get('name') or "") 
    items = str(parsed.get('items') or [])
    core = f"{phone}|{name}|{items}"
    return hashlib.sha256(core.encode()).hexdigest()

def clean_idempotency_store():
    now = datetime.now()
    with IDEMPOTENCY_LOCK:
        expired_keys = [
            k for k, v in IDEMPOTENCY_STORE.items() 
            if now - v["time"] > timedelta(seconds=IDEMPOTENCY_TTL_SECONDS)
        ]
        for k in expired_keys:
            del IDEMPOTENCY_STORE[k]

# ================================
# 📥 نماذج البيانات (Schemas)
# ================================
class ChatInput(BaseModel):
    messages: List[str]
    conversation_id: Optional[str] = "default"
    
class FeedbackInput(BaseModel):
    raw_message: str
    parsed: dict
    corrected: dict
    confidence: float


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _normalize_messages(messages: Any) -> List[str]:
    if not isinstance(messages, list):
        return []

    normalized: List[str] = []
    for msg in messages:
        text = _safe_text(msg).strip()
        if text:
            normalized.append(text)
    return normalized


def _normalize_parser_order(order: Any) -> Dict[str, Any]:
    source = order if isinstance(order, dict) else {}
    address = source.get("address") if isinstance(source.get("address"), dict) else {}
    items = source.get("items") if isinstance(source.get("items"), list) else []

    safe_items: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        safe_items.append({
            "product": _safe_text(item.get("product")).strip(),
            "quantity": item.get("quantity") if isinstance(item.get("quantity"), (int, float)) else 1,
            "color": _safe_text(item.get("color")).strip() or None,
            "size": _safe_text(item.get("size")).strip() or None
        })

    return {
        "intent": _safe_text(source.get("intent")).strip() or "new",
        "name": _safe_text(source.get("name")).strip() or None,
        "phone": _safe_text(source.get("phone")).strip() or None,
        "location": source.get("location"),
        "address": {
            "full": _safe_text(address.get("full")).strip() or None,
            "province": _safe_text(address.get("province")).strip() or None,
            "district": _safe_text(address.get("district")).strip() or None,
            "area": _safe_text(address.get("area")).strip() or None,
            "building": _safe_text(address.get("building")).strip() or None,
            "door": _safe_text(address.get("door")).strip() or None,
        },
        "items": safe_items,
        "messages": _normalize_messages(source.get("messages") or []),
        "status": _safe_text(source.get("status")).strip() or "draft",
        "meta": source.get("meta") if isinstance(source.get("meta"), dict) else {}
    }


def _extract_parser_orders(parsed: Any) -> List[Dict[str, Any]]:
    if not isinstance(parsed, dict):
        return []

    # Strict parser contract support
    if parsed.get("multi_orders") is True and isinstance(parsed.get("orders"), list):
        return [_normalize_parser_order(o) for o in parsed.get("orders", [])]
    if parsed.get("multi_orders") is False and isinstance(parsed.get("order"), dict):
        return [_normalize_parser_order(parsed["order"])]

    # Backward-compat fallback (defensive)
    if isinstance(parsed.get("orders"), list):
        return [_normalize_parser_order(o) for o in parsed.get("orders", [])]
    if parsed.get("status") == "error":
        return []
    return [_normalize_parser_order(parsed)]


def _build_history(messages: List[str], conversation_id: str, persist: bool = True) -> List[str]:
    history = get_conversation_history(conversation_id) or []
    safe_history = [m for m in _normalize_messages(history) if m]

    for msg in messages:
        if msg and msg not in safe_history[-5:]:
            safe_history.append(msg)

    safe_history = safe_history[-settings.MAX_HISTORY:]
    if persist:
        save_conversation(conversation_id, safe_history)

    return safe_history


def _enrich_parsed_order(
    parsed: Dict[str, Any],
    *,
    messages: List[str],
    conversation_id: str,
    trace_id: str,
    temp_id: Optional[str],
    history: List[str],
) -> Dict[str, Any]:
    context_text = _safe_text(build_context(history))
    memory_hints = extract_last_known_info(history) or {}
    safe_memory_name_hint = _safe_text(memory_hints.get("name_hint")).strip()

    parsed.setdefault("items", [])
    parsed.setdefault("name", None)
    parsed.setdefault("phone", None)
    parsed.setdefault("address", {})
    parsed.setdefault("meta", {})

    parsed.update({
        "conversation_id": conversation_id,
        "messages": messages,
        "raw_message": "\n".join(messages),
        "temp_id": temp_id or trace_id,
        "timestamp": datetime.utcnow().isoformat()
    })

    if not parsed.get("phone"):
        phones = re.findall(r'0\d{9}', context_text)
        if phones:
            parsed["phone"] = phones[-1]

    if not isinstance(parsed.get("items"), list):
        parsed["items"] = []

    if not parsed.get("items"):
        algerian_products = ["سروال", "قميص", "تيشورت", "حذاء", "كاسكيط", "عباية", "خمار"]
        for line in context_text.split("\n"):
            clean_line = _safe_text(line).strip()
            if clean_line and any(word in clean_line for word in algerian_products):
                parsed["items"].append({"product": clean_line, "quantity": 1})

    if not parsed.get("name"):
        parsed["name"] = extract_name(context_text) or extract_name(safe_memory_name_hint)

    parsed["customer_name"] = parsed.get("name")

    loc = infer_location(context_text) or {}
    location_struct = {
        "province": _safe_text(loc.get("province")).strip() or None,
        "district": _safe_text(loc.get("district")).strip() or None,
        "area": _safe_text(loc.get("area")).strip() or None,
        "full": _safe_text(loc.get("detail")).strip() or None
    }

    if isinstance(parsed.get("address"), dict):
        for key in ["province", "district", "area", "full"]:
            if parsed["address"].get(key):
                location_struct[key] = parsed["address"][key]

    existing_address = parsed.get("address") if isinstance(parsed.get("address"), dict) else {}
    parsed["location"] = location_struct
    parsed["address"] = {
        "full": location_struct.get("full"),
        "province": location_struct.get("province"),
        "district": location_struct.get("district"),
        "area": location_struct.get("area"),
        "building": _safe_text(existing_address.get("building")).strip() or None,
        "door": _safe_text(existing_address.get("door")).strip() or None,
    }

    confidence_data = compute_confidence(parsed) or {}
    warnings = generate_warnings(parsed) or []

    parsed["meta"] = {
        "confidence": confidence_data.get("confidence", 0),
        "decision": confidence_data.get("decision", "review"),
        "field_confidence": confidence_data.get("field_confidence", {}),
        "warnings": warnings,
        "warnings_count": len(warnings),
        "trace_id": trace_id,
        "has_errors": len(warnings) > 0
    }

    identity = resolve_identity(parsed)
    decision_data = apply_decision(parsed) or {"action": "manual_review"}
    parsed["decision_data"] = {
        "confidence_score": confidence_data.get("confidence", 0),
        "missing_fields": confidence_data.get("missing_fields", []),
        "action": decision_data.get("action", "manual_review"),
        "needs_review": decision_data.get("action") in ["review", "manual_review"]
    }

    parsed["identity"] = identity
    parsed["needs_review"] = parsed["decision_data"]["needs_review"]
    parsed["warnings"] = warnings
    parsed["fingerprint"] = parsed.get("fingerprint") or generate_order_fingerprint(parsed)
    return parsed

# ================================
# 🧠 المحرك الرئيسي: RUN PIPELINE
# ================================

async def run_single_order_pipeline(order_input: Dict[str, Any]) -> Dict[str, Any]:
    messages = _normalize_messages(order_input.get("messages") or [])
    conversation_id = _safe_text(order_input.get("conversation_id")).strip() or "default"
    trace_id = _safe_text(order_input.get("trace_id")).strip() or str(uuid.uuid4())
    client_temp_id = _safe_text(order_input.get("temp_id")).strip() or None

    if not messages:
        raise ValueError("Order input must include non-empty messages")

    history = _build_history(messages, conversation_id, persist=True)
    log_step("📥 Incoming History", history, trace_id)

    try:
        parser_payload = await parse_conversation(
            messages=history,
            conversation_id=conversation_id,
            trace_id=trace_id
        )
        log_step("🧠 Parser Payload (Single)", parser_payload, trace_id)
    except Exception as e:
        logger.error("Parser Exception", extra={"error": str(e), "trace_id": trace_id})
        parser_payload = {"multi_orders": False, "order": {}}

    parser_orders = _extract_parser_orders(parser_payload)
    if len(parser_orders) != 1:
        raise ValueError("Single pipeline received non-single parser payload")

    parsed = _enrich_parsed_order(
        parser_orders[0],
        messages=messages,
        conversation_id=conversation_id,
        trace_id=trace_id,
        temp_id=client_temp_id,
        history=history
    )
    
    # 🧠 APPLY LEARNING (NEW)
    from app.services.parser_service import apply_learning_boost

    parsed = apply_learning_boost(
        parsed.get("raw_message", ""),
        parsed
    )
    
    log_step("📦 Final Parsed Object (Single)", parsed, trace_id)
    return parsed


async def run_bulk_order_pipeline(list_of_orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    bulk_results: List[Dict[str, Any]] = []

    for index, order_input in enumerate(list_of_orders):
        isolated_trace_id = str(uuid.uuid4())
        raw_messages = _normalize_messages(order_input.get("messages") or [])
        isolated_conversation_id = _safe_text(order_input.get("conversation_id")).strip() or "default"
        temp_id = _safe_text(order_input.get("temp_id")).strip() or isolated_trace_id

        if not raw_messages:
            bulk_results.append({
                "status": "error",
                "error": "messages are required",
                "raw": order_input
            })
            continue

        try:
            history = _build_history(raw_messages, f"{isolated_conversation_id}:bulk:{index}", persist=False)
            parser_payload = await parse_conversation(
                messages=history,
                conversation_id=None,
                trace_id=isolated_trace_id
            )
            parser_orders = _extract_parser_orders(parser_payload)
            if not parser_orders:
                raise ValueError("parser returned no valid order objects")

            for parser_order in parser_orders:
                parsed = _enrich_parsed_order(
                    parser_order,
                    messages=raw_messages,
                    conversation_id=isolated_conversation_id,
                    trace_id=isolated_trace_id,
                    temp_id=temp_id,
                    history=history
                )
                from app.services.parser_service import apply_learning_boost
                parsed = apply_learning_boost(parsed.get("raw_message", ""), parsed)

                created = create_order_from_parsed(
                    data=parsed,
                    decision_data=parsed.get("decision_data"),
                    trace_id=isolated_trace_id
                )
                clean_order = created["order"] if isinstance(created, dict) and "order" in created else created
                bulk_results.append({
                    "status": "success",
                    "order": format_order_for_frontend(clean_order)
                })
        except Exception as e:
            logger.error("Bulk order isolated failure", extra={"error": str(e), "trace_id": isolated_trace_id}, exc_info=True)
            bulk_results.append({
                "status": "error",
                "error": str(e),
                "raw": {
                    "messages": raw_messages,
                    "conversation_id": isolated_conversation_id,
                    "temp_id": temp_id
                }
            })

    return bulk_results


async def run_pipeline(
    messages: List[str],
    conversation_id: str,
    trace_id: str,
    client_temp_id: Optional[str] = None
):
    # Backward compatibility shim for existing integrations.
    return await run_single_order_pipeline({
        "messages": messages,
        "conversation_id": conversation_id,
        "trace_id": trace_id,
        "temp_id": client_temp_id
    })
    
# ================================
# 🚀 نقاط النهاية (Endpoints)
# ================================

@router.post("/orders/from-chat")
async def create_order_from_chat(data: ChatInput):
    """تحويل المحادثة إلى طلب مع حماية كاملة من التكرار"""
    trace_id = str(uuid.uuid4())
    clean_idempotency_store()
    idempotency_key = generate_idempotency_key(data.messages, data.conversation_id)

    with IDEMPOTENCY_LOCK:
        if idempotency_key in IDEMPOTENCY_STORE:
            cached = IDEMPOTENCY_STORE[idempotency_key]
            log_step("♻️ Idempotency Triggered", cached, trace_id)
            return {**cached["response"], "idempotent": True}
            

    try:
        parsed = await run_single_order_pipeline({
            "messages": data.messages,
            "conversation_id": data.conversation_id,
            "trace_id": trace_id
        })
        
        # ✅ FIX 4: استدعاء create_order_from_parsed مرة واحدة فقط بالبيانات الكاملة
        order = create_order_from_parsed(
            data=parsed,
            decision_data=parsed.get("decision_data"),
            trace_id=trace_id
        )

        clean_order = order["order"] if isinstance(order, dict) and "order" in order else order
        log_step("💾 Order Created (DB)", clean_order, trace_id)

        response_payload = {
            "success": True,
            "mode": "single",
            "orders": [format_order_for_frontend(clean_order)]
        }

        with IDEMPOTENCY_LOCK:
            IDEMPOTENCY_STORE[idempotency_key] = {
                "response": response_payload,
                "fingerprint": generate_order_fingerprint(parsed),
                "time": datetime.now()
            }

        log_event(event="order_pipeline_success", trace_id=trace_id, conversation_id=data.conversation_id, status="success", confidence=parsed["meta"]["confidence"])
        
        log_step("📤 Final Response", response_payload, trace_id)
        return response_payload

    except Exception as e:
        logger.error("CRITICAL PIPELINE ERROR", extra={"error": str(e), "trace_id": trace_id}, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal processing error")


@router.post("/orders/from-chat-bulk")
async def from_chat_bulk(payload: dict):
    """معالجة الرسائل المجمعة مع عزل كامل لكل طلب"""
    raw_messages = payload.get("messages", [])
    conversation_id = _safe_text(payload.get("conversation_id")).strip() or "default"

    if not isinstance(raw_messages, list) or not raw_messages:
        raise HTTPException(status_code=400, detail="Messages are required")

    order_inputs: List[Dict[str, Any]] = []
    for msg in raw_messages:
        if isinstance(msg, dict):
            content = _safe_text(msg.get("content")).strip()
            temp_id = _safe_text(msg.get("tempId")).strip() or str(uuid.uuid4())
        else:
            content = _safe_text(msg).strip()
            temp_id = str(uuid.uuid4())

        if not content:
            continue

        order_inputs.append({
            "messages": [content],
            "conversation_id": conversation_id,
            "temp_id": temp_id
        })

    if not order_inputs:
        raise HTTPException(status_code=400, detail="No valid message content provided")

    results = await run_bulk_order_pipeline(order_inputs)
    response_payload = {
        "success": True,
        "mode": "bulk",
        "orders": results
    }
    log_step("📤 Final Response (Bulk)", response_payload, str(uuid.uuid4()))
    return response_payload

@router.post("/orders/debug-parse")
async def debug_parse(data: ChatInput):
    trace_id = str(uuid.uuid4())
    try:
        parsed = await run_single_order_pipeline({
            "messages": data.messages,
            "conversation_id": data.conversation_id,
            "trace_id": trace_id
        })
        return {"success": True, "parsed": parsed, "trace_id": trace_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/learning/feedback")
def submit_feedback(data: FeedbackInput):
    case = store_learning_case(
        data.raw_message,
        data.parsed,
        data.corrected,
        data.confidence
    )

    # 🔥 NEW: log learning event
    log_event(
        event="learning_stored",
        trace_id=str(uuid.uuid4()),
        status="ok",
        meta={"raw": data.raw_message}
    )

    return {"success": True, "case": case}

@router.get("/learning/cases")
def list_learning_cases():
    cases = get_learning_cases()
    return {"count": len(cases), "data": cases}