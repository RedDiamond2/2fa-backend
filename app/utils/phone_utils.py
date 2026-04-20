# app/utils/phone_utils.py

import re
from typing import Optional


# ================================
# 📞 Phone Normalization Engine
# ================================

def clean_phone(phone: str) -> Optional[str]:
    """
    🔥 تنظيف رقم الهاتف وتحويله إلى صيغة موحدة

    أمثلة:
    0777 88 99 99 → 0777889999
    +213777889999 → 0777889999
    213777889999 → 0777889999
    """

    if not phone:
        return None

    # إزالة كل شيء غير أرقام
    digits = re.sub(r"\D", "", str(phone))

    # 🇩🇿 تحويل الدولي إلى محلي
    if digits.startswith("213"):
        digits = "0" + digits[3:]

    # إزالة 00213
    if digits.startswith("00213"):
        digits = "0" + digits[5:]

    # تأكد من الطول الصحيح
    if len(digits) == 9:
        digits = "0" + digits

    # تحقق نهائي
    if not is_valid_phone(digits):
        return None

    return digits


# ================================
# ✅ Validation
# ================================

def is_valid_phone(phone: str) -> bool:
    """
    التحقق من أن الرقم جزائري صحيح
    """

    if not phone:
        return False

    # يجب أن يبدأ بـ 0 ويكون 10 أرقام
    if not re.match(r"^0\d{9}$", phone):
        return False

    # شركات الاتصالات الجزائرية
    valid_prefixes = ["05", "06", "07"]

    return any(phone.startswith(p) for p in valid_prefixes)


# ================================
# 🔍 Extraction
# ================================

def extract_phone(text: str) -> Optional[str]:
    """
    استخراج أول رقم هاتف صالح من النص
    """

    if not text:
        return None

    # استخراج كل sequences أرقام طويلة
    candidates = re.findall(r"\+?\d{9,15}", text)

    for c in candidates:
        cleaned = clean_phone(c)
        if cleaned:
            return cleaned

    return None


# ================================
# 🧠 Smart Detection
# ================================

def detect_phone_candidates(text: str):
    """
    إرجاع كل الأرقام المحتملة (لـ debug أو advanced usage)
    """
    if not text:
        return []

    return re.findall(r"\+?\d{8,15}", text)


# ================================
# 🧪 Debug Helper
# ================================

def debug_phone(text: str):
    """
    طباعة تحليل الهاتف (للتصحيح)
    """
    print("\n📞 PHONE DEBUG")
    print("RAW:", text)

    candidates = detect_phone_candidates(text)
    print("CANDIDATES:", candidates)

    for c in candidates:
        print(f"→ {c} → {clean_phone(c)}")