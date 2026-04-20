# app/routes/comment_routes.py

from fastapi import APIRouter, HTTPException
from app.core.database import db
from uuid import uuid4
from datetime import datetime

router = APIRouter(prefix="/comments", tags=["comments"])


# 🧼 Helper لتحويل Mongo
def serialize_comment(c):
    return {
        "id": c.get("id"),
        "name": c.get("name", "مستخدم"),
        "text": c.get("text"),
        "likes": c.get("likes", 0),
        "liked_by": c.get("liked_by", []),
        "replies": c.get("replies", []),
        "created_at": c.get("created_at").isoformat() if c.get("created_at") else None,
        "order_id": c.get("order_id")  # 🔗 Include order_id in response
    }


# 📥 Get all comments
@router.get("/")
async def get_comments():
    comments = list(db.comments.find().sort("created_at", -1))
    return [serialize_comment(c) for c in comments]


# 📥 Get comments by order_id
@router.get("/order/{order_id}")
async def get_comments_by_order(order_id: str):
    """Fetch all comments associated with a specific order"""
    comments = list(db.comments.find({"order_id": order_id}).sort("created_at", -1))
    return [serialize_comment(c) for c in comments]


# ➕ Add comment
@router.post("/")
async def add_comment(data: dict):
    if "text" not in data or not data["text"].strip():
        raise HTTPException(status_code=400, detail="Comment text required")

    comment = {
        "id": str(uuid4()),
        "name": data.get("name", "مستخدم"),
        "text": data["text"].strip(),
        "likes": 0,
        "liked_by": [],
        "replies": [],
        "created_at": datetime.utcnow(),
        "order_id": data.get("order_id")  # 🔗 Accept order_id from frontend
    }

    result = db.comments.insert_one(comment)

    # ❗ الحل النهائي لمشكل ObjectId
    comment["_id"] = str(result.inserted_id)

    return serialize_comment(comment)


# ❤️ Like toggle (احترافي)
@router.post("/{comment_id}/like/")
async def like_comment(comment_id: str, user_id: str = "anon"):
    comment = db.comments.find_one({"id": comment_id})

    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if user_id in comment.get("liked_by", []):
        db.comments.update_one(
            {"id": comment_id},
            {
                "$pull": {"liked_by": user_id},
                "$inc": {"likes": -1}
            }
        )
        liked = False
    else:
        db.comments.update_one(
            {"id": comment_id},
            {
                "$push": {"liked_by": user_id},
                "$inc": {"likes": 1}
            }
        )
        liked = True

    updated = db.comments.find_one({"id": comment_id})

    return {
        "success": True,
        "liked": liked,
        "likes": updated.get("likes", 0)
    }


# 💬 Add reply
@router.post("/{comment_id}/reply/")
async def add_reply(comment_id: str, data: dict):
    if "text" not in data or not data["text"].strip():
        raise HTTPException(status_code=400, detail="Reply text required")

    reply = {
        "id": str(uuid4()),
        "name": data.get("name", "مستخدم"),
        "text": data["text"].strip(),
        "created_at": datetime.utcnow()
    }

    result = db.comments.update_one(
        {"id": comment_id},
        {"$push": {"replies": reply}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Comment not found")

    return reply