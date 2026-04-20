# app/services/warning_service.py

from typing import List, Dict, Any


def generate_warnings(parsed: Dict[str, Any]) -> List[str]:
    """
    Generate intelligent warnings based on parsed order data.

    الهدف:
    - كشف النواقص
    - كشف الأخطاء
    - مساعدة التاجر على اتخاذ القرار
    """

    warnings = set()  # ✅ منع التكرار مباشرة

    # ==============================
    # SAFE EXTRACTION (anti-crash)
    # ==============================
    items = parsed.get("items") or []
    phone = parsed.get("phone")
    name = parsed.get("name")
    location = parsed.get("location")
    address = parsed.get("address") or {}
    meta = parsed.get("meta") or {}

    # ==============================
    # ITEMS VALIDATION
    # ==============================
    if not items:
        warnings.add("no_items")
    else:
        for item in items:
            if not isinstance(item, dict):
                warnings.add("invalid_item_structure")
                continue

            # ❌ missing product
            if not item.get("product"):
                warnings.add("invalid_item")

            # ⚠️ quantity checks
            qty = item.get("quantity", 1)

            if not isinstance(qty, (int, float)):
                warnings.add("invalid_quantity_type")
            else:
                if qty <= 0:
                    warnings.add("invalid_quantity")
                elif qty > 5:
                    warnings.add("suspicious_quantity")

    # ==============================
    # PHONE VALIDATION
    # ==============================
    if not phone:
        warnings.add("missing_phone")
    else:
        if not isinstance(phone, str):
            warnings.add("invalid_phone")
        else:
            clean_phone = phone.strip()

            # الجزائر: غالبا 10 أرقام
            if not clean_phone.isdigit():
                warnings.add("invalid_phone")
            elif len(clean_phone) != 10:
                warnings.add("invalid_phone")

    # ==============================
    # NAME VALIDATION
    # ==============================
    if not name or name in ["⚠️", "Unknown", "???"]:
        warnings.add("missing_name")
    else:
        if not isinstance(name, str):
            warnings.add("invalid_name")
        else:
            clean_name = name.strip()

            if len(clean_name) < 3:
                warnings.add("weak_name")

            # ⚠️ اسم مشبوه (أرقام فقط)
            if clean_name.isdigit():
                warnings.add("invalid_name")

    # ==============================
    # LOCATION VALIDATION
    # ==============================
    if not location:
        warnings.add("missing_location")

    elif isinstance(location, dict):
        province = location.get("province")

        if not province:
            warnings.add("missing_location")

        # ⚠️ confidence
        confidence = location.get("confidence")
        if isinstance(confidence, (int, float)):
            if confidence < 0.5:
                warnings.add("weak_location")

    elif isinstance(location, str):
        normalized_location = location.strip()
        if not normalized_location:
            warnings.add("missing_location")
        else:
            address_keywords = ["حي", "بلدية", "ولاية", "مسكن", "عمارة", "بناية", "باب", "رقم"]
            if not any(word in normalized_location for word in address_keywords):
                province = address.get("province")
                if not (province and (address.get("area") or address.get("district"))):
                    warnings.add("invalid_location_format")
    else:
        # ⚠️ format غير متوقع
        warnings.add("invalid_location_format")

    # ==============================
    # ADDRESS VALIDATION
    # ==============================
    if not address or not isinstance(address, dict):
        warnings.add("missing_address")

    else:
        full_address = address.get("full")

        if not full_address:
            warnings.add("missing_address")
        else:
            # ⚠️ عنوان ضعيف
            if not address.get("district") and not address.get("area"):
                warnings.add("weak_address")

            # ⚠️ عنوان قصير جدًا
            if isinstance(full_address, str) and len(full_address.strip()) < 5:
                warnings.add("weak_address")

    # ==============================
    # DUPLICATE ITEMS
    # ==============================
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

    # ==============================
    # META / PARSER WARNINGS
    # ==============================
    # ⚠️ parser confidence global
    parser_confidence = meta.get("confidence")

    if isinstance(parser_confidence, (int, float)):
        if parser_confidence < 0.5:
            warnings.add("low_parser_confidence")

    # ⚠️ fallback usage (AI / regex failed)
    if meta.get("fallback_used"):
        warnings.add("fallback_used")

    # ==============================
    # FINAL OUTPUT
    # ==============================
    return list(warnings)