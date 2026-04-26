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
    phone = "".join(filter(str.isdigit, phone))

    if phone.startswith("213") and len(phone) == 12:
        phone = "0" + phone[3:]

    if len(phone) != 10:
        return None

    return phone


def normalize_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None

    name = str(name).strip().lower()

    if len(name) < 3:
        return None

    if name in ["unknown", "???", "⚠️"]:
        return None

    return name


def normalize_location(location: Any) -> Optional[str]:
    if not location:
        return None

    if isinstance(location, dict):
        province = location.get("province")
        if province:
            return str(province).strip().lower()

    if isinstance(location, str):
        return location.strip().lower()

    return None


# =========================================
# 🟢 FINGERPRINT GENERATION
# =========================================


def generate_fingerprint(
    phone: Optional[str], name: Optional[str], location: Optional[str]
) -> str:
    base = f"{phone or ''}|{name or ''}|{location or ''}"
    return hashlib.sha256(base.encode()).hexdigest()


# =========================================
# 🟢 CUSTOMER BUILDER
# =========================================


def build_customer(parsed: Dict[str, Any]) -> Dict[str, Any]:
    phone = normalize_phone(parsed.get("phone"))
    name = normalize_name(parsed.get("name"))
    location = normalize_location(parsed.get("location"))

    fingerprint = generate_fingerprint(phone, name, location)

    now = datetime.utcnow()

    return {
        "fingerprint": fingerprint,
        "phone": phone,
        "name": name,
        "location": location,
        "created_at": now,
        "updated_at": now,
        "order_count": 0,
        "last_order_at": None,
    }


# =========================================
# 🟢 CUSTOMER MERGE (SAFE + STRONG)
# =========================================


def merge_customer(
    existing: Dict[str, Any], new_data: Dict[str, Any]
) -> Dict[str, Any]:
    updated = existing.copy()

    new_name = normalize_name(new_data.get("name"))
    new_phone = normalize_phone(new_data.get("phone"))
    new_location = normalize_location(new_data.get("location"))

    # name → keep الأفضل
    if new_name and (
        not existing.get("name") or len(new_name) > len(existing.get("name", ""))
    ):
        updated["name"] = new_name

    # phone → overwrite if valid
    if new_phone:
        updated["phone"] = new_phone

    # location
    if new_location:
        updated["location"] = new_location

    # stats
    updated["order_count"] = int(existing.get("order_count", 0)) + 1
    updated["last_order_at"] = datetime.utcnow()
    updated["updated_at"] = datetime.utcnow()

    return updated


# =========================================
# 🟢 FIND OR CREATE LOGIC (PRODUCTION SAFE)
# =========================================


async def find_or_create_customer(parsed: Dict[str, Any], db) -> Dict[str, Any]:
    phone = normalize_phone(parsed.get("phone"))
    name = normalize_name(parsed.get("name"))
    location = normalize_location(parsed.get("location"))

    fingerprint = generate_fingerprint(phone, name, location)

    customers_col = db["customers"]

    # =========================
    # 🔍 1. fingerprint
    # =========================
    existing = await customers_col.find_one({"fingerprint": fingerprint})

    if existing:
        updated = merge_customer(
            existing, {"phone": phone, "name": name, "location": location}
        )

        await customers_col.update_one({"_id": existing["_id"]}, {"$set": updated})

        return updated

    # =========================
    # 🔍 2. phone fallback
    # =========================
    if phone:
        existing = await customers_col.find_one({"phone": phone})

        if existing:
            updated = merge_customer(
                existing, {"phone": phone, "name": name, "location": location}
            )

            await customers_col.update_one({"_id": existing["_id"]}, {"$set": updated})

            return updated

    # =========================
    # 🆕 3. create
    # =========================
    new_customer = build_customer(parsed)

    result = await customers_col.insert_one(new_customer)
    new_customer["_id"] = result.inserted_id

    return new_customer
