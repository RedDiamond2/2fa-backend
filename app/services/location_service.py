# app/services/location_service.py

import re

# =========================================
# 🧠 DB (الولايات + المناطق)
# =========================================

LOCATION_DB = {
    "الجزائر": {
        "districts": ["باب الزوار", "الحراش", "بئر خادم", "درارية", "الشراقة", "دالي ابراهيم", "رويبة", "باش جراح"],
        "areas": ["حي 5 جويلية", "حي النخيل", "حي المستقبل", "حي الامل", "حي الموز", "حي الفايز"]
    },
    "وهران": {
        "districts": ["بير الجير", "السانيا", "عين الترك", "ارزيو", "بطيوة"],
        "areas": ["حي الصباح", "حي السلام", "حي النصر", "حي الياسمين", "حي العقيد لطفي"]
    },
    "سطيف": {
        "districts": ["العلمة", "عين ارنات", "عين ازال", "بوقاعة"],
        "areas": ["حي الهضاب", "حي 1014", "حي 600 مسكن", "حي يحياوي"]
    },
    "قسنطينة": {
        "districts": ["الخروب", "عين سمارة", "حامة بوزيان", "زيغود يوسف"],
        "areas": ["حي بوالصوف", "حي الدقسي", "علي منجلي", "حي سيدي مبروك"]
    },
    "الجلفة": {
        "districts": ["عين وسارة", "حاسي بحبح", "مسعد", "الادريسية"],
        "areas": ["حي 5 جويلية", "حي بوتريفيس", "حي قناني", "حي شعباني"]
    },
    "باتنة": {
        "districts": ["بريكة", "عين التوتة", "اريس", "مروانة"],
        "areas": ["حي كشيدة", "حي بوزوران", "حي بارك فوراج", "حي الزهور"]
    },
    "الشلف": {
        "districts": ["تنس", "بوقادير", "اولاد فارس", "وادي الفضة"],
        "areas": ["حي لالة عودة", "حي الشرفة", "حي بن سونة"]
    },
    "البليدة": {
        "districts": ["بوفاريك", "الأربعاء", "موزاية", "بوعينان"],
        "areas": ["حي 444 مسكن", "حي 666 مسكن", "حي 200 مسكن", "حي 210 مسكن"]
    }
}

# =========================================
# 🧹 NORMALIZE (ULTRA CLEAN)
# =========================================

def normalize(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""

    text = text.lower().strip()

    # توحيد الحروف
    text = re.sub(r"[أإآ]", "ا", text)
    text = text.replace("ة", "ه")
    text = text.replace("ى", "ي")

    # ❌ حذف الهاتف
    text = re.sub(r"0\d{9}", " ", text)

    # ❌ حذف كلمات المنتجات
    text = re.sub(r"(تيشورت|تريكو|product|order)", " ", text)

    # ❌ حذف الرموز
    text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text)

    # تنظيف
    text = re.sub(r"\s+", " ", text)

    return text.strip()

# =========================================
# 🔍 SMART MATCH
# =========================================

def smart_match(keyword: str, text: str) -> bool:
    keyword_n = normalize(keyword)
    text_n = normalize(text)

    if not keyword_n or not text_n:
        return False

    if keyword_n in text_n:
        return True

    # fuzzy
    if len(keyword_n) > 4:
        for i in range(len(keyword_n)):
            variant = keyword_n[:i] + keyword_n[i+1:]
            if variant in text_n:
                return True

    return False

# =========================================
# 📍 INFER LOCATION (FINAL ENGINE)
# =========================================

def infer_location(text: str):
    try:
        normalized = normalize(text)

        result = {
            "province": None,
            "district": None,
            "area": None,
            "building": None,
            "door": None,
            "detail": None,
            "confidence": 0,
            "location": None
        }

        # =====================================
        # 1. Province (🔥 FIXED)
        # =====================================
        for province in LOCATION_DB.keys():
            if province in normalized:
                result["province"] = province
                break

        # =====================================
        # 2. Scope
        # =====================================
        search_scope = [result["province"]] if result["province"] else list(LOCATION_DB.keys())

        # =====================================
        # 3. District
        # =====================================
        for prov in search_scope:
            for district in LOCATION_DB[prov]["districts"]:
                if smart_match(district, normalized):
                    result["district"] = district
                    result["province"] = prov
                    break
            if result["district"]:
                break

        # =====================================
        # 4. Area
        # =====================================
        for prov in search_scope:
            for area in LOCATION_DB[prov]["areas"]:
                if smart_match(area, normalized):
                    result["area"] = area
                    if not result["province"]:
                        result["province"] = prov
                    break
            if result["area"]:
                break

        # =====================================
        # 5. Generic Area (SAFE)
        # =====================================
        if not result["area"]:
            generic_area = re.search(r"(حي\s*\d+\s*مسكن)", normalized)
            if generic_area:
                result["area"] = generic_area.group(1)

        # =====================================
        # 6. Building / Door
        # =====================================
        building_match = re.search(r"(?:بناية|عمارة|batiment|bâtiment)\s*(\d+)", normalized)
        if building_match:
            result["building"] = building_match.group(1)

        door_match = re.search(r"(?:باب|رقم باب|شقة|appt)\s*(\d+)", normalized)
        if door_match:
            result["door"] = door_match.group(1)

        # =====================================
        # 7. Detail (🔥 FIXED FULL ADDRESS)
        # =====================================
        parts = []

        if result["province"]:
            parts.append(result["province"])

        if result["district"]:
            parts.append(result["district"])

        if result["area"]:
            parts.append(result["area"])

        if result["building"]:
            parts.append(f"عمارة {result['building']}")

        if result["door"]:
            parts.append(f"باب {result['door']}")

        result["detail"] = " - ".join(parts) if parts else None

        # =====================================
        # 8. Confidence
        # =====================================
        confidence = 0

        if result["province"]:
            confidence += 0.4

        if result["district"]:
            confidence += 0.3

        if result["area"]:
            confidence += 0.2

        if result["building"] or result["door"]:
            confidence += 0.1

        result["confidence"] = round(confidence, 2)

        # =====================================
        # 9. Clean Location
        # =====================================
        if result["area"]:
            result["location"] = result["area"]
        elif result["district"]:
            result["location"] = result["district"]
        elif result["province"]:
            result["location"] = result["province"]

        # =====================================
        # 10. FINAL SAFETY
        # =====================================
        if result["location"] and (
            len(result["location"]) > 40 or "\n" in result["location"]
        ):
            result["location"] = None

        # =====================================
        # 11. FALLBACK
        # =====================================
        if not any([result["province"], result["district"], result["area"]]):
            result["confidence"] = 0.1

        return result

    except Exception as e:
        import traceback
        print("❌ LOCATION ERROR:")
        traceback.print_exc()

        return {
            "province": None,
            "district": None,
            "area": None,
            "building": None,
            "door": None,
            "detail": text[:80] if text else None,
            "confidence": 0,
            "location": None
        }