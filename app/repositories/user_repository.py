# app/repositories/user_repository.py

from typing import Dict, Any, Optional, List

from app.models.user_model import UserModel
from app.core.database import get_database


# =========================
# 👤 USER REPOSITORY
# =========================

class UserRepository:
    def __init__(self):
        db = get_database()
        self.model = UserModel(db)

    # =========================
    # CREATE
    # =========================
    async def create(self, user: Dict[str, Any]) -> Dict[str, Any]:
        return await self.model.create_user(user)

    # =========================
    # FIND BY EMAIL
    # =========================
    async def find_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        return await self.model.find_by_email(email)

    # =========================
    # FIND BY ID
    # =========================
    async def find_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return await self.model.find_by_id(user_id)

    # =========================
    # UPDATE
    # =========================
    async def update(self, user_id: str, data: Dict[str, Any]):
        return await self.model.update_user(user_id, data)

    # =========================
    # DELETE
    # =========================
    async def delete(self, user_id: str) -> bool:
        return await self.model.delete_user(user_id)

    # =========================
    # LIST
    # =========================
    async def list(self, limit: int = 50) -> List[Dict[str, Any]]:
        return await self.model.list_users(limit)