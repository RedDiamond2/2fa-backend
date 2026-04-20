# app/services/memory_service.py
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from app.core.database import memory_collection

# =====================================
# ⚙️ CONFIG & LOGGING
# =====================================
logger = logging.getLogger("memory_service")

MAX_ITEMS_MEMORY = 5
DECAY_DAYS = 30  # المعلومات التي لم تُحدث منذ 30 يوم تعتبر منتهية الصلاحية
MIN_CONFIDENCE_THRESHOLD = 0.4  # الحد الأدنى للثقة لقبول تحديث الذاكرة

# =====================================
# 🛠️ HELPERS (Internal)
# =====================================

def smart_pick(new_value: Any, old_value: Any) -> Any:
    """
    اختيار القيمة الذكي: لا نستبدل القيمة القديمة بقيمة فارغة أو غير صالحة.
    """
    if new_value and str(new_value).strip():
        return new_value
    return old_value

def build_item_key(item: Dict) -> str:
    """
    إنشاء مفتاح فريد للمنتج بناءً على (الاسم | اللون | المقاس) لمنع التكرار.
    """
    product = str(item.get("product", "")).strip().lower()
    color = str(item.get("color", "")).strip().lower()
    size = str(item.get("size", "")).strip().lower()
    return f"{product}|{color}|{size}"

def normalize_address(address: Any) -> Dict:
    """
    توحيد شكل العنوان ليكون دائماً قاموس (Dictionary).
    """
    if not address:
        return {}
    if isinstance(address, dict):
        return address
    return {"full": str(address).strip()}

# =====================================
# 📥 GET MEMORY
# =====================================

def get_customer_memory(phone: str) -> Dict:
    """
    جلب سجل ذاكرة العميل من قاعدة البيانات.
    """
    if not phone:
        return {}

    try:
        memory = memory_collection.find_one({"phone": phone})
        return memory if memory else {}
    except Exception as e:
        logger.error(f"[MEMORY][GET] Failed for phone={phone}: {e}")
        return {}

# =====================================
# 💾 UPDATE MEMORY (SMART MERGE & PROTECTION)
# =====================================

def update_customer_memory(phone: str, parsed: Dict):
    """
    تحديث ذاكرة العميل ببيانات جديدة مع حماية من البيانات الضعيفة (Poisoning Protection).
    """
    if not phone:
        return

    try:
        # 🚨 1. منع Memory Poisoning: التحقق من درجة الثقة
        confidence = parsed.get("confidence", 1.0)
        source = parsed.get("meta", {}).get("source", "parser")
        if confidence < MIN_CONFIDENCE_THRESHOLD and source != "developer":
            logger.warning(f"[MEMORY][SKIP] Low confidence ({confidence}) for phone={phone}")
            return
            
        existing = get_customer_memory(phone)

        # 🧠 2. Smart Overwrite & Data Assembly
        updated_memory = {
            "phone": phone,
            "last_items": merge_items(existing.get("last_items", []), parsed.get("items", [])),
            "last_location": smart_pick(parsed.get("location"), existing.get("last_location")),
            "last_name": smart_pick(parsed.get("name"), existing.get("last_name")),
            "last_address": smart_pick(normalize_address(parsed.get("address")), existing.get("last_address")),
            
            # 🧠 Meta & Tracking
            "memory_version": 4,
            "last_source": parsed.get("meta", {}).get("source", "parser"),
            "last_learning_source": source,
            "updated_at": datetime.utcnow()
        }

        # 🚨 3. Debug Visibility
        logger.info(
            f"[MEMORY][UPDATE] phone={phone} items={len(updated_memory['last_items'])} "
            f"conf={confidence} source={source}"
        )
        
        memory_collection.update_one(
            {"phone": phone},
            {
                "$set": updated_memory,
                "$setOnInsert": {
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )
    except Exception as e:
        logger.error(f"[MEMORY][UPDATE] Critical failure for phone={phone}: {e}")

# =====================================
# 🧠 ENRICH PARSED WITH MEMORY (CORE)
# =====================================

def enrich_with_memory(parsed: Dict) -> Dict:
    """
    إكمال البيانات الناقصة في الطلب الحالي باستخدام ذاكرة العميل (مع معالجة التلاشي الزمني).
    """
    phone = parsed.get("phone")
    if not phone:
        return parsed

    memory = get_customer_memory(phone)
    if not memory:
        return parsed

    # ⏳ 1. Memory Decay: تجاهل الذاكرة إذا كانت قديمة جداً (Soft Decay)
    updated_at = memory.get("updated_at")
    if updated_at:
        # التعامل مع التوقيت سواء كان datetime object أو timestamp
        if isinstance(updated_at, datetime):
            age_days = (datetime.utcnow() - updated_at).days
        else:
            age_days = (datetime.utcnow() - datetime.utcfromtimestamp(updated_at)).days
            
        if age_days > DECAY_DAYS:
            logger.info(f"[MEMORY][SKIP] Decay: Memory is too old ({age_days} days) for phone={phone}")
            return parsed

    used_memory_fields = []

    # 🛒 ITEMS: اقتراح آخر منتجات إذا كان الطلب الحالي فارغاً
    if not parsed.get("items") and memory.get("last_items"):
        parsed["items"] = memory["last_items"]
        used_memory_fields.append("items")

    # 📍 LOCATION: الولاية/البلدية
    if not parsed.get("location") and memory.get("last_location"):
        parsed["location"] = memory["last_location"]
        used_memory_fields.append("location")

    # 🏠 ADDRESS: العنوان الكامل
    current_address = parsed.get("address")
    is_address_empty = not current_address or (isinstance(current_address, dict) and not current_address.get("full"))
    
    if is_address_empty and memory.get("last_address"):
        parsed["address"] = memory["last_address"]
        used_memory_fields.append("address")

    # 👤 NAME: الاسم
    if not parsed.get("name") and memory.get("last_name"):
        parsed["name"] = memory["last_name"]
        used_memory_fields.append("name")

    # 🧠 2. Traceability: تتبع استخدام الذاكرة للـ Debug و الـ SaaS
    if used_memory_fields:
        parsed.setdefault("meta", {})
        parsed["meta"].update({
            "memory_used": True,
            "memory_fields": used_memory_fields,
            "memory_timestamp": str(memory.get("updated_at")),
            "memory_age_days": (datetime.utcnow() - updated_at).days if updated_at else 0
        })

    return parsed

# =====================================
# 🔀 MERGE ITEMS (SMART & FILTERED)
# =====================================

def merge_items(old_items: List[Dict], new_items: List[Dict]) -> List[Dict]:
    """
    دمج العناصر مع التحقق من صحة البيانات ومنع التكرار (Edge-case optimization).
    """
    if not old_items and not new_items:
        return []

    # دمج القائمتين (الجديد له الأولوية في الترتيب)
    combined = (new_items or []) + (old_items or [])
    
    seen = set()
    unique_items = []

    for item in combined:
        if not isinstance(item, dict):
            continue

        # 🚨 1. حماية من العناصر الفارغة (Empty item protection)
        if not item.get("product") or not str(item.get("product")).strip():
            continue

        key = build_item_key(item)
        if key not in seen:
            seen.add(key)
            unique_items.append(item)

        # 2. التوقف عند الحد الأقصى
        if len(unique_items) >= MAX_ITEMS_MEMORY:
            break

    return unique_items

# =====================================
# 🧹 CLEAN MEMORY (MAINTENANCE)
# =====================================

def clean_old_memory():
    """
    تنظيف قاعدة البيانات من السجلات القديمة جداً (Hard Decay).
    """
    try:
        # حساب تاريخ العتبة
        threshold_date = datetime.utcnow() - timedelta(days=DECAY_DAYS)
        
        result = memory_collection.delete_many({
            "updated_at": {"$lt": threshold_date}
        })
        
        if result.deleted_count > 0:
            logger.info(f"[MEMORY][CLEAN] Hard cleanup: Deleted {result.deleted_count} stale records")
    except Exception as e:
        logger.error(f"[MEMORY][CLEAN] Maintenance failed: {e}")