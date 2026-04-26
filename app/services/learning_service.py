# app/services/learning_service.py

from __future__ import annotations

from datetime import datetime
from threading import RLock
from typing import Any, Dict, List

from app.core.database import generate_id

# 🧠 in-memory (لاحقاً MongoDB)
learning_db: Dict[str, Dict[str, Any]] = {}

# 🧠 index for fast lookup
learning_index: Dict[str, str] = {}

# 🛡️ concurrency guard
_LEARNING_LOCK = RLock()

# 🧱 storage schema version
SCHEMA_VERSION = 1

# 🎯 matching thresholds
EXACT_MATCH_SCORE = 1.0
BEST_MATCH_THRESHOLD = 0.5


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").lower().strip().split())


def _tokenize(value: Any) -> List[str]:
    text = _normalize_text(value)
    if not text:
        return []
    return [t for t in text.split(" ") if t]


def _build_case(
    *,
    case_id: str,
    raw_message: str,
    parsed: Dict[str, Any],
    corrected: Dict[str, Any],
    confidence: float,
) -> Dict[str, Any]:
    corrected = corrected if isinstance(corrected, dict) else {}
    parsed = parsed if isinstance(parsed, dict) else {}

    return {
        "id": case_id,
        "raw_message": raw_message,
        "raw_message_norm": _normalize_text(raw_message),
        "parsed": parsed,
        "corrected": corrected,
        "confidence": float(confidence or 0.0),
        "timestamp": datetime.now().isoformat(),
        # 🧠 Learning Fields
        "source": "developer",
        "fields_fixed": list(corrected.keys()),
        "is_applied": False,
        "pattern": {
            "tokens": _tokenize(raw_message),
            "schema_version": SCHEMA_VERSION,
        },
    }


def store_learning_case(
    raw_message: str,
    parsed: dict,
    corrected: dict,
    confidence: float,
):
    raw_message = str(raw_message or "").strip()
    if not raw_message:
        return None

    key = _normalize_text(raw_message)

    with _LEARNING_LOCK:
        # منع duplicate cases: نفس الرسالة تُحدَّث بدل إنشاء case جديد
        existing_case_id = learning_index.get(key)
        if existing_case_id and existing_case_id in learning_db:
            existing = learning_db[existing_case_id]

            existing["parsed"] = parsed if isinstance(parsed, dict) else {}
            existing["corrected"] = corrected if isinstance(corrected, dict) else {}
            existing["confidence"] = float(confidence or 0.0)
            existing["timestamp"] = datetime.now().isoformat()
            existing["fields_fixed"] = list((corrected or {}).keys())
            existing["raw_message"] = raw_message
            existing["raw_message_norm"] = key
            existing["pattern"] = {
                "tokens": _tokenize(raw_message),
                "schema_version": SCHEMA_VERSION,
            }
            existing["source"] = "developer"
            return existing

        case_id = generate_id()
        case = _build_case(
            case_id=case_id,
            raw_message=raw_message,
            parsed=parsed if isinstance(parsed, dict) else {},
            corrected=corrected if isinstance(corrected, dict) else {},
            confidence=confidence,
        )

        learning_db[case_id] = case
        learning_index[key] = case_id
        return case


def find_best_learning_match(text: str):
    text_norm = _normalize_text(text)
    if not text_norm:
        return None

    text_tokens = _tokenize(text_norm)
    if not text_tokens:
        return None

    best_case = None
    best_score = 0.0

    with _LEARNING_LOCK:
        # exact / near-exact first
        exact_case_id = learning_index.get(text_norm)
        if exact_case_id:
            exact_case = learning_db.get(exact_case_id)
            if exact_case:
                return exact_case

        for key, case_id in learning_index.items():
            case = learning_db.get(case_id)
            if not case:
                continue

            key_tokens = _tokenize(key)
            if not key_tokens:
                continue

            overlap = len(set(text_tokens) & set(key_tokens))
            union = len(set(text_tokens) | set(key_tokens))
            score = overlap / max(union, 1)

            # boost if one text fully contains the other
            if key in text_norm or text_norm in key:
                score = max(score, 0.9)

            if score > best_score and score >= BEST_MATCH_THRESHOLD:
                best_score = score
                best_case = case

    return best_case


def get_learning_cases():
    with _LEARNING_LOCK:
        return list(learning_db.values())


def mark_case_as_applied(case_id: str):
    if not case_id:
        return None

    with _LEARNING_LOCK:
        if case_id in learning_db:
            learning_db[case_id]["is_applied"] = True
            return learning_db[case_id]

    return None
