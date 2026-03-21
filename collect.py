from flask import Blueprint, request, jsonify
import hashlib
import json
import datetime
import os

collect_api = Blueprint("collect_api", __name__)

DATA_FOLDER = "fingerprints"

# إنشاء المجلد إذا لم يكن موجود
os.makedirs(DATA_FOLDER, exist_ok=True)


@collect_api.route("/collect", methods=["POST"])
def collect():

    try:

        data = request.json

        if not data:
            return jsonify({"status":"error","message":"no data"}),400

        # تحويل البيانات لنص
        data_string = json.dumps(data, sort_keys=True)

        # إنشاء fingerprint hash
        fingerprint_hash = hashlib.sha256(data_string.encode()).hexdigest()[:16]

        # التاريخ والوقت
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")

        # اسم الملف
        filename = f"{timestamp}_{fingerprint_hash}.json"

        filepath = os.path.join(DATA_FOLDER, filename)

        # حفظ البيانات
        with open(filepath,"w",encoding="utf-8") as f:
            json.dump(data,f,indent=2)

        return jsonify({
            "status":"ok",
            "fingerprint":fingerprint_hash
        })

    except Exception as e:

        return jsonify({
            "status":"error",
            "message":str(e)
        }),500
