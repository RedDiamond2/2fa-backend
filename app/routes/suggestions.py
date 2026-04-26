# app/routes/suggestions.py

from fastapi import APIRouter, HTTPException
from datetime import datetime
from app.core.database import suggestions_collection, db
from fastapi import Request
from app.services.identity_service import resolve_identity

router = APIRouter()


@router.post("/suggestions")
async def create_suggestion(request: Request, data: dict):
    # ================================
    # 🧼 BASIC EXTRACTION (SAFE)
    # ================================
    name = (data.get("name") or "").strip()
    message = (data.get("message") or "").strip()

    insights = data.get("insights") or {}
    meta = data.get("meta") or {}

    # ================================
    # 🧠 VALIDATION (NEW - قوي)
    # ================================
    if len(message) < 10:
        raise HTTPException(status_code=400, detail="message too short")

    if len(message.split()) < 3:
        raise HTTPException(status_code=400, detail="message not meaningful")

    # optional name (لا نكسر القديم)
    if name and len(name) < 2:
        raise HTTPException(status_code=400, detail="invalid name")

    # ================================
    # 🧠 VISITOR LINKING
    # ================================
    visitor_id = data.get("visitor_id")

    if not visitor_id:
        fingerprint = meta.get("fingerprint")
        if fingerprint and db is not None:
            visitors_col = db["visitors"]
            if visitors_col:
                visitor = await visitors_col.find_one({"fingerprint": fingerprint})
            else:
                visitor = None

            if visitor:
                visitor_id = str(visitor["_id"])

    # ================================
    # 🧠 IDENTITY RESOLUTION (AFTER LINKING 🔥)
    # ================================
    identity = await resolve_identity(
        {"name": name, "meta": meta, "visitor_id": visitor_id}
    )

    # ================================
    # 🧠 NORMALIZE INSIGHTS (NEW)
    # ================================
    safe_insights = {
        "volume": insights.get("volume"),
        "response_time": insights.get("response_time"),
        "crm_usage": insights.get("crm_usage"),
        "willing_to_pay": insights.get("willing_to_pay"),
        "channels": insights.get("channels", []),
        "problems": insights.get("problems", []),
    }

    # ================================
    # 🧠 CLEAN MESSAGE (SECURITY)
    # ================================
    clean_message = message[:1000]

    # ================================
    # 💾 DOCUMENT
    # ================================
    suggestion = {
        "name": name or None,
        "message": clean_message,
        # 🔥 NEW POWER
        "insights": safe_insights,
        # 🔗 visitor tracking
        "visitor_id": visitor_id,
        # 🧠 identity graph
        "identity": identity,
        "customer_id": identity.get("customer_id") if identity else None,
        "meta": meta,
        "created_at": datetime.utcnow(),
    }

    await suggestions_collection.insert_one(suggestion)

    return {"success": True}
