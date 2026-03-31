# routes/auth.py
# Red Diamond Project - Production Version 2026
# الوصف: إدارة عمليات الدخول، تسجيل المستخدمين الجدد، وجمع بصمة الجهاز.

import datetime
import uuid
from flask import Blueprint, request, jsonify
from models.mongo_db import users_col, gems_col, transactions_col, fingerprints_col
from services.auth_service import generate_token

# تعريف الـ Blueprint
auth_bp = Blueprint('auth', __name__)

def setup_user_session(email, user_info, extra_data):
    """
    وظيفة مركزية لإنشاء أو تحديث بيانات المستخدم ومنحه مكافأة الترحيب.
    يتم استدعاؤها عند تسجيل الدخول الناجح.
    """
    try:
        # 1. تحديث أو إنشاء بيانات المستخدم الأساسية (Upsert)
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

        # 2. إدارة محفظة الجواهر (نستخدم balance للتوحيد)
        user_wallet = gems_col.find_one({"email": email})
        
        if not user_wallet:
            # توليد كود إحالة فريد للمستخدم الجديد
            new_ref_code = str(uuid.uuid4())[:8].upper()
            
            # إنشاء المحفظة مع مكافأة الترحيب (50 جوهرة)
            gems_col.insert_one({
                "email": email,
                "balance": 50,  # الرصيد الابتدائي
                "referral_code": new_ref_code,
                "created_at": datetime.datetime.utcnow()
            })

            # تسجيل عملية الإيداع في سجل الترانزكشنز للشفافية
            transactions_col.insert_one({
                "email": email,
                "amount": 50,
                "type": "credit",
                "reason": "Welcome Bonus 🎁",
                "timestamp": datetime.datetime.utcnow()
            })
            print(f"✅ New user wallet created for: {email}")

        # 3. توليد توكن JWT آمن للجلسة
        token = generate_token(email)
        return token

    except Exception as e:
        print(f"❌ Error in setup_user_session: {str(e)}")
        return None

@auth_bp.route('/collect', methods=['POST', 'OPTIONS'])
def handle_collection():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    try:
        data = request.get_json()
        
        # 1. التحقق من البيانات الأساسية للمستخدم (إلزامي للدخول)
        if not data or 'user' not in data:
            return jsonify({"success": False, "message": "بيانات المستخدم مفقودة"}), 400

        user_email = data['user'].get('email')
        if not user_email:
            return jsonify({"success": False, "message": "البريد الإلكتروني مطلوب"}), 400

        # 2. إنشاء الجلسة ومنح مكافأة الترحيب (هذا الجزء يعمل دائماً)
        token = setup_user_session(user_email, data['user'], data)
        
        if not token:
            return jsonify({"success": False, "message": "فشل في إعداد الجلسة"}), 500

        # 3. معالجة بصمة الجهاز (اختياري - Optional)
        # إذا فشل info.js في جمع البيانات، لن يتوقف السيرفر
        device_id = data.get('fingerprint')
        if device_id:
            try:
                fingerprints_col.update_one(
                    {"device_id": device_id},
                    {"$set": {
                        "owner_email": user_email,
                        "full_specs": data.get('basic', {}),
                        "geo": data.get('geo', {}), # قد تكون فارغة بسبب الـ VPN
                        "updated_at": datetime.datetime.utcnow()
                    }},
                    upsert=True
                )
                print(f"✅ Device Fingerprint linked for: {user_email}")
            except Exception as e:
                # نسجل الخطأ في السيرفر لكن لا نخبر المستخدم لكي لا ينزعج
                print(f"⚠️ Fingerprint storage failed (Ignored): {e}")

        # 4. الرد بالنجاح حتى لو لم تتوفر البصمة
        return jsonify({
            "success": True,
            "message": "تم الدخول بنجاح",
            "token": token,
            "fingerprint_status": "captured" if device_id else "skipped"
        }), 200

    except Exception as e:
        print(f"❌ Critical Error in /collect: {str(e)}")
        return jsonify({"success": False, "message": "حدث خطأ داخلي"}), 500

@auth_bp.route('/verify-status', methods=['GET'])
def verify_auth_status():
    """مسار سريع للتحقق من أن السيرفر يستجيب لطلبات التحقق"""
    return jsonify({"status": "ready", "timestamp": datetime.datetime.utcnow()}), 200