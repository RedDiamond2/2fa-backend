# app/services/order_service.py

import hashlib
import logging
import time
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import customers_collection, orders_collection, generate_id
from app.models.customer_model import Customer
from app.models.order_model import Order, OrderItem
from app.repositories.customer_repository import CustomerRepository
from app.services.identity_service import resolve_identity
from app.services.memory_service import update_customer_memory
from app.services.usage_service import log_event

logger = logging.getLogger("order_service")


# =========================================================
# 🛡️ UTILITIES
# =========================================================
def _safe_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


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


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _item_to_dict(item: Any) -> Dict[str, Any]:
    if hasattr(item, "model_dump"):
        item = item.model_dump()
    return item if isinstance(item, dict) else {}


def _normalize_item_key(item: Dict[str, Any]) -> Tuple[str, str, str]:
    product = _safe_text(item.get("product") or item.get("name")).lower()
    color = _safe_text(item.get("color")).lower()
    size = _safe_text(item.get("size")).lower()
    return product, color, size


def _fetch_customer_by_identity_id(identity_id: Any) -> Optional[Dict[str, Any]]:
    if identity_id in [None, "", [], {}]:
        return None

    try:
        return customers_collection.find_one(
            {"$or": [{"id": identity_id}, {"_id": identity_id}]}
        )
    except Exception:
        return None


def generate_order_fingerprint(
    phone: str,
    items: List[OrderItem],
    intent: str = "new",
) -> str:
    safe_phone = _safe_text(phone)

    # Build normalized items (stable sorting, lowercase, no quantity)
    normalized: List[str] = []
    for i in items or []:
        product = _safe_text(getattr(i, "product", "")).lower()
        color = _safe_text(getattr(i, "color", "")).lower()
        size = _safe_text(getattr(i, "size", "")).lower()
        normalized.append(f"{product}|{color}|{size}")
    normalized.sort()

    if not safe_phone:
        # Deterministic + high-entropy fallback for missing-phone orders
        items_hash = hashlib.sha256("|".join(normalized).encode()).hexdigest()[:16]
        timestamp = time.time_ns()
        safe_phone = f"no_phone|{items_hash}|{timestamp}"

    raw = f"{safe_phone}|{_safe_text(intent).lower()}|" + "|".join(normalized)
    return hashlib.sha256(raw.encode()).hexdigest()


def sanitize_quantity(qty: Any) -> int:
    try:
        val = int(qty)
        if val < 1:
            return 1
        return min(val, 100)
    except (ValueError, TypeError):
        return 1


# =========================================================
# 👤 CUSTOMER ENGINE
# =========================================================
def find_or_create_customer(
    phone: str, name: Optional[str] = None
) -> Optional[Customer]:
    phone = _safe_text(phone)
    if not phone:
        return None

    existing = CustomerRepository.find_by_phone(phone)

    if existing:
        existing_name = existing.get("name")
        if name and existing_name in ["Unknown", "⚠️", None, ""]:
            CustomerRepository.update(existing["id"], {"name": name})
            existing["name"] = name

        return Customer(
            id=existing["id"],
            name=existing.get("name"),
            phone=existing.get("phone"),
        )

    customer_id = generate_id()
    new_customer = {
        "id": customer_id,
        "name": name or "Unknown",
        "phone": phone,
    }

    CustomerRepository.insert(new_customer)
    return Customer(**new_customer)


# =========================================================
# 📦 ITEMS & FINANCIAL ENGINE
# =========================================================
def normalize_item(item: Dict[str, Any]) -> Optional[OrderItem]:
    if not item or not _safe_text(item.get("product")):
        return None

    qty = sanitize_quantity(item.get("quantity", 1))

    DEFAULT_PRICES = {
        "تريكو": 1500,
        "قميص": 1200,
        "سروال": 1800,
    }

    raw_price = item.get("price")
    if raw_price in [None, "", 0, "0"]:
        price = DEFAULT_PRICES.get(item.get("product"), 0)
    else:
        price = _safe_float(raw_price, 0.0)

    product = _safe_text(item.get("product"))
    color = _safe_text(item.get("color")) or "غير محدد"
    size = _safe_text(item.get("size")) or "?"

    return OrderItem(
        product=product,
        quantity=qty,
        color=color,
        size=size,
        name=f"{product} | {item.get('color')} | {item.get('size')}",
        price=price,
        total=round(float(qty) * float(price), 2),
    )


def validate_items(items: List[Dict[str, Any]]) -> List[OrderItem]:
    if not isinstance(items, list):
        return []
    return [i for i in (normalize_item(x) for x in items) if i]


def enrich_items_and_payment(items: List[OrderItem], shipping_fee: float = 0.0):
    items_total = 0.0
    enriched_items: List[OrderItem] = []

    for item in items or []:
        price = _safe_float(getattr(item, "price", 0.0), 0.0)
        quantity = sanitize_quantity(getattr(item, "quantity", 1))
        line_total = round(price * quantity, 2)

        item.price = price
        item.quantity = quantity
        item.total = line_total

        items_total += line_total
        enriched_items.append(item)

    payment_value = round(items_total + _safe_float(shipping_fee, 0.0), 2)
    return enriched_items, payment_value


# =========================================================
# 📍 LOCATION & WARNINGS
# =========================================================
def build_safe_location(data: Dict[str, Any]) -> Dict[str, Any]:
    address_data = data.get("address")
    location_input = data.get("location")

    if isinstance(address_data, dict):
        return {
            "province": address_data.get("province"),
            "district": address_data.get("district"),
            "area": address_data.get("area"),
            "full": address_data.get("full"),
            "building": address_data.get("building"),
            "door": address_data.get("door"),
        }

    if isinstance(address_data, str):
        return {
            "province": None,
            "district": None,
            "area": None,
            "full": address_data,
            "building": None,
            "door": None,
        }

    return {
        "province": None,
        "district": None,
        "area": None,
        "full": location_input or "غير محدد",
        "building": None,
        "door": None,
    }


def compute_warnings(data: Dict[str, Any], address_text: str) -> List[str]:
    warnings: List[str] = []

    name = data.get("name")
    if not name or name in ["Unknown", "⚠️", None, ""]:
        warnings.append("missing_name")

    if not address_text or address_text == "غير محدد":
        warnings.append("missing_address")

    return warnings


# =========================================================
# 🔥 ACTION ENGINE (PURE COMPATIBILITY HELPER)
# =========================================================
def handle_action_engine(intent: str, phone: str, items: List[OrderItem]):
    intent = _safe_text(intent).lower()
    phone = _safe_text(phone)

    if intent not in ["add", "update", "remove"] or not phone:
        return None

    existing = orders_collection.find_one(
        {"phone": phone, "status": {"$in": ["draft", "confirmed"]}},
        sort=[("created_at", -1)],
    )

    if not existing:
        return None

    items_db = []
    for item in existing.get("items", []):
        item_dict = _item_to_dict(item)
        if item_dict:
            items_db.append(item_dict)

    if intent == "add":
        for new_item in items:
            found = False
            for db_item in items_db:
                if (
                    _safe_text(db_item.get("product")) == _safe_text(new_item.product)
                    and _safe_text(db_item.get("color")) == _safe_text(new_item.color)
                    and _safe_text(db_item.get("size")) == _safe_text(new_item.size)
                ):
                    db_item["quantity"] = _safe_int(
                        db_item.get("quantity"), 1
                    ) + sanitize_quantity(new_item.quantity)
                    found = True
                    break
            if not found:
                items_db.append(new_item.model_dump())

    elif intent == "update":
        for new_item in items:
            for db_item in items_db:
                if (
                    _safe_text(db_item.get("product")) == _safe_text(new_item.product)
                    and _safe_text(db_item.get("color")) == _safe_text(new_item.color)
                    and _safe_text(db_item.get("size")) == _safe_text(new_item.size)
                ):
                    db_item["quantity"] = sanitize_quantity(new_item.quantity)

    elif intent == "remove":
        items_db = [
            db_item
            for db_item in items_db
            if not any(
                _safe_text(db_item.get("product")) == _safe_text(new_item.product)
                and _safe_text(db_item.get("color")) == _safe_text(new_item.color)
                and _safe_text(db_item.get("size")) == _safe_text(new_item.size)
                for new_item in items
            )
        ]

    updated_items_objs = [OrderItem(**i) for i in items_db if isinstance(i, dict)]
    enriched_items, new_payment_value = enrich_items_and_payment(
        updated_items_objs,
        existing.get("shipping_fee", 0.0),
    )

    final_items_list = [i.model_dump() for i in enriched_items]
    updated_order = deepcopy(existing)
    updated_order["items"] = final_items_list
    updated_order["payment_value"] = new_payment_value
    updated_order["items_total"] = round(
        sum([_safe_float(i.total, 0.0) for i in enriched_items]), 2
    )
    updated_order["total_amount"] = new_payment_value
    updated_order["updated_at"] = datetime.utcnow().isoformat()
    updated_order.pop("_id", None)

    return {"success": True, "order": updated_order}


# =========================================================
# 🚀 CORE PIPELINE
# =========================================================
def create_order_from_parsed(
    data: Dict[str, Any],
    decision_data: Dict[str, Any],
    trace_id: Optional[str] = None,
):
    try:
        data = _safe_dict(data)
        decision_data = _safe_dict(decision_data)

        phone = _safe_text(data.get("phone"))
        intent = _safe_text(data.get("intent", "new")).lower()
        raw_items = data.get("items") if isinstance(data.get("items"), list) else []
        messages = _safe_list(data.get("messages"))

        # validate only once, here
        items = validate_items(raw_items)
        has_items = len(items) > 0

        # DEDUP FINGERPRINT GENERATION
        fingerprint = generate_order_fingerprint(phone, items, intent)

        # IDENTITY (STRICT BINDING)
        identity = resolve_identity(data)
        identity_id = identity.get("customer_id")
        identity_status = identity.get("status")
        identity_reason = identity.get("reason")

        customer_doc = _fetch_customer_by_identity_id(identity_id)
        customer = (
            Customer(
                id=customer_doc.get("id") or customer_doc.get("_id"),
                name=customer_doc.get("name"),
                phone=customer_doc.get("phone"),
            )
            if customer_doc
            else None
        )

        customer_id = identity_id if identity_id not in [None, "", [], {}] else None

        # Single binding source of truth for returning flag
        is_returning = bool(
            customer_id
            and orders_collection.count_documents({"customer_id": customer_id}) > 0
        )

        # Presentation/storage defaults only, after identity + decision are resolved
        raw_name = _safe_text(data.get("name"))
        customer_name = raw_name or "⚠️"

        location_obj = build_safe_location(data)
        address_obj = _safe_dict(data.get("address")) or deepcopy(location_obj)

        # warnings come only from parser/meta
        meta = _safe_dict(data.get("meta"))
        warnings = _safe_list(meta.get("warnings"))

        # Decision comes only from confidence_service (via decision_data)
        decision = decision_data.get("decision")
        confidence = decision_data.get("confidence_score")
        needs_review = bool(decision_data.get("needs_review"))

        status = "confirmed" if decision == "auto" else "draft"

        # FINANCIAL ENGINE
        shipping_fee = _safe_float(data.get("shipping_fee") or 0.0, 0.0)

        if shipping_fee == 0:
            province = location_obj.get("province")
            if province == "وهران":
                shipping_fee = 300.0
            elif province:
                shipping_fee = 500.0

        if has_items:
            items, payment_value = enrich_items_and_payment(items, shipping_fee)
            items_total = round(sum([_safe_float(i.total, 0.0) for i in items]), 2)
            total_amount = round(items_total + shipping_fee, 2)
        else:
            items = []
            payment_value = 0.0
            items_total = 0.0
            total_amount = shipping_fee

        # BUILD ORDER MODEL
        order = Order(
            id=generate_id(),
            customer_name=customer_name,
            phone=phone,
            customer_id=customer_id,
            is_returning=is_returning,
            identity_status=identity_status,
            address=address_obj,
            location=location_obj,
            items=items,
            status=status,
            timestamp=datetime.utcnow().isoformat(),
            messages=messages,
            raw_message="\n".join(messages),
            warnings=warnings,
            needs_review=needs_review,
            shipping_fee=shipping_fee,
            payment_value=payment_value,
            items_total=items_total,
            total_amount=total_amount,
        )

        order_dict = order.model_dump()

        if data.get("temp_id"):
            order_dict["temp_id"] = data["temp_id"]

        order_dict["fingerprint"] = fingerprint
        order_dict["created_at"] = datetime.utcnow().timestamp()

        # SINGLE WRITE PATH
        upsert_result = orders_collection.update_one(
            {"fingerprint": fingerprint},
            {"$setOnInsert": order_dict},
            upsert=True,
        )

        # SIDE EFFECTS
        if upsert_result.upserted_id:
            if phone:
                update_customer_memory(
                    phone,
                    {
                        "name": customer_name,
                        "location": location_obj,
                        "items": [i.model_dump() for i in items],
                    },
                )

            log_event(
                event="order_finalized",
                trace_id=trace_id,
                order_id=order.id,
                customer_id=customer_id,
                status=order.status,
                meta={
                    "decision": decision,
                    "confidence": confidence,
                    "identity_status": identity_status,
                    "identity_reason": identity_reason,
                    "warnings": warnings,
                    "items_count": len(order.items),
                },
            )

        # RETURN RESULT
        existing_order = orders_collection.find_one({"fingerprint": fingerprint})
        if existing_order:
            existing_order.pop("_id", None)
            return {
                "success": True,
                "order": existing_order,
                "meta": {
                    "has_items": has_items,
                    "is_partial": not has_items,
                    "identity_status": identity_status,
                    "fingerprint": fingerprint,
                },
            }

        logger.error(f"[ORDER LOOKUP FAILED] fingerprint={fingerprint}")
        return {"status": "error", "reason": "order_not_found_after_upsert"}

    except Exception as e:
        log_event(
            event="order_error",
            trace_id=trace_id,
            status="error",
            meta={"error": str(e)},
        )
        logger.exception("ORDER PIPELINE CRASH")
        return {
            "status": "error",
            "reason": "order_pipeline_error",
            "error": str(e),
        }
