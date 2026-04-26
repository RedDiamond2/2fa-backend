# app/services/identity_service.py

import re
from typing import Any, Dict, Optional
from datetime import datetime
from app.core.database import get_collections


# --- أدوات مساعدة ذكية (Helper Utils) ---


def normalize_phone_advanced(phone: str) -> str:
    if not phone:
        return ""

    phone = re.sub(r"[^\d]", "", phone)

    if phone.startswith("00"):
        phone = phone[2:]

    if phone.startswith("0") and len(phone) > 10 and not phone.startswith("011"):
        phone = phone[1:]

    return phone


def canonicalize_email(email: str) -> str:
    if not email:
        return ""

    email = email.lower().strip()
    if "@" not in email:
        return email

    username, domain = email.split("@", 1)

    ignore_dots_domains = ["gmail.com", "googlemail.com", "yahoo.com"]

    if domain in ignore_dots_domains:
        username = username.split("+")[0]
        username = username.replace(".", "")

    return f"{username}@{domain}"


def levenshtein_ratio(s1: str, s2: str) -> float:
    if not s1 or not s2:
        return 0.0

    s1, s2 = s1.strip().lower(), s2.strip().lower()

    if len(s1) < len(s2):
        return levenshtein_ratio(s2, s1)

    if len(s2) == 0:
        return 0.0

    previous_row = range(len(s2) + 1)

    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    distance = previous_row[-1]
    max_len = max(len(s1), len(s2))
    return 1.0 - (distance / max_len) if max_len > 0 else 0.0


# --- Identity Graph Search ---


async def find_customer_graph(
    customers_collection, phone: str, email: str, name: str, payment_id: str
) -> Optional[Dict]:
    if customers_collection is None:
        return None

    norm_phone = normalize_phone_advanced(phone)
    norm_email = canonicalize_email(email)

    query = []

    if norm_email:
        query.append({"email_canonical": norm_email})

    if norm_phone:
        query.append({"phone_normalized": norm_phone})

    if payment_id:
        query.append({"payment_identities.value": payment_id})

    if query:
        direct_match = await customers_collection.find_one({"$or": query})
        if direct_match:
            return direct_match

    if name and len(name) > 2:
        async for cust in customers_collection.find({"name": {"$exists": True}}):
            similarity = levenshtein_ratio(name, cust.get("name", ""))
            if similarity > 0.85:
                return cust

    return None


# --- Identity Resolver ---


async def resolve_identity(data: Dict[str, Any]) -> Dict[str, Any]:
    data = data if isinstance(data, dict) else {}

    cols = get_collections()
    db = cols["db"]
    customers_collection = cols["customers"]

    meta = data.get("meta") or {}
    fingerprint = meta.get("fingerprint")

    # ================================
    # 🔗 VISITOR LINK FIRST
    # ================================
    if fingerprint:
        try:
            visitor = await db["visitors"].find_one({"fingerprint": fingerprint})

            if visitor and visitor.get("linked_customer_id"):
                return {
                    "status": "same",
                    "reason": "visitor_link",
                    "customer_id": visitor["linked_customer_id"],
                    "confidence": 0.95,
                }
        except Exception:
            pass

    # ================================
    # EXPLICIT LINK
    # ================================
    bound_id = data.get("customer_id")
    if bound_id:
        try:
            exists = await customers_collection.find_one({"_id": bound_id})
            if exists:
                return {
                    "status": "same",
                    "reason": "explicit_link",
                    "customer_id": str(exists["_id"]),
                    "confidence": 1.0,
                }
        except Exception:
            pass

    # ================================
    # EXTRACT DATA
    # ================================
    raw_phone = data.get("phone") or meta.get("phone")
    raw_email = data.get("email") or meta.get("email")
    name = data.get("customer_name") or data.get("name")
    payment_id = data.get("payment_value")

    customer = await find_customer_graph(
        customers_collection, raw_phone, raw_email, name, payment_id
    )

    if customer:
        norm_phone = normalize_phone_advanced(raw_phone)
        norm_email = canonicalize_email(raw_email)

        matched_fields = []
        score = 0.5

        if norm_phone and customer.get("phone_normalized") == norm_phone:
            score += 0.35
            matched_fields.append("phone")

        if norm_email and customer.get("email_canonical") == norm_email:
            score += 0.25
            matched_fields.append("email")

        if payment_id and any(
            p["value"] == payment_id for p in customer.get("payment_identities", [])
        ):
            score += 0.20
            matched_fields.append("payment")

        if name and levenshtein_ratio(name, customer.get("name", "")) > 0.8:
            score += 0.10
            matched_fields.append("name_fuzzy")

        if norm_email and not customer.get("email_canonical"):
            await customers_collection.update_one(
                {"_id": customer["_id"]},
                {"$set": {"email": raw_email, "email_canonical": norm_email}},
            )

        return {
            "status": "same",
            "reason": "identity_graph_match",
            "customer_id": str(customer["_id"]),
            "confidence": min(score, 1.0),
            "matched_fields": matched_fields,
        }

    # ================================
    # CREATE NEW CUSTOMER
    # ================================
    if raw_phone or raw_email:
        new_customer = {
            "name": name,
            "phone": raw_phone,
            "phone_normalized": normalize_phone_advanced(raw_phone),
            "email": raw_email,
            "email_canonical": canonicalize_email(raw_email),
            "payment_identities": (
                [{"value": payment_id, "type": "initial"}] if payment_id else []
            ),
            "created_at": datetime.utcnow(),
            "status": "active",
            "source": "web_auto_gen",
        }

        try:
            result = await customers_collection.insert_one(new_customer)

            if fingerprint:
                try:
                    await db["visitors"].update_one(
                        {"fingerprint": fingerprint},
                        {"$set": {"linked_customer_id": str(result.inserted_id)}},
                        upsert=True,
                    )
                except Exception:
                    pass

            return {
                "status": "new",
                "reason": "profile_creation",
                "customer_id": str(result.inserted_id),
                "confidence": 0.7,
            }

        except Exception as e:
            print(f"[IDENTITY ERROR] {e}")

    return {
        "status": "pending",
        "reason": "insufficient_identifiers",
        "customer_id": None,
        "confidence": 0.0,
    }
