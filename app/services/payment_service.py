# app/services/payment_service.py

import re
from typing import Dict, Any, Optional


# =====================================
# 💰 PAYMENT DETECTION ENGINE
# =====================================


def detect_payment(text: Optional[str]) -> Dict[str, Any]:
    """
    Detect payment method from raw text.

    Supports:
    - COD (Cash on delivery)
    - CCP (Postal account)
    - BANK (RIB / IBAN)
    """

    if not text or not isinstance(text, str):
        return {"type": "COD", "value": None}

    text = text.lower().strip()

    # =====================================
    # 🔢 GENERIC NUMBER EXTRACTION
    # =====================================
    number_match = re.search(r"\b\d{8,20}\b", text)
    extracted_value = number_match.group(0) if number_match else None

    # =====================================
    # 🏦 CCP (POSTAL ACCOUNT)
    # =====================================
    if "ccp" in text or "بريدي" in text or "post" in text:
        return {
            "type": "CCP",
            "value": extracted_value,
        }

    # =====================================
    # 🏦 BANK TRANSFER
    # =====================================
    if "bank" in text or "rib" in text or "iban" in text or "virement" in text:
        return {
            "type": "BANK",
            "value": extracted_value,
        }

    # =====================================
    # 💵 CASH ON DELIVERY (DEFAULT)
    # =====================================
    return {
        "type": "COD",
        "value": None,
    }
