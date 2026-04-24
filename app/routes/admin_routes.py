# app/routes/admin_routes.py

from fastapi import APIRouter, HTTPException, Header, Depends
from app.core.database import get_database
from datetime import datetime
import os
import logging

router = APIRouter(prefix="/admin", tags=["admin"])

logger = logging.getLogger("admin_routes")


def get_db():
    return get_database()


@router.delete("/clear-collections")
async def clear_collections(x_admin_secret: str = Header(None), db=Depends(get_db)):
    ADMIN_SECRET = os.getenv("ADMIN_SECRET", "1234")

    if not x_admin_secret or x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        all_collections = await db.list_collection_names()

        excluded_collections = {"comments", "visitors"}

        target_collections = [
            col for col in all_collections if col not in excluded_collections
        ]

        result = {}

        logger.warning(
            f"[ADMIN] Clear collections triggered at {datetime.utcnow()} | "
            f"Target: {target_collections}"
        )

        for name in target_collections:
            deleted = await db[name].delete_many({})
            result[name] = deleted.deleted_count

            logger.info(f"[ADMIN] Cleared {name}: {deleted.deleted_count} docs")

        return {
            "success": True,
            "message": "Collections cleared successfully (comments preserved)",
            "excluded": list(excluded_collections),
            "details": result,
        }

    except Exception as e:
        logger.error(f"[ADMIN] Clear failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
