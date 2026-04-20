# app/services/payment_service.py
import re

def detect_payment(text: str):
    if not text:
        return {"type": "COD", "value": None}

    text = text.lower()

    # CCP
    ccp_match = re.search(r'\b\d{8,20}\b', text)
    if "ccp" in text or "بريدي" in text:
        return {
            "type": "CCP",
            "value": ccp_match.group(0) if ccp_match else None
        }

    # Bank
    if "bank" in text or "rib" in text or "iban" in text:
        return {
            "type": "BANK",
            "value": ccp_match.group(0) if ccp_match else None
        }

    return {"type": "COD", "value": None}