# routes/user.py
from flask import Blueprint, request, jsonify
import datetime
from models.mongo_db import users_collection, fingerprints_collection
from middleware.auth_guard import token_required

# تعريف الـ Blueprint
user_bp = Blueprint('user', __name__)

# ==========================================
# 1. جلب بيانات الملف الشخصي (Get Profile)
# ==========================================
@user_bp.route('/profile', methods=['GET'])
@token_required
def get_profile(user_email):
    """جلب بيانات المستخدم الأساسية وتاريخ انضمامه"""
    try:
        user_data = users_collection.find_one(
            {"email": user_email}, 
            {"_id": 0, "password": 0}  # حجب الـ ID وكلمة المرور للأمان
        )
        
        if not user_data:
            return jsonify({"success": False, "message": "User not found"}), 404

        return jsonify({
            "success": True,
            "data": user_data
        }), 200

    except Exception as e:
        print(f"❌ Get Profile Error: {str(e)}")
        return jsonify({"success": False, "message": "Error fetching profile"}), 500

# ==========================================
# 2. تحديث بيانات الملف الشخصي (Update Profile)
# ==========================================
@user_bp.route('/update', methods=['POST'])
@token_required
def update_profile(user_email):
    """تحديث الاسم، الهاتف، أو أي بيانات إضافية"""
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "message": "No data provided"}), 400

        # الحقول المسموح بتحديثها فقط (للأمان)
        allowed_updates = ["name", "phone", "country", "language", "bio"]
        update_query = {}
        
        for field in allowed_updates:
            if field in data:
                update_query[field] = data[field]

        if not update_query:
            return jsonify({"success": False, "message": "No valid fields to update"}), 400

        # إضافة تاريخ التحديث
        update_query["updated_at"] = datetime.datetime.utcnow()

        # تنفيذ التحديث في MongoDB
        result = users_collection.update_one(
            {"email": user_email},
            {"$set": update_query}
        )

        if result.matched_count == 0:
            return jsonify({"success": False, "message": "User not found"}), 404

        return jsonify({
            "success": True, 
            "message": "Profile updated successfully",
            "updated_fields": list(update_query.keys())
        }), 200

    except Exception as e:
        print(f"❌ Update Profile Error: {str(e)}")
        return jsonify({"success": False, "message": "Update failed"}), 500

# ==========================================
# 3. ربط الجهاز بالحساب (Device Linkage)
# ==========================================
@user_bp.route('/link-device', methods=['POST'])
@token_required
def link_device_to_user(user_email):
    """ربط بصمة الجهاز (Fingerprint) بحساب المستخدم المسجل"""
    try:
        data = request.json
        device_id = data.get("device_id")

        if not device_id:
            return jsonify({"success": False, "message": "Device ID required"}), 400

        # تحديث سجل البصمة لإضافة إيميل المستخدم صاحب الجهاز
        fingerprints_collection.update_one(
            {"device_id": device_id},
            {"$set": {"owner_email": user_email, "linked_at": datetime.datetime.utcnow()}}
        )

        return jsonify({"success": True, "message": "Device linked to your account"}), 200

    except Exception as e:
        print(f"❌ Device Linking Error: {str(e)}")
        return jsonify({"success": False, "message": "Linking failed"}), 500