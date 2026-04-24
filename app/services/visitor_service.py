# app/services/visitor_service.py

from datetime import datetime
from app.core.database import get_database


async def create_or_get_visitor(data: dict):
    db = get_database()
    collection = db["visitors"]

    # ✅ FIX: async Mongo (Motor)
    existing = await collection.find_one({"fingerprint": data.get("fingerprint")})

    if existing:
        return existing

    data["created_at"] = datetime.utcnow()

    # ✅ FIX: async insert
    result = await collection.insert_one(data)
    data["_id"] = result.inserted_id  # ensure _id exists

    return data
