# app/models/customer.py
from pydantic import BaseModel
from typing import Optional

class Customer(BaseModel):
    id: str
    name: str
    phone: Optional[str] = None  # 🔥 الحل هنا