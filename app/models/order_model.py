# app/models/order.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


# ================================
# 📦 ORDER ITEM
# ================================
class OrderItem(BaseModel):
    product: str
    quantity: int = 1
    color: Optional[str] = "غير محدد"
    size: Optional[str] = "?"
    name: Optional[str] = None
    
    # ================================
    # 💰 PRICING FIELDS (FIXED)
    # ================================
    price: Optional[float] = 0.0
    total: Optional[float] = None

    class Config:
        extra = "allow"


# ================================
# 🧾 ORDER MODEL (PRODUCTION READY)
# ================================
class Order(BaseModel):
    # ================================
    # 🆔 CORE
    # ================================
    id: str
    timestamp: str

    # ================================
    # 👤 CUSTOMER
    # ================================
    customer_name: Optional[str] = "⚠️"
    customer_id: Optional[str] = None
    phone: Optional[str] = None

    # ================================
    # 📍 LOCATION
    # ================================
    address: Optional[Dict[str, Any]] = None
    location: Optional[Dict[str, Any]] = None  # {province, district, area, full}

    # ================================
    # 📦 ITEMS
    # ================================
    items: List[OrderItem]

    # ================================
    # 🧠 PARSER / RAW DATA
    # ================================
    messages: List[str] = Field(default_factory=list)
    raw_message: str

    # ================================
    # ⚙️ DECISION ENGINE
    # ================================
    decision: Optional[str] = None
    needs_review: Optional[bool] = False
    warnings: List[str] = Field(default_factory=list)

    # ================================
    # 🧠 IDENTITY SYSTEM
    # ================================
    identity_status: str = "new"
    identity_reason: Optional[str] = None

    # ================================
    # 💳 PAYMENT SYSTEM
    # ================================
    payment_type: str = "COD"
    payment_value: Optional[float] = None
    shipping_fee: Optional[float] = 0.0
    payment_status: str = "unpaid"
    items_total: float = 0.0
    total_amount: float = 0.0
    # ================================
    # 📊 ORDER STATE (BUSINESS FLOW)
    # ================================
    status: str = "draft"  
    # draft | confirmed

    order_stage: str = "new"  
    # new | confirming | ready | delivery | completed | cancelled

    # ================================
    # 🧠 SYSTEM META (IMPORTANT)
    # ================================
    is_returning: Optional[bool] = False
    fingerprint: Optional[str] = None
    created_at: Optional[float] = None
    updated_at: Optional[float] = None
 
    # ================================
    # ⚙️ FLEXIBILITY (CRITICAL)
    # ================================
    class Config:
        extra = "allow"