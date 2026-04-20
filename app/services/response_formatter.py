from typing import Any, Dict, List


def _normalize_item(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {"name": "", "quantity": 0}

    product = str(item.get("product") or item.get("name") or item.get("title") or "").strip()
    color = str(item.get("color") or "").strip()
    size = str(item.get("size") or "").strip()

    name_parts = [part for part in [product, color, size] if part]
    name = " | ".join(name_parts).strip() or ""

    quantity = item.get("quantity", 1)
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        quantity = 1

    # ================================
    # 💰 PRICING FIELDS (FIXED)
    # ================================
    price = item.get("price", 0.0)
    try:
        price = float(price)
    except (TypeError, ValueError):
        price = 0.0

    total = quantity * price

    return {
        "product": product,
        "name": name,
        "quantity": quantity,
        "color": color or None,
        "size": size or None,
        "price": price,
        "total": total,
    }

def _safe_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def format_order_for_frontend(order: Any) -> Dict[str, Any]:
    order_data = order.model_dump() if hasattr(order, "model_dump") else order or {}
    if not isinstance(order_data, dict):
        order_data = {}

    address = order_data.get("address")
    location = order_data.get("location")

    address_full = ""
    structured_location = {}

    # Prefer structured address if exists
    if isinstance(address, dict):
        structured_location = address
        address_full = _safe_text(address.get("full"))

    elif isinstance(location, dict):
        structured_location = location
        address_full = _safe_text(location.get("full"))

    # Fallback to string
    elif isinstance(address, str):
        address_full = address

    elif isinstance(location, str):
        address_full = location

    # Ensure structured object exists
    if not isinstance(structured_location, dict):
        structured_location = {}

    # Inject full into structure if missing
    if address_full and "full" not in structured_location:
        structured_location["full"] = address_full

    raw_items = order_data.get("items") or []
    items: List[Dict[str, Any]] = []
    if isinstance(raw_items, list):
        for item in raw_items:
            if hasattr(item, "model_dump"):
                item = item.model_dump()
            if isinstance(item, dict):
                normalized = _normalize_item(item)
                if normalized.get("product") or normalized.get("name"):
                    items.append(normalized)

    warnings = order_data.get("warnings")
    if not isinstance(warnings, list):
        warnings = []

    id_value = order_data.get("id") or order_data.get("_id")

    # ================================
    # 💰 CALCULATE TOTALS & PAYMENT (FIXED)
    # ================================
    shipping_fee = order_data.get("shipping_fee", 0.0)
    try:
        shipping_fee = float(shipping_fee) if shipping_fee else 0.0
    except (TypeError, ValueError):
        shipping_fee = 0.0

    payment_value = order_data.get("payment_value")
    try:
        payment_value = float(payment_value) if payment_value else 0.0
    except (TypeError, ValueError):
        payment_value = 0.0

    return {
        "id": str(id_value) if id_value else "",
        "temp_id": order_data.get("temp_id") or "",
        "fingerprint": order_data.get("fingerprint") or "",
        "customer_name": _safe_text(order_data.get("customer_name") or order_data.get("name") or ""),
        "phone": _safe_text(order_data.get("phone")),
        "address": address_full,
        "location": structured_location,
        "items": items,
        "status": _safe_text(order_data.get("status")),
        "order_stage": _safe_text(order_data.get("order_stage") or "new"),
        "payment_status": _safe_text(order_data.get("payment_status")),
        "payment_type": _safe_text(order_data.get("payment_type")),
        "payment_value": payment_value,
        "shipping_fee": shipping_fee,
        "needs_review": bool(order_data.get("needs_review")),
        "warnings": warnings,
    }
