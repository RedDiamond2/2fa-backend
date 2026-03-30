# routes/auth.py
from flask import Blueprint, request, jsonify
from services.auth_service import generate_token
from models.mongo_db import users_collection # تأكد من وجود هذا التعريف
import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/collect', methods=['POST'])
def collect_data():
    data = request.json
    if not data or 'user' not in data:
        return jsonify({"success": False, "message": "Missing data"}), 400

    user_info = data['user']
    email = user_info.get('email')

    if not email:
        return jsonify({"success": False, "message": "Email is required"}), 400

    # 1. تحديث أو إنشاء المستخدم في قاعدة البيانات
    users_collection.update_one(
        {"email": email},
        {"$set": {
            "name": user_info.get('name'),
            "photo": user_info.get('photo'),
            "phone": data.get('userPhone'),
            "last_login": datetime.datetime.utcnow(),
            "device_info": data.get('basic', {})
        }},
        upsert=True
    )

    # 2. توليد التوكن الاحترافي
    token = generate_token(email)

    return jsonify({
        "success": True,
        "token": token, # ✅ هذا هو التوكن الذي ينتظره الـ Frontend
        "message": "Data synchronized successfully"
    })