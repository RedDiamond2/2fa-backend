# app/services/context_service.py

from typing import List, Dict, Any
from datetime import datetime
import threading
import re

from app.core.database import conversations_collection

# =====================================
# ⚙️ CONFIG (Elite Production)
# =====================================
MAX_HISTORY = 20
CONTEXT_WINDOW = 10
MAX_STACK = 5

_CONTEXT_LOCK = threading.Lock()


# =====================================
# 🧠 SAFE NORMALIZATION (ANTI-CORRUPTION)
# =====================================
def _normalize_messages(messages: Any) -> List[str]:
    if not isinstance(messages, list):
        return []

    cleaned: List[str] = []
    for msg in messages:
        if msg is None:
            continue
        text = str(msg).strip()
        if text:
            cleaned.append(text)

    return cleaned


def _extract_message_text(msg: Any) -> str:
    if isinstance(msg, dict):
        return str(msg.get("text", "")).strip()
    return str(msg).strip()


def _load_existing_history(conversation_id: str) -> List[str]:
    if not conversation_id or conversations_collection is None:
        return []

    try:
        convo = conversations_collection.find_one({"id": conversation_id})
        if not convo:
            return []

        messages = convo.get("messages", [])
        if not isinstance(messages, list):
            return []

        cleaned = []
        for msg in messages:
            text = _extract_message_text(msg)
            if text:
                cleaned.append(text)

        return cleaned[-MAX_HISTORY:]
    except Exception:
        return []


# =====================================
# 📥 GET HISTORY (READ ONLY + SAFE)
# =====================================
def get_conversation_history(conversation_id: str) -> List[str]:
    return _load_existing_history(conversation_id)


# =====================================
# 💾 SAVE HISTORY (ISOLATED MUTATION)
# =====================================
def save_conversation(conversation_id: str, messages: List[Any]):
    if not conversation_id or conversations_collection is None:
        return

    try:
        incoming = _normalize_messages(messages)
        if not incoming:
            return

        with _CONTEXT_LOCK:
            existing_messages = _load_existing_history(conversation_id)

            # Preserve order, avoid duplicate re-appends at the tail
            tail_window = existing_messages[-5:] if existing_messages else []
            merged = list(existing_messages)

            for msg in incoming:
                if msg and msg not in tail_window:
                    merged.append(msg)
                    tail_window.append(msg)
                    tail_window = tail_window[-5:]

            trimmed = [
                {"text": msg, "timestamp": datetime.utcnow(), "type": "user"}
                for msg in merged[-MAX_HISTORY:]
            ]

            conversations_collection.update_one(
                {"id": conversation_id},
                {
                    "$set": {
                        "messages": trimmed,
                        "updated_at": datetime.utcnow(),
                    },
                    "$setOnInsert": {"created_at": datetime.utcnow()},
                },
                upsert=True,
            )
    except Exception:
        return


# =====================================
# 🧠 EXTRACT LAST KNOWN INFO (NO COUPLING)
# =====================================
def extract_last_known_info(history: List[str]) -> Dict[str, Any]:
    history = _normalize_messages(history)

    last_name = None
    last_location = None
    last_phone = None

    location_keywords = [
        "حي",
        "بلدية",
        "دار",
        "باب",
        "طريق",
        "وهران",
        "الجزائر",
        "سطيف",
        "عنابة",
        "قسنطينة",
    ]

    for msg in reversed(history[-MAX_HISTORY:]):
        msg_clean = msg.strip()

        # 📞 phone
        if not last_phone:
            digits = "".join(filter(str.isdigit, msg_clean))
            if len(digits) >= 8:
                if digits.startswith("213"):
                    digits = "0" + digits[3:]
                last_phone = digits

        # 📍 location
        if not last_location:
            if any(w in msg_clean for w in location_keywords):
                last_location = msg_clean

        # 👤 name
        if not last_name:
            words = msg_clean.split()
            if (
                1 <= len(words) <= 3
                and not any(c.isdigit() for c in msg_clean)
                and len(msg_clean) > 2
            ):
                last_name = msg_clean

        if last_name and last_location and last_phone:
            break

    identity = None
    if last_phone:
        identity = f"user_{last_phone}"
    elif last_name:
        identity = f"user_{last_name}"

    return {
        "name_hint": last_name,
        "location_hint": last_location,
        "phone_hint": last_phone,
        "identity_hint": identity,
    }


# =====================================
# 🧠 CONTEXT BUILDER (ANTI-CONTAMINATION)
# =====================================
def build_context(messages: List[str]) -> str:
    if not messages:
        return ""

    messages = _normalize_messages(messages)
    if not messages:
        return ""

    recent = messages[-CONTEXT_WINDOW:]

    context_parts = []
    last_product = None
    product_stack = []
    seen = set()

    for i, msg in enumerate(recent):
        msg = clean_message(msg)

        if not msg:
            continue

        # 🚫 noise filter
        if msg.lower() in ["ok", "okay", "merci", "شكرا", "تمام", "done", "ماشي"]:
            continue

        if msg in seen:
            continue
        seen.add(msg)

        weight = round((i + 1) / len(recent), 2) if recent else 1.0

        # 🛒 product
        if is_product(msg):
            last_product = msg
            if msg not in product_stack:
                product_stack.append(msg)

            if len(product_stack) > MAX_STACK:
                product_stack.pop(0)

            context_parts.append(f"[PRODUCT|w={weight}] {msg}")
            continue

        target = last_product or (product_stack[-1] if product_stack else None)

        # 🔢 quantity
        if is_quantity(msg) and target:
            context_parts.append(f"[QTY→{target}|w={weight}] {msg}")
            continue

        # ➕ continuation
        if is_continuation(msg) and target:
            context_parts.append(f"[UPDATE→{target}|w={weight}] {msg}")
            continue

        # 📍 location
        if any(
            w in msg for w in ["حي", "بلدية", "دار", "باب", "وهران", "سطيف", "الجزائر"]
        ):
            context_parts.append(f"[LOCATION|w={weight}] {msg}")
            continue

        # 📞 phone
        digits = "".join(filter(str.isdigit, msg))
        if len(digits) >= 8:
            if digits.startswith("213"):
                digits = "0" + digits[3:]
            context_parts.append(f"[PHONE|w={weight}] {digits}")
            continue

        context_parts.append(f"[{weight}] {msg}")

    # safe size cap
    joined = " || ".join(context_parts)
    if len(joined) > 4000:
        joined = joined[-4000:]

    return joined


# =====================================
# 🧹 UTILS
# =====================================
def clean_message(msg: str) -> str:
    msg = str(msg or "").strip().replace("\n", " ").replace("\t", " ")
    msg = re.sub(r"\s+", " ", msg)
    return msg


def is_product(msg: str) -> bool:
    keywords = [
        "تريكو",
        "تيش",
        "سروال",
        "صباط",
        "حذاء",
        "قميص",
        "فستان",
        "جلباب",
        "خمار",
        "عباءة",
    ]
    return any(k in msg for k in keywords)


def is_quantity(msg: str) -> bool:
    qty_words = ["زوج", "ثلاثة", "اربعة", "خمسة", "حبة", "قطعة", "عدد"]
    return any(c.isdigit() for c in msg) or any(k in msg for k in qty_words)


def is_continuation(msg: str) -> bool:
    keywords = ["زيد", "اضف", "زيدلي", "كمان", "ايضا", "حتى"]
    return any(k in msg for k in keywords)
