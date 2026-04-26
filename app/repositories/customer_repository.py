# app/repositories/customer_repository.py

from typing import Dict, Any, Optional
from app.core.database import customers_collection


# =========================================
# 🟢 CUSTOMER REPOSITORY
# =========================================


class CustomerRepository:
    @staticmethod
    async def find_by_phone(phone: str) -> Optional[Dict[str, Any]]:
        if not phone or customers_collection is None:
            return None

        return await customers_collection.find_one({"phone": phone})

    @staticmethod
    async def find_by_id(customer_id: str) -> Optional[Dict[str, Any]]:
        if not customer_id or customers_collection is None:
            return None

        return await customers_collection.find_one({"_id": customer_id})

    @staticmethod
    async def insert(customer: Dict[str, Any]) -> Any:
        if customers_collection is None:
            return None

        return await customers_collection.insert_one(customer)

    @staticmethod
    async def update(customer_id: str, data: Dict[str, Any]) -> Any:
        if customers_collection is None:
            return None

        return await customers_collection.update_one(
            {"_id": customer_id}, {"$set": data}
        )
