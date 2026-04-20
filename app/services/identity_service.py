# app/services/identity_service.py
from typing import Dict, Optional
from app.core.database import customers_collection


def resolve_identity(data: Dict) -> Dict:
    phone = data.get("phone")
    name = (data.get("name") or "").strip()
    location = data.get("location")

    # =========================
    # 📞 PHONE MATCH
    # =========================
    if phone:
        existing = customers_collection.find_one({"phone": phone})
        if existing:
            return {
                "status": "same",
                "reason": "phone_match",
                "customer_id": existing["id"]
            }

    # =========================
    # 💳 PAYMENT MATCH
    # =========================
    payment_value = data.get("payment_value")
    if payment_value:
        existing = customers_collection.find_one({
            "payment_identities.value": payment_value
        })
        if existing:
            return {
                "status": "same",
                "reason": "payment_match",
                "customer_id": existing["id"]
            }

    # =========================
    # 🧠 NAME + LOCATION
    # =========================
    if name and location:
        similar = customers_collection.find_one({
            "name": name,
            "last_location": location
        })
        if similar:
            return {
                "status": "suspicious",
                "reason": "name_location_match",
                "customer_id": similar["id"]
            }

    # =========================
    # ⚠️ PENDING
    # =========================
    if not phone and not payment_value:
        return {
            "status": "pending",
            "reason": "no_identity_data",
            "customer_id": None
        }

    return {
        "status": "new",
        "reason": "no_match",
        "customer_id": None
    }