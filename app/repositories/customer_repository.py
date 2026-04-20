# app/repositories/customer_repository.py
from app.core.database import customers_collection

class CustomerRepository:

    @staticmethod
    def find_by_phone(phone: str):
        return customers_collection.find_one({"phone": phone})

    @staticmethod
    def insert(customer: dict):
        return customers_collection.insert_one(customer)

    @staticmethod
    def update(customer_id: str, data: dict):
        return customers_collection.update_one(
            {"id": customer_id},
            {"$set": data}
        )