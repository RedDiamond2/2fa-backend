# /routes/collect.py
from flask import Blueprint, request, jsonify
import hashlib
import datetime
# استيراد المجموعة بالاسم الصحيح الموحد
from models.mongo_db import fingerprints_col

collect_api = Blueprint("collect_api", __name__)

def get_real_ip():
    """جلب IP المستخدم الحقيقي بدقة في Render/Cloudflare"""
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip: return cf_ip
    
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded: return forwarded.split(",")[0].strip()
    
    return request.remote_addr

@collect_api.route("/collect", methods=["POST", "OPTIONS"])
def collect():
    # معالجة طلبات Pre-flight الخاصة بالمتصفحات
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data"}), 400

        # التحقق من وجود الاتصال بقاعدة البيانات
        if fingerprints_col is None:
            return jsonify({"status": "error", "message": "DB Offline"}), 503

        # 1. تحديد معرف الجهاز (Device ID)
        device_id = data.get("deviceId")
        if not device_id:
            ua = data.get("basic", {}).get("ua", "")
            raw = f"{ua}|{data.get('screen', {}).get('res', '')}"
            device_id = "rd_" + hashlib.md5(raw.encode()).hexdigest()[:12]

        # 2. تجهيز سجل البيانات
        now = datetime.datetime.utcnow()
        record = {
            "device_id": device_id,
            "last_seen": now,
            "ip": get_real_ip(),
            "event": data.get("event", "sync"),
            "user": data.get("user", {}),
            "geo": data.get("geo", {}),
            "hardware": data.get("hardware", {}),
            "system": data.get("basic", {}),
            "bot_info": data.get("botDetection", {})
        }

        # 3. التحديث أو الإضافة (Upsert)
        fingerprints_col.update_one(
            {"device_id": device_id},
            {"$set": record, "$setOnInsert": {"first_seen": now}},
            upsert=True
        )

        return jsonify({"status": "success", "device_id": device_id}), 200

    except Exception as e:
        print(f"❌ Error in /collect: {str(e)}")
        return jsonify({"status": "error"}), 500