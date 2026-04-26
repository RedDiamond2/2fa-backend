# app/services/usage_service.py

import logging
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict, Optional
from uuid import uuid4

from app.core.database import get_database

logger = logging.getLogger("usage_service")

usage_collection = None
_USAGE_LOCK = RLock()


# =====================================
# 🗄️ COLLECTION HANDLER
# =====================================
def get_collection():
    global usage_collection

    if usage_collection is None:
        db = get_database()
        if db is None:
            return None
        usage_collection = db["usage_logs"]

    return usage_collection


# =====================================
# 📊 INDEXES
# =====================================
def ensure_usage_indexes():
    collection = get_collection()

    if collection is None:
        logger.warning("MongoDB not connected - skipping index creation")
        return

    try:
        collection.create_index([("timestamp", -1)])
        collection.create_index([("event", 1), ("timestamp", -1)])
        collection.create_index([("trace_id", 1), ("timestamp", -1)])
        collection.create_index([("conversation_id", 1), ("timestamp", -1)])
        collection.create_index([("customer_id", 1), ("timestamp", -1)])
        collection.create_index([("order_id", 1), ("timestamp", -1)])
        collection.create_index([("status", 1), ("timestamp", -1)])
        collection.create_index([("decision", 1), ("timestamp", -1)])
        logger.info("Usage indexes created successfully")
    except Exception as e:
        logger.warning(f"Index creation failed: {e}")


# =====================================
# ⏱️ UTILS
# =====================================
def _utc_now():
    return datetime.now(timezone.utc)


def _truncate(value: Any, limit: int = 500):
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= limit else text[:limit]


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalize_optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# =====================================
# 🧠 MAIN LOGGER (PRODUCTION GRADE)
# =====================================
def log_event(
    event: str,
    *,
    trace_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    order_id: Optional[str] = None,
    route: Optional[str] = None,
    source: Optional[str] = None,
    stage: Optional[str] = None,
    status: Optional[str] = None,
    outcome: Optional[str] = None,
    duration_ms: Optional[int] = None,
    has_warning: bool = False,
    auto_filled: bool = False,
    needs_review: bool = False,
    messages_count: Optional[int] = None,
    unique_messages_count: Optional[int] = None,
    items_count: Optional[int] = None,
    warnings_count: Optional[int] = None,
    confidence: Optional[float] = None,
    decision: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> Optional[str]:
    event = _normalize_optional_text(event) or "unknown_event"

    doc = {
        "event": event,
        "trace_id": _normalize_optional_text(trace_id) or str(uuid4()),
        "conversation_id": _normalize_optional_text(conversation_id),
        "customer_id": _normalize_optional_text(customer_id),
        "order_id": _normalize_optional_text(order_id),
        "route": _normalize_optional_text(route),
        "source": _normalize_optional_text(source),
        "stage": _normalize_optional_text(stage),
        "status": _normalize_optional_text(status),
        "outcome": _normalize_optional_text(outcome),
        "duration_ms": duration_ms if isinstance(duration_ms, int) else None,
        "has_warning": bool(has_warning),
        "auto_filled": bool(auto_filled),
        "needs_review": bool(needs_review),
        "messages_count": messages_count if isinstance(messages_count, int) else None,
        "unique_messages_count": unique_messages_count
        if isinstance(unique_messages_count, int)
        else None,
        "items_count": items_count if isinstance(items_count, int) else None,
        "warnings_count": warnings_count if isinstance(warnings_count, int) else None,
        "confidence": confidence if isinstance(confidence, (int, float)) else None,
        "decision": _normalize_optional_text(decision),
        "error": _truncate(error, 1000),
        "timestamp": _utc_now(),
        "version": 1,
    }

    safe_meta = _safe_dict(meta)
    safe_extra = _safe_dict(extra)

    if safe_meta:
        doc["meta"] = safe_meta

    if safe_extra:
        doc["extra"] = safe_extra

    try:
        with _USAGE_LOCK:
            collection = get_collection()

            if collection is None:
                logger.warning("No DB - skipping log")
                return None

            result = collection.insert_one(doc)
            return str(result.inserted_id)

    except Exception as e:
        logger.warning(f"Usage log failed: {e}")
        return None
