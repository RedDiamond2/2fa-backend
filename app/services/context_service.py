# app/services/context_service.py

from typing import List, Dict, Any
from datetime import datetime
from app.core.database import conversations_collection

# =====================================
# ⚙️ CONFIG (Elite Production)
# =====================================
MAX_HISTORY = 20          # أقصى عدد رسائل يتم تخزينها في قاعدة البيانات
CONTEXT_WINDOW = 10       # عدد الرسائل المستخدمة لبناء السياق الذكي
MAX_STACK = 5             # أقصى حد لمنتجات الـ Stack لمنع تضخم السياق

# =====================================
# 📥 GET HISTORY (Normalized)
# =====================================
def get_conversation_history(conversation_id: str) -> List[str]:
    """تسترجع التاريخ وتنظفه ليعود دائماً كقائمة نصوص لضمان التوافق."""
    if not conversation_id:
        return []

    convo = conversations_collection.find_one({"id": conversation_id})
    if not convo:
        return []

    messages = convo.get("messages", [])[-MAX_HISTORY:]

    cleaned = []
    for msg in messages:
        if isinstance(msg, dict):
            cleaned.append(msg.get("text", ""))
        else:
            cleaned.append(msg)
    return cleaned


# =====================================
# 💾 SAVE HISTORY (Structured JSON)
# =====================================
def save_conversation(conversation_id: str, messages: List[Any]):
    """تحفظ المحادثة مع هيكلة JSON غنية للحفاظ على التوقيت ونوع الرسالة."""
    if not conversation_id:
        return

    normalized = []
    for msg in messages:
        if isinstance(msg, str):
            normalized.append({
                "text": msg,
                "timestamp": datetime.utcnow(),
                "type": "user"
            })
        else:
            normalized.append(msg)

    trimmed = normalized[-MAX_HISTORY:]

    conversations_collection.update_one(
        {"id": conversation_id},
        {
            "$set": {
                "messages": trimmed,
                "updated_at": datetime.utcnow()
            },
            "$setOnInsert": {
                "created_at": datetime.utcnow()
            }
        },
        upsert=True
    )


# =====================================
# 🧠 EXTRACT LAST KNOWN INFO (Identity & Cities)
# =====================================
def extract_last_known_info(history: List[str]) -> Dict:
    """استخراج المعلومات الأساسية مع كشف المدن الجزائرية وتوليد Identity Hint."""
    last_name = None
    last_location = None
    last_phone = None

    # المدن والكلمات الدلالية للمواقع
    location_keywords = ["حي", "بلدية", "دار", "باب", "طريق", "وهران", "الجزائر", "سطيف", "عنابة", "قسنطينة"]

    for msg in reversed(history):
        msg_clean = msg.strip()

        # 📞 كشف الهاتف (Normalizing DZ numbers)
        if not last_phone:
            digits = "".join(filter(str.isdigit, msg_clean))
            if len(digits) >= 8:
                if digits.startswith("213"):
                    digits = "0" + digits[3:]
                last_phone = digits

        # 📍 كشف الموقع
        if not last_location:
            if any(w in msg_clean for w in location_keywords):
                last_location = msg_clean

        # 👤 كشف الاسم (مع فلاتر الجودة)
        if not last_name:
            words = msg_clean.split()
            if (1 <= len(words) <= 3 
                and not any(char.isdigit() for char in msg_clean)
                and len(msg_clean) > 2):
                last_name = msg_clean

        if last_name and last_location and last_phone:
            break

    # توليد معرف الهوية الفريد للربط بين الجلسات
    identity = None
    if last_phone:
        identity = f"user_{last_phone}"
    elif last_name:
        identity = f"user_{last_name}"

    return {
        "name_hint": last_name,
        "location_hint": last_location,
        "phone_hint": last_phone,
        "identity_hint": identity
    }


# =====================================
# 🧠 BUILD SMART CONTEXT (Elite Version)
# =====================================
def build_context(messages: List[str]) -> str:
    """
    محرك السياق الذكي:
    - يدعم Multi-product stack مع حماية Memory Leak.
    - يزن الرسائل (Weighting) حسب الحداثة.
    - يحقن إشارات الثقة (Confidence) للـ AI.
    - يصفي الضجيج (Noise Filter).
    """
    if not messages:
        return ""

    recent_messages = messages[-CONTEXT_WINDOW:]
    total = len(recent_messages)
    
    context_parts = []
    last_product = None
    product_stack = []  # تتبع تسلسل المنتجات
    seen = set()        # منع التكرار (Anti-Spam)

    for i, msg in enumerate(recent_messages):
        msg = clean_message(msg)

        # 🚫 Context Noise Filter (تجاهل الرسائل غير المفيدة)
        if not msg or msg.lower() in ["ok", "okay", "merci", "شكرا", "تمام", "done", "ماشي"]:
            continue

        if msg in seen:
            continue
        
        seen.add(msg)
        
        # حساب الوزن (الرسالة الأحدث = وزن 1.0)
        weight = round((i + 1) / total, 2) if total > 0 else 1.0

        # 🛒 PRODUCT: Smart Dedup & Memory Protection
        if is_product(msg):
            last_product = msg
            if msg not in product_stack:
                product_stack.append(msg)
            
            # حماية من تضخم الـ Stack (Memory Leak Fix)
            if len(product_stack) > MAX_STACK:
                product_stack.pop(0)
                
            context_parts.append(f"[PRODUCT|w={weight}|c=high] {msg}")
            continue

        # تحديد المنتج المستهدف (Target) بناءً على الـ Stack
        target = last_product or (product_stack[-1] if product_stack else None)

        # 🔢 QUANTITY
        if is_quantity(msg) and target:
            context_parts.append(f"[QTY→{target}|w={weight}|c=high] {msg}")
            continue

        # ➕ CONTINUATION / UPDATE
        if is_continuation(msg) and target:
            context_parts.append(f"[UPDATE→{target}|w={weight}|c=high] {msg}")
            continue

        # 📍 LOCATION (Medium Confidence)
        if any(w in msg for w in ["حي", "بلدية", "دار", "باب", "وهران", "سطيف", "الجزائر"]):
            context_parts.append(f"[LOCATION|w={weight}|c=medium] {msg}")
            continue

        # 📞 PHONE (Normalization & High Confidence)
        digits = "".join(filter(str.isdigit, msg))
        if len(digits) >= 8:
            if digits.startswith("213"):
                digits = "0" + digits[3:]
            context_parts.append(f"[PHONE|w={weight}|c=high] {digits}")
            continue

        # DEFAULT (Low Confidence)
        context_parts.append(f"[{weight}|c=low] {msg}")

    return " || ".join(context_parts)


# =====================================
# 🧹 UTILS & DETECTORS
# =====================================
def clean_message(msg: str) -> str:
    """تنظيف عميق للنص من المسافات المتعددة والرموز."""
    msg = msg.strip().replace("\n", " ").replace("\t", " ")
    while "  " in msg:
        msg = msg.replace("  ", " ")
    return msg


def is_product(msg: str) -> bool:
    """الكلمات المفتاحية للمنتجات."""
    keywords = ["تريكو", "تيش", "سروال", "صباط", "حذاء", "قميص", "فستان", "جلباب", "خمار", "عباءة"]
    return any(k in msg for k in keywords)


def is_quantity(msg: str) -> bool:
    """كشف الكميات (أرقام أو كلمات)."""
    has_digit = any(char.isdigit() for char in msg)
    qty_words = ["زوج", "ثلاثة", "اربعة", "خمسة", "حبة", "قطعة", "كونتيتي", "عدد"]
    return has_digit or any(k in msg for k in qty_words)


def is_continuation(msg: str) -> bool:
    """كشف الرغبة في الإضافة لآخر منتج."""
    keywords = ["زيد", "اضف", "حتى", "زيدلي", "كمان", "ايضا"]
    return any(k in msg for k in keywords)