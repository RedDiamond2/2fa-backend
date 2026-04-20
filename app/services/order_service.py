# app/services/order_service.py

import hashlib
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

from app.core.database import orders_collection, generate_id
from app.services.identity_service import resolve_identity
from app.models.order_model import Order, OrderItem
from app.models.customer_model import Customer
from app.services.memory_service import update_customer_memory
from app.services.usage_service import log_event
from app.repositories.order_repository import OrderRepository
from app.repositories.customer_repository import CustomerRepository

logger = logging.getLogger("order_service")

# =========================================================
# 🛡️ UTILITIES
# =========================================================

def generate_order_fingerprint(phone: str, items: List[OrderItem], intent: str = "new") -> str:
    """توليد بصمة فريدة للطلب لمنع التكرار (Deduplication)"""
    safe_phone = phone or "no_phone"
    normalized = []

    for i in items:
        normalized.append(
            f"{(i.product or '').strip().lower()}|"
            f"{(i.color or '').strip().lower()}|"
            f"{(i.size or '').strip().lower()}"
        )

    normalized.sort()
    raw = f"{safe_phone}|{intent}|" + "|".join(normalized)
    return hashlib.sha256(raw.encode()).hexdigest()


def sanitize_quantity(qty: Any) -> int:
    """تحجيم الكميات لضمان منطقية البيانات التجارية"""
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

def find_or_create_customer(phone: str, name: Optional[str] = None) -> Optional[Customer]:
    if not phone:
        return None

    existing = CustomerRepository.find_by_phone(phone)

    if existing:
        # تحديث الاسم إذا كان مجهولاً وجاء اسم جديد من البارسر
        if name and existing.get("name") in ["Unknown", "⚠️", None]:
            CustomerRepository.update(existing["id"], {"name": name})
            existing["name"] = name

        return Customer(
            id=existing["id"],
            name=existing.get("name"),
            phone=existing.get("phone")
        )

    customer_id = generate_id()
    new_customer = {
        "id": customer_id,
        "name": name or "Unknown",
        "phone": phone
    }

    CustomerRepository.insert(new_customer)
    return Customer(**new_customer)


# =========================================================
# 📦 ITEMS & FINANCIAL ENGINE
# =========================================================

def normalize_item(item: Dict) -> Optional[OrderItem]:
    """تهيئة المنتج مع ضمان صحة الأنواع والحسابات الأولية"""
    if not item or not item.get("product"):
        return None

    qty = sanitize_quantity(item.get("quantity", 1))
    # 🔥 SMART PRICE ENGINE (Fallback)
    DEFAULT_PRICES = {
        "تريكو": 1500,
        "قميص": 1200,
        "سروال": 1800,
    }

    price = (
        float(item.get("price"))
        if item.get("price") not in [None, 0, "0"]
        else DEFAULT_PRICES.get(item.get("product"), 0)
    )
    
    return OrderItem(
        product=item.get("product"),
        quantity=qty,
        color=item.get("color") or "غير محدد",
        size=item.get("size") or "?",
        name=f"{item.get('product')} | {item.get('color')} | {item.get('size')}",
        price=price,
        total=round(float(qty) * float(price), 2)
    )


def validate_items(items: List[Dict]) -> List[OrderItem]:
    if not isinstance(items, list):
        return []
    return [i for i in (normalize_item(x) for x in items) if i]


def enrich_items_and_payment(items: List[OrderItem], shipping_fee: float = 0.0):
    """
    🔥 Financial Engine (Production Safe)
    تحديث كافة العمليات الحسابية للمنتجات والقيمة الإجمالية بشكل مركزي
    """
    items_total = 0.0
    enriched_items = []

    for item in items:
        price = float(item.price or 0.0)
        quantity = sanitize_quantity(item.quantity)
        line_total = round(float(price or 0) * float(quantity or 1), 2)

        item.price = price
        item.quantity = quantity
        item.total = line_total
        
        items_total += line_total
        enriched_items.append(item)

    payment_value = round(items_total + float(shipping_fee or 0.0), 2)
    return enriched_items, payment_value


# =========================================================
# 📍 LOCATION & WARNINGS
# =========================================================

def build_safe_location(data: Dict) -> Dict:
    """بناء هيكل الموقع بأمان مع معالجة كافة الحالات"""
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
            "province": None, "district": None, "area": None,
            "full": address_data
        }

    return {
        "province": None, "district": None, "area": None,
        "full": location_input or "غير محدد"
    }


def compute_warnings(data: Dict, address_text: str) -> List[str]:
    """محرك التحذيرات لضمان جودة البيانات قبل التأكيد"""
    warnings = []
    if not data.get("name") or data.get("name") in ["Unknown", "⚠️"]:
        warnings.append("missing_name")
    if not address_text or address_text == "غير محدد":
        warnings.append("missing_address")
    return warnings


# =========================================================
# 🔥 ACTION ENGINE (Add/Update/Remove)
# =========================================================

def handle_action_engine(intent: str, phone: str, items: List[OrderItem]):
    """إدارة العمليات المتطورة على الطلبات الحالية مع إعادة حساب القيم مالياً"""
    if intent not in ["add", "update", "remove"] or not phone:
        return None

    existing = orders_collection.find_one(
        {"phone": phone, "status": {"$in": ["draft", "confirmed"]}},
        sort=[("created_at", -1)]
    )

    if not existing:
        return None

    items_db = [dict(i) for i in existing.get("items", [])]

    if intent == "add":
        for new_item in items:
            found = False
            for db_item in items_db:
                if (db_item.get("product") == new_item.product and
                    db_item.get("color") == new_item.color and
                    db_item.get("size") == new_item.size):
                    db_item["quantity"] += new_item.quantity
                    found = True
                    break
            if not found:
                items_db.append(new_item.model_dump())

    elif intent == "update":
        for new_item in items:
            for db_item in items_db:
                if (db_item.get("product") == new_item.product and
                    db_item.get("color") == new_item.color and
                    db_item.get("size") == new_item.size):
                    db_item["quantity"] = new_item.quantity

    elif intent == "remove":
        items_db = [
            db_item for db_item in items_db
            if not any(
                db_item.get("product") == new_item.product and
                db_item.get("color") == new_item.color and
                db_item.get("size") == new_item.size
                for new_item in items
            )
        ]

    # 🔥 تحديث الحسابات المالية بعد التعديل
    updated_items_objs = [OrderItem(**i) for i in items_db]
    enriched_items, new_payment_value = enrich_items_and_payment(
        updated_items_objs, 
        existing.get("shipping_fee", 0.0)
    )

    final_items_list = [i.model_dump() for i in enriched_items]

    orders_collection.update_one(
        {"id": existing["id"]},
        {"$set": {
            "items": final_items_list,
            "payment_value": new_payment_value,
            "items_total": sum([i.total for i in enriched_items]),
            "total_amount": new_payment_value
        }}
    )

    existing["items"] = final_items_list
    existing["payment_value"] = new_payment_value
    existing.pop("_id", None)
    return {"success": True, "order": existing}


# =========================================================
# 🚀 CORE PIPELINE (Production Grade)
# =========================================================

def create_order_from_parsed(data: Dict, decision_data: Dict, trace_id: Optional[str] = None):
    logger.info(f"[PIPELINE START] trace_id={trace_id}")

    phone = data.get("phone")
    intent = data.get("intent", "new")
    raw_items = data.get("items") if isinstance(data.get("items"), list) else []
    messages = data.get("messages", [])

    # ✅ [FIX 1] التحقق من وجود منتجات دون رفض الطلب
    items = validate_items(raw_items)
    has_items = len(items) > 0

    # =====================================================
    # ACTION ENGINE (Smart Updates)
    # =====================================================
    # ✅ [FIX 2] منع محرك العمليات من الاشتغال إذا لم تكن هناك منتجات جديدة
    if has_items:
        action_result = handle_action_engine(intent, phone, items)
        if action_result:
            logger.info(f"[ACTION ENGINE] Handled {intent} for phone={phone}")
            return action_result

    # =====================================================
    # DEDUP FINGERPRINT GENERATION
    # =====================================================
    fingerprint = generate_order_fingerprint(phone, items, intent)

    # =====================================================
    # IDENTITY & CUSTOMER
    # =====================================================
    identity = resolve_identity(data)
    customer = find_or_create_customer(phone, data.get("name")) if phone else None
    is_returning = False

    is_returning = False

    if customer and phone:
        existing_orders_count = orders_collection.count_documents({
            "customer_id": customer.id
        })
        # ⚠️ مهم: -1 لأن الطلب الحالي لم يُحفظ بعد
        if existing_orders_count > 0:
            is_returning = True
            
    if customer:
        data["identity_status"] = "known"
    else:
        data["identity_status"] = "new"
    # =====================================================
    # LOCATION & ADDRESS FIXES
    # =====================================================
    location_obj = build_safe_location(data)
    address_obj = data.get("address") if isinstance(data.get("address"), dict) else location_obj
    address_text = location_obj.get("full")

    # =====================================================
    # CUSTOMER NAME RESOLUTION
    # =====================================================
    customer_name = (
        data.get("name")
        or (customer.name if customer and customer.name not in ["Unknown", "⚠️"] else None)
        or "⚠️"
    )

    # =====================================================
    # WARNINGS ENGINE
    # =====================================================
    warnings = compute_warnings({**data, "name": customer_name}, address_text)
    
    # ✅ [FIX 5] إضافة تحذير في حال غياب المنتجات
    if not has_items:
        warnings.append("no_items")
        
    needs_review = bool(warnings)

    # =====================================================
    # 💰 FINANCIAL ENGINE
    # =====================================================
    shipping_fee = float(data.get("shipping_fee") or 0.0)

    # 🔥 SMART SHIPPING (Fallback)
    if shipping_fee == 0:
        province = location_obj.get("province")

        if province == "وهران":
            shipping_fee = 300
        elif province:
            shipping_fee = 500
            
    # ✅ [FIX 3] معالجة الحسابات المالية بناءً على وجود منتجات
    if has_items:
        items, payment_value = enrich_items_and_payment(items, shipping_fee)

        # 🔥 SAFE TOTAL CALCULATION
        items_total = sum([(i.total or 0) for i in items])
        total_amount = items_total + shipping_fee

    else:
        items = []
        payment_value = 0.0

        # 🔥 FIX: prevent crash
        items_total = 0.0
        total_amount = shipping_fee

    # =====================================================
    # BUILD ORDER MODEL
    # =====================================================
    order = Order(
        id=generate_id(),
        customer_name=customer_name,
        phone=phone,
        customer_id=(customer.id if customer else None),
        is_returning=is_returning,
        identity_status=data.get("identity_status", "new"),
        address=address_obj,   
        location=location_obj,
        items=items,
        status="confirmed" if (not needs_review and has_items) else "draft",
        timestamp=datetime.utcnow().isoformat(),
        messages=messages,
        raw_message="\n".join(messages),
        warnings=warnings,
        needs_review=needs_review,
        shipping_fee=shipping_fee,
        payment_value=payment_value,
        items_total=items_total,
        total_amount=total_amount
    )

    order_dict = order.model_dump()
    temp_id = data.get("temp_id")
    if temp_id:
        order_dict["temp_id"] = temp_id
    order_dict["fingerprint"] = fingerprint
    order_dict["created_at"] = datetime.now().timestamp()

    # =====================================================
    # ATOMIC SAVE & PERSISTENCE
    # =====================================================
    upsert_result = orders_collection.update_one(
        {"fingerprint": fingerprint},
        {"$setOnInsert": order_dict},
        upsert=True
    )

    # =====================================================
    # SIDE EFFECTS
    # =====================================================
    if upsert_result.upserted_id:
        if phone:
            update_customer_memory(phone, {
                "name": customer_name,
                "location": location_obj,
                "items": [i.model_dump() for i in items]
            })

        logger.info(f"[ORDER CREATED] id={order.id} name={customer_name} phone={phone} status={order.status}")

        log_event(
            event="order_created",
            trace_id=trace_id,
            order_id=order.id,
            customer_id=(customer.id if customer else None)
        )

    # =====================================================
    # RETURN RESULT
    # =====================================================
    existing_order = orders_collection.find_one({"fingerprint": fingerprint})
    if existing_order:
        existing_order.pop("_id", None)
        # ✅ [FIX 6] إرجاع النتيجة مع بيانات وصفية (Meta)
        return {
            "success": True, 
            "order": existing_order,
            "meta": {
                "has_items": has_items,
                "is_partial": not has_items
            }
        }
    else:
        logger.error(f"[ORDER LOOKUP FAILED] fingerprint={fingerprint}")
        return {"status": "error", "reason": "order_not_found_after_upsert"}