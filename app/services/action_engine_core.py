# app/services/action_engine_core.py

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# =====================================
# 🧹 SAFE UTILS
# =====================================
def _safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _safe_int(value: Any, default: int = 1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _coerce_item(item: Any) -> Dict[str, Any]:
    if hasattr(item, "model_dump"):
        item = item.model_dump()
    return item if isinstance(item, dict) else {}


def _normalize_item_key(item: Dict[str, Any]) -> Tuple[str, str, str]:
    """
    Canonical item identity:
    product + color + size
    """
    product = _safe_text(item.get("product") or item.get("name")).lower()
    color = _safe_text(item.get("color")).lower()
    size = _safe_text(item.get("size")).lower()
    return product, color, size


def _normalize_item_payload(item: Any) -> Dict[str, Any]:
    """
    Pure, defensive normalization used only inside action merge/update flows.
    It does NOT perform business decisions.
    """
    safe = _coerce_item(item)
    if not safe:
        return {}

    product = _safe_text(safe.get("product") or safe.get("name"))
    if not product:
        return {}

    normalized = deepcopy(safe)
    normalized["product"] = product
    normalized["name"] = _safe_text(safe.get("name")) or product

    if "quantity" in normalized:
        normalized["quantity"] = _safe_int(normalized.get("quantity"), 1)

    if "price" in normalized:
        normalized["price"] = _safe_float(normalized.get("price"), 0.0)

    if "total" in normalized:
        normalized["total"] = _safe_float(normalized.get("total"), 0.0)

    if normalized.get("color") is not None:
        normalized["color"] = _safe_text(normalized.get("color")) or None
    if normalized.get("size") is not None:
        normalized["size"] = _safe_text(normalized.get("size")) or None

    return normalized


def _normalize_items(items: Any) -> List[Dict[str, Any]]:
    safe_items: List[Dict[str, Any]] = []
    for item in _safe_list(items):
        normalized = _normalize_item_payload(item)
        if normalized:
            safe_items.append(normalized)
    return safe_items


# =====================================
# 🧱 BUILD ORDER
# =====================================
def _build_new_order(parsed: Dict[str, Any], action: str) -> Dict[str, Any]:
    """
    Build a new order snapshot from parsed payload.
    Pure function: no DB, no logging, no side effects.
    """
    parsed = _safe_dict(parsed)

    status = "confirmed" if _safe_text(action).lower() == "auto" else "draft"

    items = _normalize_items(parsed.get("items"))

    return {
        "conversation_id": parsed.get("conversation_id"),
        "customer_name": parsed.get("customer_name") or parsed.get("name"),
        "phone": parsed.get("phone"),
        "items": items,
        "address": deepcopy(parsed.get("address")),
        "location": deepcopy(parsed.get("location")),
        "status": status,
        "order_stage": "new",
        "needs_review": bool(parsed.get("needs_review", False)),
        "meta": deepcopy(_safe_dict(parsed.get("meta"))),
        "fingerprint": parsed.get("fingerprint"),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


# =====================================
# 🛒 MERGE ITEMS
# =====================================
def _merge_items(
    existing_items: List[Dict[str, Any]], new_items: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Merge items by canonical key: product + color + size.
    Pure function: returns merged items and change descriptors.
    """
    merged = deepcopy(_normalize_items(existing_items))
    changes: List[str] = []

    for raw_new_item in _normalize_items(new_items):
        new_item = deepcopy(raw_new_item)
        new_key = _normalize_item_key(new_item)

        if not new_key[0]:
            continue

        found_index: Optional[int] = None
        for idx, item in enumerate(merged):
            if _normalize_item_key(item) == new_key:
                found_index = idx
                break

        if found_index is not None:
            item = merged[found_index]
            item_name = item.get("name") or item.get("product") or new_key[0]

            # Quantity update
            if new_item.get("quantity") is not None:
                item["quantity"] = _safe_int(
                    new_item.get("quantity"), _safe_int(item.get("quantity"), 1)
                )
                changes.append(f"qty_updated:{item_name}")

            # Attribute updates only when provided
            for key in ["color", "size", "price", "total"]:
                if new_item.get(key) not in [None, "", {}]:
                    item[key] = new_item[key]
                    changes.append(f"{key}_updated:{item_name}")

            # Keep canonical fields aligned
            if new_item.get("product"):
                item["product"] = new_item["product"]
            if new_item.get("name"):
                item["name"] = new_item["name"]

        else:
            merged.append(new_item)
            item_name = new_item.get("name") or new_item.get("product") or new_key[0]
            changes.append(f"item_added:{item_name}")

    return merged, changes


# =====================================
# 🔄 UPDATE ORDER
# =====================================
def _update_order(
    existing: Dict[str, Any], parsed: Dict[str, Any]
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Update an existing order snapshot with parsed changes.
    Pure function: no DB, no logging.
    """
    existing = _safe_dict(existing)
    parsed = _safe_dict(parsed)

    updated = deepcopy(existing)
    changes: List[str] = []

    # Customer name
    new_name = parsed.get("customer_name") or parsed.get("name")
    if new_name and new_name != existing.get("customer_name"):
        updated["customer_name"] = new_name
        changes.append("customer_updated")

    # Phone
    new_phone = parsed.get("phone")
    if new_phone and new_phone != existing.get("phone"):
        updated["phone"] = new_phone
        changes.append("phone_updated")

    # Address / location
    new_address = parsed.get("address")
    if new_address and new_address != existing.get("address"):
        updated["address"] = deepcopy(new_address)
        changes.append("address_updated")

    new_location = parsed.get("location")
    if new_location and new_location != existing.get("location"):
        updated["location"] = deepcopy(new_location)
        changes.append("location_updated")

    # Items
    parsed_items = _normalize_items(parsed.get("items"))
    existing_items = _normalize_items(existing.get("items"))

    if parsed_items:
        merged_items, item_changes = _merge_items(existing_items, parsed_items)
        updated["items"] = merged_items
        changes.extend(item_changes)

    # Meta should remain coherent and merged, not overwritten blindly
    existing_meta = _safe_dict(existing.get("meta"))
    parsed_meta = _safe_dict(parsed.get("meta"))
    if parsed_meta:
        merged_meta = deepcopy(existing_meta)
        merged_meta.update(parsed_meta)
        updated["meta"] = merged_meta
        if merged_meta != existing_meta:
            changes.append("meta_updated")

    updated["updated_at"] = datetime.utcnow().isoformat()

    return updated, changes


# =====================================
# 🔀 MERGE ORDERS
# =====================================
def _merge_orders(
    existing: Dict[str, Any], parsed: Dict[str, Any]
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Merge one order payload into another.
    Pure function: delegates to update logic and annotates merge intent.
    """
    merged, changes = _update_order(existing, parsed)
    changes.append("orders_merged")
    return merged, changes


__all__ = [
    "_build_new_order",
    "_update_order",
    "_merge_items",
    "_merge_orders",
]
