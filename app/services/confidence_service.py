# app/services/confidence_service.py

from typing import Dict

# ⚖️ weights (قابلة للتعديل)
WEIGHTS = {
    "items": 0.25,
    "quantity": 0.10,
    "phone": 0.20,
    "location": 0.20,
    "name": 0.10,
    "address": 0.15
}

def score_items(items):
    if not items:
        return 0

    score = 0

    for item in items:
        if item.get("product"):
            score += 0.5
        if item.get("color"):
            score += 0.2
        if item.get("size"):
            score += 0.2
        if item.get("quantity"):
            score += 0.1

    return min(score / len(items), 1)

def score_quantity(items):
    if not items:
        return 0

    valid = 0
    for item in items:
        qty = item.get("quantity", 0)
        if isinstance(qty, int) and 1 <= qty <= 10:
            valid += 1

    return valid / len(items)


def score_phone(phone):
    if not phone:
        return 0
    if len(phone) == 10 and phone.startswith("0"):
        return 1
    return 0.5


def score_location(location):
    if not location:
        return 0

    if isinstance(location, str):
        location = location.strip().lower()
        if any(k in location for k in ["حي", "بلدية", "ولاية", "مسكن", "عمارة", "بناية", "باب", "رقم"]):
            return 0.8
        return 0.5

    # 🔥 استخدام confidence إذا موجود
    if isinstance(location, dict) and location.get("confidence") is not None:
        return location["confidence"]

    score = 0
    if location.get("province"):
        score += 0.4
    if location.get("district"):
        score += 0.3
    if location.get("area"):
        score += 0.2
    if location.get("detail"):
        score += 0.1

    return min(score, 1)

def score_address(address):
    if not address:
        return 0

    if isinstance(address, str):
        return 0.3

    score = 0

    if address.get("province"):
        score += 0.3
    if address.get("district"):
        score += 0.3
    if address.get("area"):
        score += 0.2
    if address.get("full"):
        score += 0.2

    return min(score, 1)
    
def score_name(name):
    if not name or name in ["⚠️", "Unknown"]:
        return 0
    if len(name) < 3:
        return 0.5
    return 1


def compute_confidence(parsed: Dict) -> Dict:
    items = parsed.get("items", [])
    phone = parsed.get("phone")
    location = parsed.get("location", {})
    address = parsed.get("address", {})
    name = parsed.get("name")
    warnings = parsed.get("meta", {}).get("warnings", [])

    scores = {
    "items": score_items(items),
    "quantity": score_quantity(items),
    "phone": score_phone(phone),
    "location": score_location(location),
    "name": score_name(name),
    "address": score_address(address)
    }

    total = 0
    for k, v in scores.items():
        total += v * WEIGHTS[k]
    
    # =====================================
    # ⚠️ PENALTIES (Commercial Intelligence)
    # =====================================
    if not phone:
        total -= 0.15

    if not items:
        total -= 0.25

    if warnings:
        total -= min(0.2, len(warnings) * 0.05)

    total = max(0, min(total, 1))


    # 🎯 decision logic
    if total >= 0.85 and not warnings:
        decision = "auto"
    elif total >= 0.60:
        decision = "review"
    else:
        decision = "manual"

    field_confidence = {
        "name": scores["name"],
        "phone": scores["phone"],
        "items": scores["items"],
        "quantity": scores["quantity"],
        "location": scores["location"],
        "address": scores["address"]
    }

    return {
        "confidence": round(total, 2),
        "decision": decision,
        "breakdown": scores,
        "field_confidence": field_confidence
    }