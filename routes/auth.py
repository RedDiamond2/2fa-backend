# routes/auth.py
from flask import Blueprint, request, jsonify
from services.auth_service import generate_token
from models.mongo_db import users_collection, gems_collection, transactions_collection
import datetime
import uuid

# تعريف الـ Blueprint
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/collect', methods=['POST', 'OPTIONS'])
def collect_data():
    # معالجة طلب Preflight الخاص بـ CORS
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    try:
        data = request.get_json()
        
        # 1. التأكد من وصول البيانات المطلوبة
        if not data or 'user' not in data:
            return jsonify({"success": False, "message": "Missing user data"}), 400

        user_info = data['user']
        email = user_info.get('email')
        ref_code_received = data.get('ref_code') # استلام كود الإحالة من Frontend

        if not email:
            return jsonify({"success": False, "message": "Email is required"}), 400

        # 2. تحديث أو إنشاء سجل المستخدم الرئيسي
        user_exists = users_collection.find_one({"email": email})
        
        users_collection.update_one(
            {"email": email},
            {"$set": {
                "name": user_info.get('name'),
                "photo": user_info.get('photo'),
                "phone": data.get('userPhone'),
                "last_login": datetime.datetime.utcnow(),
                "device_info": data.get('basic', {}),
                "is_active": True
            }},
            upsert=True
        )

        # 3. معالجة نظام الجواهر والإحالة للمستخدم الجديد فقط
        if not user_exists:
            # توليد كود إحالة فريد للمستخدم الجديد
            new_unic_code = str(uuid.uuid4())[:8].upper()
            
            # إنشاء سجل في مجموعة الجواهر (Gems Collection)
            gems_collection.insert_one({
                "email": email,
                "balance": 50, # هدية ترحيبية
                "referral_code": new_unic_code,
                "created_at": datetime.datetime.utcnow()
            })
            
            # تسجيل عملية الهدية الترحيبية
            transactions_collection.insert_one({
                "email": email,
                "amount": 50,
                "type": "credit",
                "reason": "Welcome Bonus 🎁",
                "timestamp": datetime.datetime.utcnow()
            })

            # 4. إذا كان المستخدم قد جاء عبر رابط إحالة (Reward the Referrer)
            if ref_code_received:
                referrer = gems_collection.find_one({"referral_code": ref_code_received})
                # نكافئ المحيل إذا وجد وكان الإيميل مختلفاً (منع الغش)
                if referrer and referrer['email'] != email:
                    gems_collection.update_one(
                        {"email": referrer['email']},
                        {"$inc": {"balance": 30}}
                    )
                    transactions_collection.insert_one({
                        "email": referrer['email'],
                        "amount": 30,
                        "type": "credit",
                        "reason": f"Referral Reward (New Friend) 💎",
                        "timestamp": datetime.datetime.utcnow()
                    })

        # 5. توليد توكن الدخول
        token = generate_token(email)

        return jsonify({
            "success": True,
            "token": token,
            "message": "Auth successful",
            "is_new_user": not user_exists
        }), 200

    except Exception as e:
        print(f"❌ Auth Error: {str(e)}")
        return jsonify({"success": False, "message": "Server Error"}), 500