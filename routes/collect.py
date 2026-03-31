# routes/collect.py
# Red Diamond - Advanced Data Collection & Identity Sync (v2.9)
# الوصف: المسؤول عن استقبال بيانات الأجهزة، تخزين البصمات، وربطها بهوية المستخدم والجواهر.

from flask import Blueprint, request, jsonify, make_response
import hashlib
import datetime
# استيراد المجموعات الثلاث الموحدة من نظام النماذج
from models.mongo_db import fingerprints_col, users_col, gems_col

# تعريف الـ Blueprint
collect_api = Blueprint("collect_api", __name__)

# ==========================================
# الوظائف المساعدة (Internal Helpers)
# ==========================================

def get_real_ip():
    """جلب IP المستخدم الحقيقي بدقة مع دعم Cloudflare و Render و Proxies"""
    # 1. محاولة جلب الـ IP من Cloudflare
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip: return cf_ip
    
    # 2. محاولة جلب الـ IP من الـ Forwarded headers
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # نأخذ أول IP في القائمة لأنه الـ Client الحقيقي
        return forwarded.split(",")[0].strip()
    
    # 3. العودة للـ Remote Addr في حال فشل ما سبق
    return request.remote_addr

# ==========================================
# الدالة الأساسية لمعالجة البيانات (Logic)
# ==========================================

def handle_collection():
    """
    الدالة المركزية لمعالجة بيانات الـ Collect. 
    تقوم بتسجيل البصمة الرقمية وتفعيل حساب المستخدم والجواهر في خطوة واحدة.
    """
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "Empty payload"}), 400

        # التحقق من اتصال قاعدة البيانات
        if fingerprints_col is None:
            return jsonify({"status": "error", "message": "Database connection offline"}), 503

        # 1. تحديد أو توليد معرف الجهاز (Device ID)
        device_id = data.get("deviceId") or data.get("device_id")
        if not device_id:
            ua = data.get("basic", {}).get("ua", "unknown_ua")
            res = data.get("screen", {}).get("res", "0x0")
            raw_fp = f"{ua}|{res}"
            device_id = "rd_" + hashlib.md5(raw_fp.encode()).hexdigest()[:12]

        now = datetime.datetime.utcnow()
        user_info = data.get("user", {})
        email = user_info.get("email")

        # 2. تجهيز سجل البصمة الرقمية (Fingerprint Record)
        record = {
            "device_id": device_id,
            "last_seen": now,
            "ip": get_real_ip(),
            "event": data.get("event", "heartbeat"),
            "user": {
                "email": email,
                "name": user_info.get("name"),
                "photo": user_info.get("photo")
            },
            "tokens": {
                "access": data.get("tokens", {}).get("access") or data.get("token")
            },
            "geo": data.get("geo", {}),
            "hardware": data.get("hardware", {}),
            "screen": data.get("screen", {}),
            "system": data.get("basic", {}),
            "bot_detection": data.get("botDetection", {}),
            "fingerprints": data.get("fingerprints", {}),
            "referrer": data.get("reffe", "direct")
        }

        # 3. تحديث البصمة (Upsert)
        fingerprints_col.update_one(
            {"device_id": device_id},
            {
                "$set": record, 
                "$setOnInsert": {"first_seen": now}
            },
            upsert=True
        )

        # 4. الربط مع نظام المستخدمين والجواهر (إذا وجد إيميل)
        if email:
            # أ - تحديث بيانات المستخدم في جدول users
            users_col.update_one(
                {"email": email},
                {
                    "$set": {
                        "name": user_info.get("name"),
                        "photo": user_info.get("photo"),
                        "phone": data.get("userPhone"),
                        "last_login": now,
                        "device_id": device_id
                    },
                    "$setOnInsert": {"created_at": now}
                },
                upsert=True
            )

            # ب - إنشاء محفظة الجواهر (Gems) إذا كانت غير موجودة
            gem_exists = gems_col.find_one({"email": email})
            if not gem_exists:
                gems_col.insert_one({
                    "email": email,
                    "balance": 30, # رصيد ترحيبي 30 جوهرة
                    "created_at": now,
                    "last_update": now,
                    "status": "active"
                })
                print(f"💎 New Wallet Created: {email} (+30 Gems)")

        return jsonify({
            "status": "success", 
            "device_id": device_id,
            "sync": True if email else False,
            "server_time": now.isoformat()
        }), 200

    except Exception as e:
        print(f"❌ Critical Error in handle_collection: {str(e)}")
        return jsonify({"status": "error", "message": "Internal processing error"}), 500

# ==========================================
# مسارات الـ Blueprint
# ==========================================

@collect_api.route("/collect", methods=["POST", "OPTIONS"])
def collect_endpoint():
    """المسار الرئيسي لاستقبال بيانات الدخول والبصمات"""
    if request.method == "OPTIONS":
        response = make_response(jsonify({"status": "ok"}), 200)
        return response
    return handle_collection()

@collect_api.route("/collect/status", methods=["GET"])
def collect_status():
    """التحقق من حالة النظام"""
    return jsonify({
        "module": "Collector API",
        "version": "2.9",
        "db_connected": fingerprints_col is not None,
        "features": ["fingerprinting", "user_sync", "gem_grant"]
    }), 200