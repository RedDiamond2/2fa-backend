# app/services/response_formatter.py

from typing import Any, Dict, List
from copy import deepcopy
from datetime import datetime


# =====================================
# 🧹 SAFE UTILS
# =====================================


def _safe_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# =====================================
# 🛒 ITEM NORMALIZATION
# =====================================


def _normalize_item(item: Any) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {
            "product": "",
            "name": "",
            "quantity": 1,
            "color": None,
            "size": None,
            "price": 0.0,
            "total": 0.0,
        }

    product = _safe_text(item.get("product") or item.get("name") or item.get("title"))
    color = _safe_text(item.get("color"))
    size = _safe_text(item.get("size"))

    name_parts = [p for p in [product, color, size] if p]
    name = " | ".join(name_parts) if name_parts else product

    quantity = _safe_int(item.get("quantity"), 1)
    price = _safe_float(item.get("price"), 0.0)
    total = round(quantity * price, 2)

    return {
        "product": product,
        "name": name,
        "quantity": quantity,
        "color": color or None,
        "size": size or None,
        "price": price,
        "total": total,
    }


# =====================================
# 📍 LOCATION NORMALIZATION
# =====================================


def _normalize_location(address: Any, location: Any):
    address_full = ""
    structured = {}

    if isinstance(address, dict):
        structured = deepcopy(address)
        address_full = _safe_text(address.get("full"))

    elif isinstance(location, dict):
        structured = deepcopy(location)
        address_full = _safe_text(location.get("full"))

    elif isinstance(address, str):
        address_full = address

    elif isinstance(location, str):
        address_full = location

    if not isinstance(structured, dict):
        structured = {}

    if address_full and "full" not in structured:
        structured["full"] = address_full

    return address_full, structured


# =====================================
# 🧠 META NORMALIZATION
# =====================================


def _normalize_meta(order_data: Dict[str, Any]) -> Dict[str, Any]:
    meta = order_data.get("meta")
    if not isinstance(meta, dict):
        meta = {}

    warnings = order_data.get("warnings")
    if not isinstance(warnings, list):
        warnings = meta.get("warnings", [])
        if not isinstance(warnings, list):
            warnings = []

    return {
        "confidence": meta.get("confidence", 0),
        "decision": meta.get("decision", "manual"),
        "warnings": warnings,
        "warnings_count": len(warnings),
        "field_confidence": meta.get("field_confidence", {}),
        "trace_id": meta.get("trace_id"),
    }


# =====================================
# 🧾 CORE FORMATTER
# =====================================


def format_order_for_frontend(order: Any) -> Dict[str, Any]:
    order_data = order.model_dump() if hasattr(order, "model_dump") else order

    if not isinstance(order_data, dict):
        order_data = {}

    order_data = deepcopy(order_data)

    # ================================
    # 📍 LOCATION
    # ================================
    address_full, structured_location = _normalize_location(
        order_data.get("address"),
        order_data.get("location"),
    )

    # ================================
    # 🛒 ITEMS
    # ================================
    raw_items = order_data.get("items") or []
    items: List[Dict[str, Any]] = []

    if isinstance(raw_items, list):
        for item in raw_items:
            if hasattr(item, "model_dump"):
                item = item.model_dump()

            normalized = _normalize_item(item)

            if normalized.get("product") or normalized.get("name"):
                items.append(normalized)

    # ================================
    # 💰 FINANCIALS
    # ================================
    shipping_fee = _safe_float(order_data.get("shipping_fee"))
    payment_value = _safe_float(order_data.get("payment_value"))

    items_total = round(sum(i["total"] for i in items), 2)
    grand_total = round(items_total + shipping_fee, 2)

    # ================================
    # 🧠 META
    # ================================
    meta = _normalize_meta(order_data)

    # ================================
    # 🆔 IDS
    # ================================
    id_value = order_data.get("id") or order_data.get("_id")

    # ================================
    # 📦 FINAL CONTRACT
    # ================================
    return {
        "id": str(id_value) if id_value else "",
        "temp_id": order_data.get("temp_id") or "",
        "fingerprint": order_data.get("fingerprint") or "",
        "conversation_id": order_data.get("conversation_id"),
        "customer_name": _safe_text(
            order_data.get("customer_name") or order_data.get("name")
        ),
        "phone": _safe_text(order_data.get("phone")),
        "address": address_full,
        "location": structured_location,
        "items": items,
        "status": _safe_text(order_data.get("status") or "new"),
        "order_stage": _safe_text(order_data.get("order_stage") or "new"),
        # 💰 finance
        "payment_status": _safe_text(order_data.get("payment_status")),
        "payment_type": _safe_text(order_data.get("payment_type")),
        "payment_value": payment_value,
        "shipping_fee": shipping_fee,
        "items_total": items_total,
        "total": grand_total,
        # ⚠️ flags
        "needs_review": bool(order_data.get("needs_review")),
        "warnings": meta["warnings"],
        # 🧠 meta
        "meta": meta,
        # 🕒 timestamps
        "created_at": order_data.get("created_at") or datetime.utcnow().isoformat(),
        "updated_at": order_data.get("updated_at"),
    }


# =====================================
# 🔥 BULK FORMATTER
# =====================================


def format_bulk_orders(results: List[Any]) -> List[Dict[str, Any]]:
    formatted: List[Dict[str, Any]] = []

    for r in results:
        try:
            if isinstance(r, dict) and r.get("status") == "success":
                formatted.append(
                    {
                        "status": "success",
                        "order": format_order_for_frontend(r.get("order")),
                    }
                )
            else:
                formatted.append(
                    {
                        "status": "error",
                        "error": str(r),
                    }
                )
        except Exception as e:
            formatted.append(
                {
                    "status": "error",
                    "error": str(e),
                }
            )

    return formatted
