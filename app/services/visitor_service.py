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
        update_fields: Dict[str, Any] = {}

        # 🔄 Always refresh dynamic fields
        update_fields["last_seen"] = datetime.utcnow()
        if data.get("ip"):
            update_fields["ip"] = data["ip"]

        # 🧠 Merge location (non-destructive)
        if data.get("location"):
            merged_location = {
                **(existing.get("location") or {}),
                **data.get("location"),
            }
            update_fields["location"] = merged_location

        # 🧠 Merge hardware (non-destructive)
        if data.get("hardware"):
            merged_hardware = {
                **(existing.get("hardware") or {}),
                **data.get("hardware"),
            }
            update_fields["hardware"] = merged_hardware

        # 🧬 Raw fingerprint enrichment (append-only style)
        if data.get("raw_fp"):
            update_fields["raw_fp"] = data["raw_fp"]

        # 🌐 Network / UA enrichment
        if data.get("user_agent") and not existing.get("user_agent"):
            update_fields["user_agent"] = data["user_agent"]

        if data.get("isp_org"):
            update_fields["isp_org"] = data["isp_org"]

        # 🔐 Security signals
        for field in ["is_vpn", "is_proxy", "is_hosting"]:
            if field in data:
                update_fields[field] = data[field]

        # 🔁 Counters
        update_fields["visit_count"] = (existing.get("visit_count") or 0) + 1

        # 🕒 Keep first_seen stable
        if not existing.get("first_seen"):
            update_fields["first_seen"] = datetime.utcnow()

        if update_fields:
            update_fields["updated_at"] = datetime.utcnow()

            await collection.update_one(
                {"_id": existing["_id"]},
                {"$set": update_fields},
            )

            existing.update(update_fields)

        existing["_id"] = str(existing["_id"])
        return existing

    # =========================
    # 🆕 CREATE NEW VISITOR
    # =========================
    now = datetime.utcnow()

    visitor = {
        "fingerprint": fingerprint,
        # 🌐 network
        "ip": data.get("ip"),
        "user_agent": data.get("user_agent"),
        "isp_org": data.get("isp_org"),
        # 🔐 security
        "is_vpn": data.get("is_vpn", False),
        "is_proxy": data.get("is_proxy", False),
        "is_hosting": data.get("is_hosting", False),
        # 📍 location
        "location": data.get("location") or {},
        # 💻 hardware
        "hardware": data.get("hardware") or {},
        # 🧬 raw fingerprint
        "raw_fp": data.get("raw_fp") or {},
        # 🧩 linking
        "linked_customer_id": None,
        # 📊 metrics
        "visit_count": 1,
        "incognito_mode": data.get("incognito_mode", False),
        # 🕒 timestamps
        "first_seen": now,
        "last_seen": now,
        "created_at": now,
        "updated_at": now,
    }

    result = await collection.insert_one(visitor)
    visitor["_id"] = str(result.inserted_id)

    return visitor
