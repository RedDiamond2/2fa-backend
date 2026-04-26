# app/services/parser_service.py

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from app.schemas.parser_schema import Address, Item, ParsedOrder
from app.services.location_service import infer_location
from app.services.payment_service import detect_payment
from app.services.usage_service import log_event
from app.utils.phone_utils import clean_phone

logger = logging.getLogger("parser_service")

# ================================
# 🧠 CONSTANTS
# ================================
NUMBER_MAP = {
    "واحد": 1,
    "وحدة": 1,
    "زوج": 2,
    "جوج": 2,
    "ثلاثة": 3,
    "ثلاث": 3,
    "اربعة": 4,
    "خمسة": 5,
    "ستة": 6,
    "سبعة": 7,
    "ثمانية": 8,
}

PRODUCTS_MAP = {
    "تريكو": ["تريكو", "تيشرت", "تيش", "tshirt", "تيشورت", "تيشور"],
    "صباط": ["صباط", "حذاء", "شوز", "سباط"],
    "قميص": ["قميص", "شميز", "chemise"],
    "سروال": ["سروال", "جين", "جينز", "pantalon"],
    "فستان": ["فستان"],
}

COLORS = {
    "نوار": "أسود",
    "اسود": "أسود",
    "أبيض": "أبيض",
    "بيض": "أبيض",
    "حمر": "أحمر",
    "احمر": "أحمر",
    "جون": "أصفر",
    "اصفر": "أصفر",
    "ازرق": "أزرق",
    "أزرق": "أزرق",
}

SIZES = ["xs", "s", "m", "l", "xl", "xxl", "2xl", "3xl"]

NAME_STOPWORDS = [
    "السلام",
    "عليكم",
    "مرحبا",
    "نحب",
    "حاب",
    "نحتاج",
    "بغيت",
    "زيدني",
    "كاين",
    "واحد",
    "زوج",
    "خويا",
    "يا",
    "ألو",
]


# ================================
# 🧹 UTILS
# ================================
def normalize(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def safe_infer_location(text: str) -> Dict[str, Any]:
    try:
        return infer_location(text) or {}
    except Exception as e:
        logger.error(f"LOCATION ERROR: {e}")
        return {}


# ================================
# 🧠 INTENT
# ================================
def detect_intent(text: str) -> str:
    text = normalize(text)
    if "احذف" in text or "نحي" in text or "الغاء" in text:
        return "remove"
    if "بدل" in text or "غير" in text or "تغيير" in text:
        return "update"
    if "زيد" in text or "اضف" in text:
        return "add"
    if "أكد" in text or "نأكد" in text or "confirm" in text:
        return "confirm"
    return "new"


# ================================
# 🔢 NUMBER
# ================================
def classify_number(num: str) -> Dict[str, Any]:
    try:
        n = int(num)
    except (TypeError, ValueError):
        return {"type": "ignore", "value": None}

    # phone-like numbers (DZ local or with country prefix)
    if len(num) in [9, 10, 12]:
        return {"type": "phone", "value": clean_phone(num)}

    if 1 <= n <= 100:
        return {"type": "quantity", "value": n}

    return {"type": "ignore", "value": None}


def extract_phone(text: str) -> Optional[str]:
    for m in re.findall(r"\d+", text or ""):
        c = classify_number(m)
        if c["type"] == "phone":
            return c["value"]
    return None


# ================================
# 👤 NAME EXTRACTION (RAW ONLY)
# ================================
def extract_name(text: str) -> Optional[str]:
    text = (text or "").strip()
    if not text:
        return None

    # explicit phrases only — no guessing fallback
    match = re.search(
        r"(?:^|\n)(?:الاسم[:：]?\s*|اسمي\s+|أنا\s+|انا\s+|معاك\s+)([^\n\d]+)", text
    )
    if match:
        candidate = match.group(1).strip()
        if candidate and candidate not in NAME_STOPWORDS:
            return candidate

    # name followed by phone
    match = re.search(r"^([^\d\n]+?)\s+0\d{8,11}", text)
    if match:
        candidate = match.group(1).strip()
        if candidate and candidate not in NAME_STOPWORDS:
            return candidate

    return None


# ================================
# 🧠 PRODUCT SAFE MATCH
# ================================
def detect_product(word: str) -> Optional[str]:
    word = _safe_text(word).strip()
    if not word:
        return None

    for key, variants in PRODUCTS_MAP.items():
        # exact match
        if word in variants:
            return key

        # safe fuzzy (NO truncation match)
        for v in variants:
            if len(word) > 3 and len(v) > 3:
                if word == v:
                    return key
                if word in v and len(word) / len(v) > 0.75:
                    return key

    return None


# ================================
# 📦 SEGMENTATION (SAFE "و")
# ================================
def segment_items_by_connector(text: str) -> List[str]:
    if not text:
        return []

    parts = re.split(r"\s+و\s+", text)
    return [p.strip() for p in parts if p.strip()]


# ================================
# 📦 ITEMS EXTRACTION (STABLE)
# ================================
def extract_items(text: str) -> List[Dict[str, Any]]:
    if not text:
        return []

    segments = segment_items_by_connector(text)
    results: List[Dict[str, Any]] = []

    for seg in segments:
        words = normalize(seg).split()
        if not words:
            continue

        item: Dict[str, Any] = {
            "product": None,
            "quantity": 1,
            "color": None,
            "size": None,
        }

        # qty
        if words[0].isdigit():
            try:
                item["quantity"] = int(words[0])
            except (TypeError, ValueError):
                item["quantity"] = 1
        elif words[0] in NUMBER_MAP:
            item["quantity"] = NUMBER_MAP[words[0]]

        # scan words
        product_words = []

        for w in words:
            if w in COLORS:
                item["color"] = COLORS[w]
                continue

            if w in SIZES:
                item["size"] = w.upper()
                continue

            if detect_product(w):
                product_words.append(w)

        if product_words:
            item["product"] = " ".join(product_words)
        else:
            continue

        # hard guard
        if item["quantity"] < 1:
            item["quantity"] = 1
        if item["quantity"] > 20:
            item["quantity"] = 20

        results.append(item)

    return results


def merge_similar_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not items:
        return []

    merged: List[Dict[str, Any]] = []

    for i in items:
        if not isinstance(i, dict):
            continue

        found = False
        for m in merged:
            if (
                m.get("product") == i.get("product")
                and m.get("color") == i.get("color")
                and m.get("size") == i.get("size")
            ):
                try:
                    m["quantity"] = int(m.get("quantity", 1)) + int(
                        i.get("quantity", 1)
                    )
                except (TypeError, ValueError):
                    m["quantity"] = m.get("quantity", 1)
                found = True
                break

        if not found:
            merged.append(i.copy())

    return merged


# ================================
# 🧩 LOCATION / ADDRESS BUILDERS
# ================================
def _build_location_struct(loc: Dict[str, Any], raw_text: str = "") -> Dict[str, Any]:
    loc = loc or {}
    location_struct = {
        "province": _safe_text(loc.get("province")).strip() or None,
        "district": _safe_text(loc.get("district")).strip() or None,
        "area": _safe_text(loc.get("area")).strip() or None,
        "building": _safe_text(loc.get("building")).strip() or None,
        "door": _safe_text(loc.get("door")).strip() or None,
        "detail": _safe_text(loc.get("detail")).strip() or None,
        "confidence": loc.get("confidence")
        if isinstance(loc.get("confidence"), (int, float))
        else 0,
        "location": loc.get("location"),
    }

    parts = []
    if location_struct["province"]:
        parts.append(location_struct["province"])
    if location_struct["district"]:
        parts.append(location_struct["district"])
    if location_struct["area"]:
        parts.append(location_struct["area"])
    if location_struct["building"]:
        parts.append(f"عمارة {location_struct['building']}")
    if location_struct["door"]:
        parts.append(f"باب {location_struct['door']}")

    if not location_struct["detail"]:
        location_struct["detail"] = " - ".join(parts) if parts else None

    if not location_struct["location"]:
        location_struct["location"] = (
            location_struct["area"]
            or location_struct["district"]
            or location_struct["province"]
            or None
        )

    # fallback if current text contains a clear location phrase
    if not any(
        [
            location_struct["province"],
            location_struct["district"],
            location_struct["area"],
        ]
    ):
        m = re.search(r"(حي\s*\d+\s*مسكن)", normalize(raw_text))
        if m:
            location_struct["area"] = m.group(1)
            location_struct["location"] = m.group(1)
            location_struct["confidence"] = max(
                float(location_struct["confidence"] or 0), 0.1
            )

    return location_struct


def _build_address_struct(
    location_struct: Dict[str, Any], existing_address: Any = None
) -> Dict[str, Any]:
    existing_address = existing_address if isinstance(existing_address, dict) else {}
    return {
        "full": _safe_text(
            existing_address.get("full") or location_struct.get("detail")
        ).strip()
        or None,
        "province": _safe_text(
            existing_address.get("province") or location_struct.get("province")
        ).strip()
        or None,
        "district": _safe_text(
            existing_address.get("district") or location_struct.get("district")
        ).strip()
        or None,
        "area": _safe_text(
            existing_address.get("area") or location_struct.get("area")
        ).strip()
        or None,
        "building": _safe_text(
            existing_address.get("building") or location_struct.get("building")
        ).strip()
        or None,
        "door": _safe_text(
            existing_address.get("door") or location_struct.get("door")
        ).strip()
        or None,
    }


def _coerce_item_dicts(items: Any) -> List[Dict[str, Any]]:
    safe_items: List[Dict[str, Any]] = []
    if not isinstance(items, list):
        return safe_items

    for item in items:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        if isinstance(item, dict):
            safe_items.append(item)

    return safe_items


def _finalize_order(parsed: Dict[str, Any]) -> Dict[str, Any]:
    safe = dict(parsed or {})

    # sanitize items
    safe_items = _coerce_item_dicts(safe.get("items", []))
    safe["items"] = [Item(**i) for i in safe_items if isinstance(i, dict)]

    # sanitize address
    address_data = safe.get("address")
    if hasattr(address_data, "model_dump"):
        address_data = address_data.model_dump()
    if not isinstance(address_data, dict):
        address_data = {}

    try:
        safe["address"] = Address(**address_data)
    except Exception:
        safe["address"] = Address(full=_safe_text(address_data.get("full")))

    # normalize meta
    meta = safe.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    safe["meta"] = meta

    # final schema
    try:
        return ParsedOrder(**safe).model_dump()
    except Exception:
        # fallback raw dict for resilience
        safe["items"] = [
            i.model_dump() if hasattr(i, "model_dump") else i
            for i in safe.get("items", [])
        ]
        safe["address"] = (
            safe["address"].model_dump()
            if hasattr(safe.get("address"), "model_dump")
            else safe.get("address")
        )
        return safe


# ================================
# 🧩 MULTI ORDER DETECTION (SAFE)
# ================================
def split_orders(messages: List[str]) -> List[List[str]]:
    messages = [m for m in messages if _safe_text(m).strip()]
    if not messages:
        return []

    full_text = "\n".join(messages)

    # conservative multi-order detection
    separators = [
        r"\n\s*\n",
        r"\s+---\s+",
        r"\bطلب\s+ثاني\b",
        r"\border\s+2\b",
        r"\border\s+two\b",
    ]

    if not any(re.search(p, full_text, flags=re.IGNORECASE) for p in separators):
        return [messages]

    chunks = re.split(
        r"\n\s*\n|\s+---\s+|\bطلب\s+ثاني\b|\border\s+2\b|\border\s+two\b",
        full_text,
        flags=re.IGNORECASE,
    )
    batches: List[List[str]] = []
    for chunk in chunks:
        lines = [line.strip() for line in chunk.split("\n") if line.strip()]
        if lines:
            batches.append(lines)

    return batches if batches else [messages]


# ================================
# 🏆 MAIN PARSER (EXTRACTION ONLY)
# ================================
async def parse_conversation(
    messages: List[str],
    conversation_id: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        messages = [_safe_text(m).strip() for m in messages if _safe_text(m).strip()]
        if len(messages) > 20:
            messages = messages[-20:]

        if not messages:
            return {
                "multi_orders": False,
                "order": {
                    "status": "empty",
                    "items": [],
                    "meta": {"trace_id": trace_id, "conversation_id": conversation_id},
                },
            }

        # conservative multi-order handling
        batches = split_orders(messages)
        if len(batches) > 1:
            results = await asyncio.gather(
                *[
                    parse_conversation(batch, conversation_id, trace_id)
                    for batch in batches
                ],
                return_exceptions=True,
            )

            valid_orders = []
            for result in results:
                if isinstance(result, Exception):
                    continue
                if not isinstance(result, dict):
                    continue
                if result.get("multi_orders") is True and isinstance(
                    result.get("orders"), list
                ):
                    valid_orders.extend(
                        [o for o in result["orders"] if isinstance(o, dict)]
                    )
                elif isinstance(result.get("order"), dict):
                    valid_orders.append(result["order"])

            if valid_orders:
                return {"multi_orders": True, "orders": valid_orders}

            return {
                "multi_orders": True,
                "orders": [
                    {
                        "status": "error",
                        "items": [],
                        "meta": {"error": "All orders failed"},
                    }
                ],
            }

        text = " ".join(messages)

        # raw extraction only
        intent = detect_intent(text)
        name = extract_name(text)
        phone = extract_phone(text)

        # location
        loc = safe_infer_location(text)
        location_struct = _build_location_struct(loc, raw_text=text)
        address_struct = _build_address_struct(location_struct)

        # items
        items = extract_items(text)
        items = merge_similar_items(items)

        # raw structural hint only — not a decision system
        status = "draft" if items else "needs_input"

        parsed: Dict[str, Any] = {
            "intent": intent,
            "name": name,
            "customer_name": name,
            "phone": phone,
            "location": location_struct,
            "address": address_struct,
            "items": items,
            "status": status,
            "needs_review": False,
            "messages": messages,
            "raw_message": "\n".join(messages),
            "meta": {
                "trace_id": trace_id,
                "conversation_id": conversation_id,
                "raw_items_count": len(items),
                "raw_extraction": True,
            },
        }

        # payment is raw extraction too
        payment = detect_payment(text)
        if payment:
            parsed["payment_type"] = payment.get("type")
            parsed["payment_value"] = payment.get("value")
            parsed["payment_status"] = (
                "cod" if payment.get("type") == "COD" else "unpaid"
            )

        # keep parsed output raw and structured only
        log_event(
            event="parser_completed",
            trace_id=trace_id,
            conversation_id=conversation_id,
            status="ok",
            items_count=len(items),
            meta={
                "intent": intent,
                "has_name": bool(name),
                "has_phone": bool(phone),
                "raw_extraction": True,
            },
        )

        return {
            "multi_orders": False,
            "order": _finalize_order(parsed),
        }

    except Exception as e:
        log_event(
            event="parser_error",
            trace_id=trace_id,
            conversation_id=conversation_id,
            status="error",
            meta={"error": str(e)},
        )
        logger.error(f"PARSER CRASH: {e}", exc_info=True)
        return {
            "multi_orders": False,
            "order": {
                "status": "error",
                "items": [],
                "meta": {"error": str(e), "fallback": True},
            },
        }
