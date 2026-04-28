# app/services/visitor_service.py

from datetime import datetime
from typing import Dict, Any
from app.core.database import get_database


async def create_or_get_visitor(data: Dict[str, Any]) -> Dict[str, Any]:
    db = get_database()
    collection = db["visitors"]

    fingerprint = (data.get("fingerprint") or "").strip()

    if not fingerprint:
        return {
            "status": "invalid",
            "reason": "missing_fingerprint",
        }

    # =========================
    # 🔍 FIND EXISTING
    # =========================
    existing = await collection.find_one({"fingerprint": fingerprint})

    if existing:
        # 🧠 soft update meta (non-destructive)
        update_fields = {}

        for field in ["ip", "user_agent"]:
            if data.get("location"):
                update_fields["location"] = data["location"]

            if data.get("hardware"):
                update_fields["hardware"] = data["hardware"]
            if data.get(field) and not existing.get(field):
                update_fields[field] = data[field]

        if update_fields:
            update_fields["updated_at"] = datetime.utcnow()

            await collection.update_one(
                {"_id": existing["_id"]}, {"$set": update_fields}
            )

            existing.update(update_fields)

        return existing

    # =========================
    # 🆕 CREATE NEW VISITOR
    # =========================
    now = datetime.utcnow()

    visitor = {
        "fingerprint": fingerprint,
        # optional meta
        "ip": data.get("ip"),
        "location": data.get("location"),
        "hardware": data.get("hardware"),
        "raw_fp": data.get("raw_fp"),
        "user_agent": data.get("user_agent"),
        # linking
        "linked_customer_id": None,
        # timestamps
        "created_at": now,
        "updated_at": now,
    }

    result = await collection.insert_one(visitor)
    visitor["_id"] = result.inserted_id

    return visitor
