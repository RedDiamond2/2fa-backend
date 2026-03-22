#https://github.com/RedDiamond2/2fa-backend/edit/main/collect.py
from flask import Blueprint, request, jsonify
import hashlib
import datetime
import os
from pymongo import MongoClient

collect_api = Blueprint("collect_api", __name__)

# MongoDB Atlas connection
MONGO_URI = os.environ.get("MONGO_URI")  # ضع رابط MongoDB هنا كـ env variable
client = MongoClient(MONGO_URI)
db = client.red_diamond
collection = db.f

@collect_api.route("/collect", methods=["POST"])
def collect():
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No data"}), 400

    # إنشاء fingerprint hash ثابت لكل مجموعة البيانات
    data_string = str(sorted(data.items()))
    fingerprint_hash = hashlib.sha256(data_string.encode()).hexdigest()[:16]

    # التاريخ والوقت
    timestamp = datetime.datetime.utcnow()

    # تجميع السجل
    record = {
        "timestamp": timestamp,
        "fingerprint": fingerprint_hash,
        "data": data
    }

    # حفظ في MongoDB
    collection.insert_one(record)

    return jsonify({"status": "ok", "fingerprint": fingerprint_hash})
