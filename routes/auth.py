# routes/auth.py
from flask import Blueprint, request, jsonify
from services.auth_service import generate_token
from models.mongo_db import users_collection
import datetime

# تعريف الـ Blueprint
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/collect', methods=['POST', 'OPTIONS'])
def collect_data():
    # معالجة طلب Preflight الخاص بـ CORS
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    try:
        data = request.get_json()
        
        # التأكد من وصول البيانات المطلوبة
        if not data or 'user' not in data:
            return jsonify({"success": False, "message": "Missing user data"}), 400

        user_info = data['user']
        email = user_info.get('email')

        if not email:
            return jsonify({"success": False, "message": "Email is required"}), 400

        # 1. تحديث أو إنشاء المستخدم في قاعدة البيانات (Atomic Update)
        # نستخدم upsert=True لإنشاء السجل إذا لم يكن موجوداً
        users_collection.update_one(
            {"email": email},
            {"$set": {
                "name": user_info.get('name'),
                "photo": user_info.get('photo'),
                "phone": data.get('userPhone'),
                "last_login": datetime.datetime.utcnow(),
                "device_info": data.get('basic', {}),
                "location": data.get('location', {}), # إضافة الموقع إذا توفر
                "is_active": True
            }},
            upsert=True
        )

        # 2. توليد التوكن الاحترافي باستخدام الخدمة التي صممناها
        token = generate_token(email)

        if not token:
            return jsonify({"success": False, "message": "Failed to generate token"}), 500

        # 3. الرد على الـ Frontend بالتوكن والنجاح
        return jsonify({
            "success": True,
            "token": token,
            "message": "Session established successfully",
            "server_time": datetime.datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        print(f"❌ Auth Error: {str(e)}")
        return jsonify({"success": False, "message": "Internal Server Error"}), 500