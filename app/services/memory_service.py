# app/services/memory_service.py

import logging
from typing import Dict, List, Any
from datetime import datetime, timedelta

from app.core.database import memory_collection

# =====================================
# ⚙️ CONFIG & LOGGING
# =====================================
logger = logging.getLogger("memory_service")

MAX_ITEMS_MEMORY = 5
DECAY_DAYS = 30
MIN_CONFIDENCE_THRESHOLD = 0.4


# =====================================
# 🛠️ HELPERS
# =====================================


def smart_pick(new_value: Any, old_value: Any) -> Any:
    if new_value and str(new_value).strip():
        return new_value
    return old_value


def build_item_key(item: Dict) -> str:
    product = str(item.get("product", "")).strip().lower()
    color = str(item.get("color", "")).strip().lower()
    size = str(item.get("size", "")).strip().lower()
    return f"{product}|{color}|{size}"


def normalize_address(address: Any) -> Dict:
    if not address:
        return {}
    if isinstance(address, dict):
        return address
    return {"full": str(address).strip()}


# =====================================
# 📥 GET MEMORY
# =====================================


def get_customer_memory(phone: str) -> Dict:
    if not phone:
        return {}

    try:
        memory = memory_collection.find_one({"phone": phone})
        return memory or {}
    except Exception as e:
        logger.error(f"[MEMORY][GET] Failed for phone={phone}: {e}")
        return {}


# =====================================
# 💾 UPDATE MEMORY
# =====================================


def update_customer_memory(phone: str, parsed: Dict):
    if not phone:
        return

    try:
        confidence = parsed.get("confidence", 1.0)
        source = parsed.get("meta", {}).get("source", "parser")

        if confidence < MIN_CONFIDENCE_THRESHOLD and source != "developer":
            logger.warning(
                f"[MEMORY][SKIP] Low confidence ({confidence}) phone={phone}"
            )
            return

        existing = get_customer_memory(phone)

        updated_memory = {
            "phone": phone,
            "last_items": merge_items(
                existing.get("last_items", []), parsed.get("items", [])
            ),
            "last_location": smart_pick(
                parsed.get("location"), existing.get("last_location")
            ),
            "last_name": smart_pick(parsed.get("name"), existing.get("last_name")),
            "last_address": smart_pick(
                normalize_address(parsed.get("address")),
                existing.get("last_address"),
            ),
            "memory_version": 4,
            "last_source": parsed.get("meta", {}).get("source", "parser"),
            "last_learning_source": source,
            "updated_at": datetime.utcnow(),
        }

        logger.info(
            f"[MEMORY][UPDATE] phone={phone} items={len(updated_memory['last_items'])} conf={confidence}"
        )

        memory_collection.update_one(
            {"phone": phone},
            {
                "$set": updated_memory,
                "$setOnInsert": {"created_at": datetime.utcnow()},
            },
            upsert=True,
        )

    except Exception as e:
        logger.error(f"[MEMORY][UPDATE] Critical failure phone={phone}: {e}")


# =====================================
# 🧠 ENRICH PARSED
# =====================================


def enrich_with_memory(parsed: Dict) -> Dict:
    phone = parsed.get("phone")
    if not phone:
        return parsed

    memory = get_customer_memory(phone)
    if not memory:
        return parsed

    updated_at = memory.get("updated_at")

    if updated_at:
        if isinstance(updated_at, datetime):
            age_days = (datetime.utcnow() - updated_at).days
        else:
            age_days = (datetime.utcnow() - datetime.utcfromtimestamp(updated_at)).days

        if age_days > DECAY_DAYS:
            logger.info(f"[MEMORY][SKIP] Decay {age_days} days phone={phone}")
            return parsed

    used = []

    if not parsed.get("items") and memory.get("last_items"):
        parsed["items"] = memory["last_items"]
        used.append("items")

    if not parsed.get("location") and memory.get("last_location"):
        parsed["location"] = memory["last_location"]
        used.append("location")

    addr_empty = not parsed.get("address") or (
        isinstance(parsed.get("address"), dict) and not parsed["address"].get("full")
    )

    if addr_empty and memory.get("last_address"):
        parsed["address"] = memory["last_address"]
        used.append("address")

    if not parsed.get("name") and memory.get("last_name"):
        parsed["name"] = memory["last_name"]
        used.append("name")

    if used:
        parsed.setdefault("meta", {})
        parsed["meta"].update(
            {
                "memory_used": True,
                "memory_fields": used,
                "memory_age_days": age_days if updated_at else 0,
            }
        )

    return parsed


# =====================================
# 🔀 MERGE ITEMS
# =====================================


def merge_items(old_items: List[Dict], new_items: List[Dict]) -> List[Dict]:
    if not old_items and not new_items:
        return []

    combined = (new_items or []) + (old_items or [])
    seen = set()
    result = []

    for item in combined:
        if not isinstance(item, dict):
            continue

        if not item.get("product"):
            continue

        key = build_item_key(item)

        if key in seen:
            continue

        seen.add(key)
        result.append(item)

        if len(result) >= MAX_ITEMS_MEMORY:
            break

    return result


# =====================================
# 🧹 CLEAN MEMORY
# =====================================


def clean_old_memory():
    try:
        threshold = datetime.utcnow() - timedelta(days=DECAY_DAYS)

        result = memory_collection.delete_many({"updated_at": {"$lt": threshold}})

        if result.deleted_count > 0:
            logger.info(f"[MEMORY][CLEAN] Deleted {result.deleted_count} records")

    except Exception as e:
        logger.error(f"[MEMORY][CLEAN] Failed: {e}")
