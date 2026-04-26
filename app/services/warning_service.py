# app/services/warning_service.py

from typing import List, Dict, Any


# =====================================
# 🚨 WARNING ENGINE (ONE PASS SAFE)
# =====================================


def generate_warnings(parsed: Dict[str, Any]) -> List[str]:
    """
    Generate intelligent warnings based on parsed order data.

    الهدف:
    - كشف النواقص
    - كشف الأخطاء
    - دعم القرار بدون side effects
    """

    warnings = set()

    # =====================================
    # 🧠 SAFE EXTRACTION (ANTI-CRASH)
    # =====================================

    items = parsed.get("items") or []
    phone = parsed.get("phone")
    name = parsed.get("name")
    location = parsed.get("location")
    address = parsed.get("address") or {}
    meta = parsed.get("meta") or {}

    # =====================================
    # 🛒 ITEMS VALIDATION
    # =====================================

    if not items:
        warnings.add("no_items")

    else:
        for item in items:
            if not isinstance(item, dict):
                warnings.add("invalid_item_structure")
                continue

            product = item.get("product")

            if not product:
                warnings.add("invalid_item")

            qty = item.get("quantity", 1)

            if not isinstance(qty, (int, float)):
                warnings.add("invalid_quantity_type")
            else:
                if qty <= 0:
                    warnings.add("invalid_quantity")
                elif qty > 5:
                    warnings.add("suspicious_quantity")

    # =====================================
    # 📞 PHONE VALIDATION
    # =====================================

    if not phone:
        warnings.add("missing_phone")

    else:
        if not isinstance(phone, str):
            warnings.add("invalid_phone")
        else:
            clean_phone = phone.strip()

            if not clean_phone.isdigit():
                warnings.add("invalid_phone")
            elif len(clean_phone) != 10:
                warnings.add("invalid_phone")

    # =====================================
    # 👤 NAME VALIDATION
    # =====================================

    if not name or name in ["⚠️", "Unknown", "???"]:
        warnings.add("missing_name")

    else:
        if not isinstance(name, str):
            warnings.add("invalid_name")
        else:
            clean_name = name.strip()

            if len(clean_name) < 3:
                warnings.add("weak_name")

            if clean_name.isdigit():
                warnings.add("invalid_name")

    # =====================================
    # 📍 LOCATION VALIDATION
    # =====================================

    if not location:
        warnings.add("missing_location")

    elif isinstance(location, dict):
        province = location.get("province")

        if not province:
            warnings.add("missing_location")

        confidence = location.get("confidence")

        if isinstance(confidence, (int, float)) and confidence < 0.5:
            warnings.add("weak_location")

    elif isinstance(location, str):
        normalized = location.strip()

        if not normalized:
            warnings.add("missing_location")
        else:
            keywords = ["حي", "بلدية", "ولاية", "مسكن", "عمارة", "بناية", "باب", "رقم"]

            if not any(k in normalized for k in keywords):
                province = address.get("province")

                if not (province and (address.get("area") or address.get("district"))):
                    warnings.add("invalid_location_format")

    else:
        warnings.add("invalid_location_format")

    # =====================================
    # 🏠 ADDRESS VALIDATION
    # =====================================

    if not address or not isinstance(address, dict):
        warnings.add("missing_address")

    else:
        full = address.get("full")

        if not full:
            warnings.add("missing_address")

        else:
            if not address.get("district") and not address.get("area"):
                warnings.add("weak_address")

            if isinstance(full, str) and len(full.strip()) < 5:
                warnings.add("weak_address")

    # =====================================
    # 🔁 DUPLICATE ITEMS
    # =====================================

    seen = set()

    for item in items:
        if not isinstance(item, dict):
            continue

        key = (
            item.get("product"),
            item.get("color"),
            item.get("size"),
        )

        if key in seen:
            warnings.add("duplicate_item")
            break

        seen.add(key)

    # =====================================
    # 🧠 META VALIDATION
    # =====================================

    parser_confidence = meta.get("confidence")

    if isinstance(parser_confidence, (int, float)) and parser_confidence < 0.5:
        warnings.add("low_parser_confidence")

    if meta.get("fallback_used"):
        warnings.add("fallback_used")

    # =====================================
    # 📦 FINAL OUTPUT
    # =====================================

    return list(warnings)
