# app/routes/customer_routes.py

from fastapi import APIRouter
from app.core.database import customers_collection, generate_id
from app.models.customer_model import Customer

router = APIRouter()

# ================================
# ➕ Create Customer
# ================================
@router.post("/customers")
def create_customer(name: str, phone: str = None):
    customer_id = generate_id()

    customer = {
        "id": customer_id,
        "name": name,
        "phone": phone
    }

    customers_collection.insert_one(customer)

    return customer


# ================================
# 📥 Get Customers
# ================================
@router.get("/customers")
def get_customers():
    customers = list(customers_collection.find({}, {"_id": 0}))
    return customers