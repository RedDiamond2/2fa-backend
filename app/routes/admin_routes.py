from fastapi import APIRouter, HTTPException, Header
from app.core.config import settings
from pymongo import MongoClient
from datetime import datetime
import os
import logging

router = APIRouter(prefix="/admin", tags=["admin"])

client = MongoClient(settings.MONGO_URL)
db = client[settings.DB_NAME]

logger = logging.getLogger("admin_routes")


@router.delete("/clear-collections")
def clear_collections(x_admin_secret: str = Header(None)):
    """
    🧹 Clear all collections except comments (SAFE MODE)
    """

    ADMIN_SECRET = os.getenv("ADMIN_SECRET", "1234")

    # 🔐 Security check
    if x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        # 🧠 All collections in DB
        all_collections = db.list_collection_names()

        # 🚫 Never delete comments visitors
        excluded_collections = {"comments","visitors"}

        # 🎯 Target collections = everything except excluded
        target_collections = [
            col for col in all_collections
            if col not in excluded_collections
        ]

        result = {}

        logger.warning(
            f"[ADMIN] Clear collections triggered at {datetime.utcnow()} | "
            f"Target: {target_collections}"
        )

        # 🧹 Delete data safely
        for name in target_collections:
            deleted = db[name].delete_many({})
            result[name] = deleted.deleted_count

            logger.info(f"[ADMIN] Cleared {name}: {deleted.deleted_count} docs")

        return {
            "success": True,
            "message": "Collections cleared successfully (comments preserved)",
            "excluded": list(excluded_collections),
            "details": result
        }

    except Exception as e:
        logger.error(f"[ADMIN] Clear failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))