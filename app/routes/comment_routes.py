from fastapi import APIRouter, HTTPException
from uuid import uuid4
from datetime import datetime
from app.core.database import get_database

router = APIRouter(prefix="/comments", tags=["comments"])


def safe_time(t):
    """معالجة التواريخ لضمان التوافق مع JSON"""
    if hasattr(t, "isoformat"):
        return t.isoformat()
    if isinstance(t, dict) and "$date" in t:
        return t["$date"]
    return t


def serialize_comment(c):
    """تحويل وثيقة MongoDB إلى JSON احترافي وقابل للقراءة"""
    return {
        "id": c.get("id") or str(c.get("_id")),
        "_id": str(c.get("_id")) if c.get("_id") else None,
        "name": c.get("name", "مستخدم"),
        "text": c.get("text"),
        "likes": c.get("likes", 0),
        "liked_by": c.get("liked_by", []),
        "replies": [
            {
                "id": r.get("id"),
                "name": r.get("name", "مستخدم"),
                "text": r.get("text"),
                "created_at": safe_time(r.get("created_at")),
            }
            for r in c.get("replies", [])
        ],
        "created_at": safe_time(c.get("created_at")),
        "order_id": c.get("order_id"),
    }


@router.get("/")
async def get_comments():
    db = get_database()
    cursor = db["comments"].find({}).sort("created_at", -1)
    comments = await cursor.to_list(length=None)
    return [serialize_comment(c) for c in comments]


@router.get("/order/{order_id}")
async def get_comments_by_order(order_id: str):
    db = get_database()
    cursor = db["comments"].find({"order_id": order_id}).sort("created_at", -1)
    comments = await cursor.to_list(length=None)
    return [serialize_comment(c) for c in comments]


@router.post("/")
async def add_comment(data: dict):
    if "text" not in data or not data["text"].strip():
        raise HTTPException(status_code=400, detail="Comment text required")

    db = get_database()
    comment = {
        "id": str(uuid4()),
        "name": data.get("name", "مستخدم"),
        "text": data["text"].strip(),
        "likes": 0,
        "liked_by": [],
        "replies": [],
        "created_at": datetime.utcnow(),
        "order_id": data.get("order_id"),
    }

    result = await db["comments"].insert_one(comment)
    comment["_id"] = str(result.inserted_id)

    return serialize_comment(comment)


@router.post("/{comment_id}/like")
async def like_comment(comment_id: str, user_id: str = "anon"):
    db = get_database()
    comment = await db["comments"].find_one({"id": comment_id})

    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")

    if user_id in comment.get("liked_by", []):
        await db["comments"].update_one(
            {"id": comment_id}, {"$pull": {"liked_by": user_id}, "$inc": {"likes": -1}}
        )
        liked = False
    else:
        await db["comments"].update_one(
            {"id": comment_id}, {"$push": {"liked_by": user_id}, "$inc": {"likes": 1}}
        )
        liked = True

    updated = await db["comments"].find_one({"id": comment_id})

    return {"success": True, "liked": liked, "likes": updated.get("likes", 0)}


@router.post("/{comment_id}/reply")
async def add_reply(comment_id: str, data: dict):
    if "text" not in data or not data["text"].strip():
        raise HTTPException(status_code=400, detail="Reply text required")

    db = get_database()
    reply = {
        "id": str(uuid4()),
        "name": data.get("name", "مستخدم"),
        "text": data["text"].strip(),
        "created_at": datetime.utcnow(),
    }

    result = await db["comments"].update_one(
        {"id": comment_id}, {"$push": {"replies": reply}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Comment not found")

    reply_response = reply.copy()
    reply_response["created_at"] = reply["created_at"].isoformat()

    return reply_response
