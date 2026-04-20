# app/services/visitor_service.py

from datetime import datetime
from app.core.database import db

async def create_or_get_visitor(data: dict):
    collection = db["visitors"]

    existing = collection.find_one({
        "fingerprint": data["fingerprint"]
    })

    if existing:
        return existing

    data["created_at"] = datetime.utcnow()

    collection.insert_one(data)

    return data