# app/models/user_model.py

from datetime import datetime
from typing import Optional, Dict, Any, List
from bson import ObjectId
from app.core.database import get_database


class UserRepository:
    def __init__(self):
        db = get_database()
        self.model = UserModel(db)

    async def create(self, user: Dict[str, Any]):
        return await self.model.create_user(user)

    async def find_by_email(self, email: str):
        return await self.model.find_by_email(email)

    async def find_by_id(self, user_id: str):
        return await self.model.find_by_id(user_id)

    async def update(self, user_id: str, data: Dict[str, Any]):
        return await self.model.update_user(user_id, data)

    async def delete(self, user_id: str):
        return await self.model.delete_user(user_id)

    async def list(self, limit: int = 50):
        return await self.model.list_users(limit)

# =========================
# 👤 USER MODEL
# =========================

class UserModel:
    COLLECTION_NAME = "users"

    def __init__(self, db):
        self.collection = db[self.COLLECTION_NAME]

    # =========================
    # CREATE USER
    # =========================
    async def create_user(self, user: Dict[str, Any]) -> Dict[str, Any]:
        user["created_at"] = datetime.utcnow()
        user["last_login"] = None
        user["role"] = user.get("role", "trader")

        result = await self.collection.insert_one(user)
        user["_id"] = result.inserted_id

        return user

    # =========================
    # FIND BY EMAIL
    # =========================
    async def find_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one({"email": email})

    # =========================
    # FIND BY ID
    # =========================
    async def find_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        try:
            return await self.collection.find_one({"_id": ObjectId(user_id)})
        except Exception:
            return None

    # =========================
    # UPDATE USER
    # =========================
    async def update_user(self, user_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            await self.collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_data}
            )
            return await self.find_by_id(user_id)
        except Exception:
            return None

    # =========================
    # DELETE USER
    # =========================
    async def delete_user(self, user_id: str) -> bool:
        try:
            result = await self.collection.delete_one({"_id": ObjectId(user_id)})
            return result.deleted_count > 0
        except Exception:
            return False

    # =========================
    # LIST USERS
    # =========================
    async def list_users(self, limit: int = 50) -> List[Dict[str, Any]]:
        cursor = self.collection.find().limit(limit)
        return await cursor.to_list(length=limit)


class UserRepository:
    def __init__(self):
        db = get_database()
        self.model = UserModel(db)

    async def create(self, user: Dict[str, Any]):
        return await self.model.create_user(user)

    async def find_by_email(self, email: str):
        return await self.model.find_by_email(email)

    async def find_by_id(self, user_id: str):
        return await self.model.find_by_id(user_id)

    async def update(self, user_id: str, data: Dict[str, Any]):
        return await self.model.update_user(user_id, data)

    async def delete(self, user_id: str):
        return await self.model.delete_user(user_id)

    async def list(self, limit: int = 50):
        return await self.model.list_users(limit)