# app/services/customer_service.py

import hashlib
from typing import Dict, Any, Optional
from datetime import datetime


# =========================================
# 🟢 NORMALIZATION HELPERS
# =========================================

def normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None

    phone = str(phone).strip()

    # إزالة المسافات والرموز
    phone = "".join(filter(str.isdigit, phone))

    # الجزائر: 213xxxxxxxxx → 0xxxxxxxxx
    if phone.startswith("213") and len(phone) == 12:
        phone = "0" + phone[3:]

    return phone if len(phone) == 10 else None


def normalize_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None

    name = str(name).strip().lower()

    if len(name) < 3:
        return None

    # إزالة garbage
    if name in ["unknown", "???", "⚠️"]:
        return None

    return name


def normalize_location(location: Any) -> Optional[str]:
    if not location:
        return None

    if isinstance(location, dict):
        province = location.get("province")
        if province:
            return province.lower()

    if isinstance(location, str):
        return location.strip().lower()

    return None


# =========================================
# 🟢 FINGERPRINT GENERATION
# =========================================

def generate_fingerprint(
    phone: Optional[str],
    name: Optional[str],
    location: Optional[str]
) -> str:
    """
    توليد هوية فريدة للعميل
    """

    base = f"{phone or ''}|{name or ''}|{location or ''}"

    return hashlib.sha256(base.encode()).hexdigest()


# =========================================
# 🟢 CUSTOMER BUILDER
# =========================================

def build_customer(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    بناء كائن العميل من parsed data
    """

    phone = normalize_phone(parsed.get("phone"))
    name = normalize_name(parsed.get("name"))
    location = normalize_location(parsed.get("location"))

    fingerprint = generate_fingerprint(phone, name, location)

    customer = {
        "fingerprint": fingerprint,
        "phone": phone,
        "name": name,
        "location": location,

        # metadata
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),

        # analytics
        "order_count": 0,
        "last_order_at": None,
    }

    return customer


# =========================================
# 🟢 CUSTOMER MERGE (CRITICAL)
# =========================================

def merge_customer(existing: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    دمج بيانات العميل (ذكي)
    """

    updated = existing.copy()

    # 🔁 name (keep الأفضل)
    if new_data.get("name") and len(new_data["name"]) > len(existing.get("name", "")):
        updated["name"] = new_data["name"]

    # 🔁 phone (always trust normalized)
    if new_data.get("phone"):
        updated["phone"] = new_data["phone"]

    # 🔁 location
    if new_data.get("location"):
        updated["location"] = new_data["location"]

    # 🔁 stats
    updated["order_count"] = existing.get("order_count", 0) + 1
    updated["last_order_at"] = datetime.utcnow()
    updated["updated_at"] = datetime.utcnow()

    return updated


# =========================================
# 🟢 FIND OR CREATE LOGIC (CORE)
# =========================================

async def find_or_create_customer(parsed: Dict[str, Any], db) -> Dict[str, Any]:
    """
    أهم function في النظام:
    - يبحث عن العميل
    - أو ينشئ واحد جديد
    """

    phone = normalize_phone(parsed.get("phone"))
    name = normalize_name(parsed.get("name"))
    location = normalize_location(parsed.get("location"))

    fingerprint = generate_fingerprint(phone, name, location)

    # =========================
    # 🔍 1. البحث بالـ fingerprint
    # =========================
    existing = await db.customers.find_one({"fingerprint": fingerprint})

    if existing:
        updated = merge_customer(existing, {
            "phone": phone,
            "name": name,
            "location": location
        })

        await db.customers.update_one(
            {"_id": existing["_id"]},
            {"$set": updated}
        )

        return updated

    # =========================
    # 🔍 2. fallback: البحث بالهاتف
    # =========================
    if phone:
        existing = await db.customers.find_one({"phone": phone})

        if existing:
            updated = merge_customer(existing, {
                "phone": phone,
                "name": name,
                "location": location
            })

            await db.customers.update_one(
                {"_id": existing["_id"]},
                {"$set": updated}
            )

            return updated

    # =========================
    # 🆕 3. create new
    # =========================
    new_customer = build_customer(parsed)

    await db.customers.insert_one(new_customer)

    return new_customer