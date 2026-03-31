# /routes/collect.py
from flask import Blueprint, request, jsonify
import hashlib
import datetime
import os
from pymongo import MongoClient

# تعريف الـ Blueprint للمسار /collect
collect_api = Blueprint("collect_api", __name__)

# الاتصال بقاعدة البيانات (يفضل مستقبلاً جلب 'db' من models/mongo_db.py)
MONGO_URI = os.environ.get("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client.get_database()
fingerprints_col = db.fingerprints

def get_real_ip():
    """جلب IP المستخدم الحقيقي بدقة في بيئة Render/Cloudflare"""
    if request.headers.get("CF-Connecting-IP"):
        return request.headers.get("CF-Connecting-IP")
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr

@collect_api.route("/collect", methods=["POST"])
def collect():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        # 1. إنشاء معرف فريد للجهاز (Fingerprint Hash)
        # نعتمد على UA ودقة الشاشة والمعالج كمعايير ثابتة
        ua = data.get("basic", {}).get("ua", "")
        screen_res = data.get("screen", {}).get("res", "")
        cores = data.get("hardware", {}).get("cores", "")
        
        raw_id = f"{ua}|{screen_res}|{cores}"
        device_hash = hashlib.sha256(raw_id.encode()).hexdigest()[:20]

        # 2. تجهيز سجل البيانات للإنتاج
        record = {
            "device_id": device_hash,
            "timestamp": datetime.datetime.utcnow(),
            "ip": get_real_ip(),
            "event": data.get("event", "page_view"),
            "user_info": {
                "email": data.get("user", {}).get("email"),
                "phone": data.get("user", {}).get("phone"),
                "name": data.get("user", {}).get("name")
            },
            "full_details": data,
            "geo_snapshot": data.get("geo", {})
        }

        # 3. حفظ أو تحديث البيانات (Upsert)
        # إذا كان الجهاز معروفاً، نقوم بتحديث آخر ظهور له وبياناته
        fingerprints_col.update_one(
            {"device_id": device_hash},
            {"$set": record, "$setOnInsert": {"first_seen": datetime.datetime.utcnow()}},
            upsert=True
        )

        return jsonify({
            "status": "ok", 
            "device_id": device_hash,
            "server_time": datetime.datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        # تسجيل الخطأ في السيرفر دون إظهار تفاصيل تقنية للمستخدم (أمان)
        print(f"❌ Collection Error: {str(e)}")
        return jsonify({"status": "error", "message": "Internal processing error"}), 500