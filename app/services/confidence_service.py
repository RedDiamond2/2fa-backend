# app/services/confidence_service.py

from typing import Any, Dict, List

# ⚖️ weights (قابلة للتعديل)
WEIGHTS = {
    "items": 0.25,
    "quantity": 0.10,
    "phone": 0.20,
    "location": 0.20,
    "name": 0.10,
    "address": 0.15,
}

# 🎯 thresholds (ثابتة ومستقرة)
AUTO_THRESHOLD = 0.85
REVIEW_THRESHOLD = 0.60

# 🛡️ penalties
MISSING_PHONE_PENALTY = 0.15
MISSING_ITEMS_PENALTY = 0.25
WARNINGS_PENALTY_PER_ITEM = 0.05
MAX_WARNINGS_PENALTY = 0.20


# =====================================
# 🧹 SAFE UTILS
# =====================================
def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(value, high))


def _is_truthy_item(item: Any) -> bool:
    return isinstance(item, dict) and bool(item.get("product") or item.get("name"))


# =====================================
# 🛒 ITEMS SCORE
# =====================================
def score_items(items: List[Dict[str, Any]]) -> float:
    if not items or not isinstance(items, list):
        return 0.0

    valid_items = [
        item for item in items if isinstance(item, dict) and _is_truthy_item(item)
    ]
    if not valid_items:
        return 0.0

    score = 0.0

    for item in valid_items:
        # strong signal: product exists
        if item.get("product") or item.get("name"):
            score += 0.5

        # supporting signals
        if item.get("color"):
            score += 0.2
        if item.get("size"):
            score += 0.2
        if item.get("quantity") is not None:
            score += 0.1

    # normalize by number of valid items
    return _clamp(score / max(len(valid_items), 1))


# =====================================
# 🔢 QUANTITY SCORE
# =====================================
def score_quantity(items: List[Dict[str, Any]]) -> float:
    if not items or not isinstance(items, list):
        return 0.0

    valid = 0
    considered = 0

    for item in items:
        if not isinstance(item, dict):
            continue

        considered += 1
        qty = item.get("quantity", 0)

        if isinstance(qty, bool):
            continue

        try:
            qty_int = int(qty)
        except (TypeError, ValueError):
            continue

        if 1 <= qty_int <= 10:
            valid += 1

    if considered == 0:
        return 0.0

    return _clamp(valid / considered)


# =====================================
# 📞 PHONE SCORE
# =====================================
def score_phone(phone: Any) -> float:
    if not phone:
        return 0.0

    phone = str(phone).strip()
    digits = "".join(ch for ch in phone if ch.isdigit())

    # Algeria local mobile format: 0XXXXXXXXX (10 digits)
    if len(digits) == 10 and digits.startswith("0"):
        return 1.0

    # good enough signal
    if len(digits) >= 8:
        return 0.5

    return 0.0


# =====================================
# 📍 LOCATION SCORE
# =====================================
def score_location(location: Any) -> float:
    if not location:
        return 0.0

    if isinstance(location, str):
        location = location.strip().lower()

        keywords = [
            "حي",
            "بلدية",
            "ولاية",
            "مسكن",
            "عمارة",
            "بناية",
            "باب",
            "رقم",
        ]

        if any(k in location for k in keywords):
            return 0.8

        return 0.5

    if isinstance(location, dict):
        if location.get("confidence") is not None:
            try:
                return _clamp(float(location["confidence"]))
            except Exception:
                return 0.5

        score = 0.0
        if location.get("province"):
            score += 0.4
        if location.get("district"):
            score += 0.3
        if location.get("area"):
            score += 0.2
        if location.get("detail") or location.get("full"):
            score += 0.1

        return _clamp(score)

    return 0.0


# =====================================
# 🏠 ADDRESS SCORE
# =====================================
def score_address(address: Any) -> float:
    if not address:
        return 0.0

    if isinstance(address, str):
        return 0.3 if address.strip() else 0.0

    score = 0.0

    if isinstance(address, dict):
        if address.get("province"):
            score += 0.3
        if address.get("district"):
            score += 0.3
        if address.get("area"):
            score += 0.2
        if address.get("full"):
            score += 0.2

    return _clamp(score)


# =====================================
# 👤 NAME SCORE
# =====================================
def score_name(name: Any) -> float:
    if not name or name in ["⚠️", "Unknown"]:
        return 0.0

    name = str(name).strip()

    if len(name) < 3:
        return 0.5

    # names with 1-3 tokens are usually decent
    token_count = len(name.split())
    if 1 <= token_count <= 3:
        return 1.0

    return 0.8


# =====================================
# 🧠 DECISION CONTRACT
# =====================================
def _derive_decision(total: float, warnings: List[Any]) -> Dict[str, str]:
    """
    Strict decision contract:
    - auto / review / manual only
    - reason is stable and deterministic
    """
    if total >= AUTO_THRESHOLD and not warnings:
        return {
            "decision": "auto",
            "reason": "high_confidence_no_warnings",
        }

    if total >= REVIEW_THRESHOLD:
        return {
            "decision": "review",
            "reason": "medium_confidence",
        }

    return {
        "decision": "manual",
        "reason": "low_confidence_or_warnings_present",
    }


# =====================================
# 🧠 MAIN CONFIDENCE ENGINE
# =====================================
def compute_confidence(parsed: Dict[str, Any]) -> Dict[str, Any]:
    parsed = _safe_dict(parsed)

    items = _safe_list(parsed.get("items", []))
    phone = parsed.get("phone")
    location = parsed.get("location", {})
    address = parsed.get("address", {})
    name = parsed.get("name")

    meta = _safe_dict(parsed.get("meta"))
    warnings = _safe_list(meta.get("warnings"))

    scores = {
        "items": score_items(items),
        "quantity": score_quantity(items),
        "phone": score_phone(phone),
        "location": score_location(location),
        "name": score_name(name),
        "address": score_address(address),
    }

    total = 0.0
    for k, v in scores.items():
        total += v * WEIGHTS.get(k, 0.0)

    # =====================================
    # ⚠️ PENALTIES (Commercial Intelligence)
    # =====================================
    if not phone:
        total -= MISSING_PHONE_PENALTY

    if not items:
        total -= MISSING_ITEMS_PENALTY

    if warnings:
        total -= min(MAX_WARNINGS_PENALTY, len(warnings) * WARNINGS_PENALTY_PER_ITEM)

    total = _clamp(total)

    decision_data = _derive_decision(total, warnings)

    field_confidence = {
        "name": scores["name"],
        "phone": scores["phone"],
        "items": scores["items"],
        "quantity": scores["quantity"],
        "location": scores["location"],
        "address": scores["address"],
    }

    return {
        "confidence": round(total, 2),
        "decision": decision_data["decision"],
        "reason": decision_data["reason"],
        "breakdown": scores,
        "field_confidence": field_confidence,
        "missing_fields": [
            field
            for field, value in {
                "name": name,
                "phone": phone,
                "items": items,
                "location": location,
                "address": address,
            }.items()
            if not value
        ],
    }
