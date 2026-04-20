# app/api/customer_routes_api.py

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, List, Optional
from datetime import datetime

# Services
from app.services.customer_service import find_or_create_customer, merge_customer
from app.utils.fingerprint import fingerprint_from_parsed

# DB
from app.core.database import get_db

router = APIRouter(prefix="/customers", tags=["Customers"])


# =========================================
# 🟢 GET CUSTOMER BY ID
# =========================================

@router.get("/{customer_id}")
async def get_customer(customer_id: str, db=Depends(get_db)):
    customer = await db.customers.find_one({"_id": customer_id})

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    return customer


# =========================================
# 🟢 LIST CUSTOMERS
# =========================================

@router.get("/")
async def list_customers(
    limit: int = Query(50, le=200),
    skip: int = Query(0),
    db=Depends(get_db)
):
    cursor = db.customers.find().sort("updated_at", -1).skip(skip).limit(limit)

    customers = []
    async for doc in cursor:
        customers.append(doc)

    return {
        "customers": customers,
        "count": len(customers)
    }


# =========================================
# 🟢 SEARCH CUSTOMER (IMPORTANT)
# =========================================

@router.get("/search/")
async def search_customers(
    phone: Optional[str] = None,
    name: Optional[str] = None,
    db=Depends(get_db)
):
    query = {}

    if phone:
        query["phone"] = phone

    if name:
        query["name"] = {"$regex": name.lower(), "$options": "i"}

    if not query:
        raise HTTPException(status_code=400, detail="Provide phone or name")

    cursor = db.customers.find(query).limit(50)

    results = []
    async for doc in cursor:
        results.append(doc)

    return {"results": results}


# =========================================
# 🟢 CREATE / FIND CUSTOMER (API ENTRY)
# =========================================

@router.post("/")
async def create_or_find_customer(payload: Dict[str, Any], db=Depends(get_db)):
    """
    يستعمل من frontend أو internal tools
    """

    parsed = payload.get("parsed")

    if not parsed:
        raise HTTPException(status_code=400, detail="Missing parsed data")

    customer = await find_or_create_customer(parsed, db)

    return {
        "success": True,
        "customer": customer
    }


# =========================================
# 🟢 UPDATE CUSTOMER
# =========================================

@router.put("/{customer_id}")
async def update_customer(customer_id: str, payload: Dict[str, Any], db=Depends(get_db)):
    existing = await db.customers.find_one({"_id": customer_id})

    if not existing:
        raise HTTPException(status_code=404, detail="Customer not found")

    updates = payload.get("updates")

    if not updates:
        raise HTTPException(status_code=400, detail="Missing updates")

    # 🔁 merge logic
    updated = merge_customer(existing, updates)

    await db.customers.update_one(
        {"_id": customer_id},
        {"$set": updated}
    )

    return {
        "success": True,
        "customer": updated
    }


# =========================================
# 🟢 GET CUSTOMER ORDERS
# =========================================

@router.get("/{customer_id}/orders")
async def get_customer_orders(
    customer_id: str,
    limit: int = 50,
    db=Depends(get_db)
):
    cursor = db.orders.find(
        {"customer_id": customer_id}
    ).sort("created_at", -1).limit(limit)

    orders = []
    async for doc in cursor:
        orders.append(doc)

    return {"orders": orders}


# =========================================
# 🟢 MERGE CUSTOMERS (CRITICAL FEATURE 🔥)
# =========================================

@router.post("/merge")
async def merge_customers(payload: Dict[str, Any], db=Depends(get_db)):
    """
    🔥 دمج عميلين (Backend is the single source of truth)
    """

    source_id = payload.get("source_id")
    target_id = payload.get("target_id")

    # ✅ Validation قوي
    if not source_id or not target_id:
        raise HTTPException(status_code=400, detail="Missing IDs")

    if source_id == target_id:
        raise HTTPException(status_code=400, detail="Cannot merge same customer")

    source = await db.customers.find_one({"_id": source_id})
    target = await db.customers.find_one({"_id": target_id})

    if not source or not target:
        raise HTTPException(status_code=404, detail="Customer not found")

    # 🔥 استخدم merge_service (بدل merge_customer المباشر)
    result = merge_customer(target, source)

    # 🟢 تحديث الهدف
    await db.customers.update_one(
        {"_id": target_id},
        {"$set": result}
    )

    # 🟢 نقل الطلبات
    await db.orders.update_many(
        {"customer_id": source_id},
        {"$set": {"customer_id": target_id}}
    )

    # 🗑️ حذف المصدر
    await db.customers.delete_one({"_id": source_id})
    print(f"[MERGE] {source_id} → {target_id}")
    # 🔥 إرجاع بيانات غنية للـ frontend
    return {
        "success": True,
        "merged_into": target_id,
        "merged_customer": result,
        "source_deleted": source_id,
        "updated_orders": True
    }

# =========================================
# 🟢 DELETE CUSTOMER
# =========================================

@router.delete("/{customer_id}")
async def delete_customer(customer_id: str, db=Depends(get_db)):
    customer = await db.customers.find_one({"_id": customer_id})

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # ⚠️ لا نحذف الطلبات (data safety)
    await db.customers.delete_one({"_id": customer_id})

    return {"success": True}
