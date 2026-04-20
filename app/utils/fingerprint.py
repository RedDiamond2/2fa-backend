# app/utils/fingerprint.py

import hashlib
from typing import Optional, Dict, Any


# =========================================
# 🟢 NORMALIZATION LAYER
# =========================================

def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Normalize Algerian phone numbers:
    - remove spaces / symbols
    - convert 213XXXXXXXXX → 0XXXXXXXXX
    """

    if not phone:
        return None

    phone = str(phone).strip()

    # keep only digits
    phone = "".join(filter(str.isdigit, phone))

    # Algeria international format
    if phone.startswith("213") and len(phone) == 12:
        phone = "0" + phone[3:]

    # valid Algerian phone = 10 digits
    if len(phone) != 10:
        return None

    return phone


def normalize_name(name: Optional[str]) -> Optional[str]:
    """
    Normalize customer name:
    - lowercase
    - remove noise
    """

    if not name:
        return None

    name = str(name).strip().lower()

    # remove invalid names
    if name in ["unknown", "???", "⚠️"]:
        return None

    if len(name) < 3:
        return None

    return name


def normalize_location(location: Any) -> Optional[str]:
    """
    Normalize location:
    - prefer province
    """

    if not location:
        return None

    if isinstance(location, dict):
        province = location.get("province")
        if province:
            return province.strip().lower()

    if isinstance(location, str):
        return location.strip().lower()

    return None


# =========================================
# 🟢 CORE FINGERPRINT LOGIC
# =========================================

def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def generate_fingerprint(
    phone: Optional[str],
    name: Optional[str],
    location: Optional[str]
) -> str:
    """
    Strong fingerprint strategy:

    Priority:
    1. phone → strongest identity
    2. phone + name
    3. name + location
    4. fallback (weak identity)
    """

    # =========================
    # 🥇 STRONG: PHONE ONLY
    # =========================
    if phone:
        return _hash(f"phone:{phone}")

    # =========================
    # 🥈 MEDIUM: NAME + LOCATION
    # =========================
    if name and location:
        return _hash(f"name_loc:{name}|{location}")

    # =========================
    # 🥉 WEAK: NAME ONLY
    # =========================
    if name:
        return _hash(f"name:{name}")

    # =========================
    # ⚠️ FALLBACK
    # =========================
    return _hash("anonymous")


# =========================================
# 🟢 PARSED WRAPPER (MAIN ENTRY)
# =========================================

def fingerprint_from_parsed(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract + normalize + fingerprint

    Returns:
    {
        fingerprint,
        phone,
        name,
        location,
        strength
    }
    """

    raw_phone = parsed.get("phone")
    raw_name = parsed.get("name")
    raw_location = parsed.get("location")

    phone = normalize_phone(raw_phone)
    name = normalize_name(raw_name)
    location = normalize_location(raw_location)

    fingerprint = generate_fingerprint(phone, name, location)

    # =========================
    # 🟢 STRENGTH SCORING
    # =========================
    if phone:
        strength = "strong"
    elif name and location:
        strength = "medium"
    elif name:
        strength = "weak"
    else:
        strength = "anonymous"

    return {
        "fingerprint": fingerprint,
        "phone": phone,
        "name": name,
        "location": location,
        "strength": strength
    }


# =========================================
# 🟢 MATCHING (IMPORTANT FOR FUTURE)
# =========================================

def is_same_customer(fp1: str, fp2: str) -> bool:
    """
    Simple comparison (future: fuzzy matching)
    """
    return fp1 == fp2


# =========================================
# 🟢 DEBUG / TRACE (PRODUCTION READY)
# =========================================

def fingerprint_debug(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """
    Useful for logs / debugging in production
    """

    data = fingerprint_from_parsed(parsed)

    return {
        "raw": {
            "phone": parsed.get("phone"),
            "name": parsed.get("name"),
            "location": parsed.get("location"),
        },
        "normalized": {
            "phone": data["phone"],
            "name": data["name"],
            "location": data["location"],
        },
        "fingerprint": data["fingerprint"],
        "strength": data["strength"]
    }