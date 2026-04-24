# app/services/usage_service.py
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

logger = logging.getLogger("usage_service")

usage_collection = None


def get_collection():
    global usage_collection

    if usage_collection is None:
        db = get_database()
        usage_collection = db["usage_logs"]

    return usage_collection


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

        logger.info("Usage indexes created")

    except Exception as e:
        logger.warning(f"Index creation failed: {e}")


def _utc_now():
    return datetime.now(timezone.utc)


def _truncate(value: Any, limit: int = 500):
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= limit else text[:limit]


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
    doc = {
        "event": event,
        "trace_id": trace_id or str(uuid4()),
        "conversation_id": conversation_id,
        "customer_id": customer_id,
        "order_id": order_id,
        "route": route,
        "source": source,
        "stage": stage,
        "status": status,
        "outcome": outcome,
        "duration_ms": duration_ms,
        "has_warning": has_warning,
        "auto_filled": auto_filled,
        "needs_review": needs_review,
        "messages_count": messages_count,
        "unique_messages_count": unique_messages_count,
        "items_count": items_count,
        "warnings_count": warnings_count,
        "confidence": confidence,
        "decision": decision,
        "error": _truncate(error, 1000),
        "timestamp": _utc_now(),
        "version": 1,
    }

    if meta is not None:
        doc["meta"] = meta

    if extra is not None:
        doc["extra"] = extra

    try:
        collection = get_collection()

        if collection is None:
            logger.warning("No DB - skipping log")
            return None

        result = collection.insert_one(doc)

        return str(result.inserted_id)
    except Exception as e:
        logger.warning(f"Usage log failed: {str(e)}")
        return None
