# app/repositories/order_repository.py
from app.core.database import orders_collection

class OrderRepository:

    @staticmethod
    def find_by_fingerprint(fp: str):
        return orders_collection.find_one({"fingerprint": fp})

    @staticmethod
    def insert(order_dict: dict):
        return orders_collection.insert_one(order_dict)

    @staticmethod
    def update(order_id: str, data: dict):
        return orders_collection.update_one(
            {"id": order_id},
            {"$set": data}
        )

    @staticmethod
    def find_recent_by_phone(phone: str):
        return list(orders_collection.find(
            {"phone": phone}
        ).sort("created_at", -1).limit(5))