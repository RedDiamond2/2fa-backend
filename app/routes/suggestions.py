# app/routes/suggestions.py

from fastapi import APIRouter, HTTPException
from datetime import datetime
from app.core.database import suggestions_collection, db

router = APIRouter()

@router.post("/suggestions")
async def create_suggestion(data: dict):

    name = data.get("name", "").strip()
    message = data.get("message", "").strip()

    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    visitor_id = data.get("visitor_id")

    # 🔥 fallback: حاول الربط عن طريق fingerprint
    if not visitor_id:
        fingerprint = data.get("meta", {}).get("fingerprint")
        if fingerprint:
            visitor = db["visitors"].find_one({"fingerprint": fingerprint})
            if visitor:
                visitor_id = str(visitor["_id"])

    suggestion = {
        "name": name,
        "message": message,
        "visitor_id": visitor_id,
        "meta": data.get("meta", {}),
        "created_at": datetime.utcnow()
    }

    suggestions_collection.insert_one(suggestion)

    return {"success": True}