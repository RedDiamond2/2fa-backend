# routes/auth.py
from flask import Blueprint, request, jsonify
from services.auth_service import generate_token
from models.mongo_db import users_col, gems_col, transactions_col
import datetime
import uuid

auth_bp = Blueprint('auth', __name__)

def setup_user_session(email, user_info, extra_data):
    """وظيفة مشتركة لإنشاء أو تحديث بيانات المستخدم ومنحه الجواهر"""
    # 1. تحديث بيانات المستخدم الأساسية
    users_col.update_one(
        {"email": email},
        {"$set": {
            "name": user_info.get('name') or email.split('@')[0],
            "photo": user_info.get('photo') or "./icons/user-286.svg",
            "phone": extra_data.get('userPhone'),
            "last_login": datetime.datetime.utcnow(),
            "device_info": extra_data.get('basic', {}),
            "is_active": True
        }},
        upsert=True
    )

    # 2. التحقق من وجود حساب جواهر (منح 50 جوهرة للمستخدم الجديد)
    if not gems_col.find_one({"email": email}):
        gems_col.insert_one({
            "email": email,
            "balance": 50,
            "referral_code": str(uuid.uuid4())[:8].upper(),
            "created_at": datetime.datetime.utcnow()
        })
        transactions_col.insert_one({
            "email": email,
            "amount": 50,
            "type": "credit",
            "reason": "Welcome Bonus 🎁",
            "timestamp": datetime.datetime.utcnow()
        })

    # 3. توليد التوكن
    return generate_token(email)

@auth_bp.route('/collect', methods=['POST', 'OPTIONS'])
def collect_data():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
    try:
        data = request.get_json()
        if not data or 'user' not in data:
            return jsonify({"success": False, "message": "Missing data"}), 400
        
        email = data['user'].get('email')
        token = setup_user_session(email, data['user'], data)
        
        return jsonify({"success": True, "token": token, "message": "Logged in"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500