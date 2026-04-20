# app/routes/admin_routes.py

from fastapi import APIRouter, HTTPException
from app.core.config import settings
# app/routes/admin_routes.py
from pymongo import MongoClient
import os

router = APIRouter(prefix="/admin", tags=["admin"])

# ⚠️ نفس الاتصال الموجود عندك
client = MongoClient(settings.MONGO_URL)


@router.delete("/drop-db")
def drop_database(secret: str = None):
    """
    ⚠️ DANGER: Delete entire database
    """

    # 🔐 حماية بسيطة (اختياري لكن مهم)
    ADMIN_SECRET = os.getenv("ADMIN_SECRET", "1234")

    if secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        client.drop_database(settings.DB_NAME)
        return {"success": True, "message": f"Database '{settings.DB_NAME}' deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))