# routes/gems.py
# Red Diamond Project - Production Version 2026
# الوصف: إدارة الجواهر مع نظام حماية "المسؤولين" للعمليات اليدوية.

import datetime
import uuid
from flask import Blueprint, request, jsonify
from models.mongo_db import gems_col
from middleware.auth_guard import token_required
from services.gem_service import GemService
from config import Config

gems_bp = Blueprint('gems', __name__)

# ==========================================
# 1. جلب حالة الجواهر (للمستخدم العادي)
# ==========================================
@gems_bp.route('/status', methods=['GET'])
@token_required
def get_gems_status(user_email):
    try:
        stats = GemService.get_user_stats(user_email)
        if not stats:
            # إنشاء محفظة تلقائية إذا لم تكن موجودة
            new_ref = str(uuid.uuid4())[:8].upper()
            gems_col.insert_one({
                "email": user_email, "balance": 50, 
                "referral_code": new_ref, "created_at": datetime.datetime.utcnow()
            })
            return jsonify({"success": True, "balance": 50, "referral_code": new_ref, "history": []}), 200

        return jsonify({"success": True, **stats}), 200
    except Exception as e:
        return jsonify({"success": False, "message": "Error fetching stats"}), 500

# ==========================================
# 2. مسار العمليات اليدوية (محمي للمسؤولين فقط)
# ==========================================
@gems_bp.route('/transaction', methods=['POST'])
@token_required
def manual_transaction(user_email):
    """
    مسار إداري: لا يسمح بتنفيذه إلا لمجموعة ADMIN_EMAILS المعرفة في config.py
    """
    # 1. التحقق من صلاحيات المسؤول (Admin Authorization)
    admin_list = getattr(Config, 'ADMIN_EMAILS', [])
    if user_email not in admin_list:
        print(f"⚠️ Security Alert: Unauthorized Admin-Action attempt by {user_email}")
        return jsonify({"success": False, "message": "غير مسموح لك بالقيام بهذه العملية (صلاحيات مسؤول فقط)"}), 403

    try:
        data = request.get_json()
        target_email = data.get('target_email') # الإيميل المراد شحنه أو الخصم منه
        amount = data.get('amount', 0)
        reason = data.get('reason', 'Admin Correction')
        t_type = data.get('type', 'credit') # 'credit' or 'debit'

        # 2. التحقق من صحة البيانات وسقف العمليات (Max 1000)
        if not target_email or amount <= 0:
            return jsonify({"success": False, "message": "بيانات العملية غير مكتملة"}), 400
        
        if amount > 1000:
            return jsonify({"success": False, "message": "لا يمكن معالجة أكثر من 1000 جوهرة في عملية يدوية واحدة للأمان"}), 400

        # 3. تنفيذ العملية عبر الخدمة المركزية
        success, message = GemService.update_gems(target_email, amount, reason, t_type)

        if success:
            return jsonify({
                "success": True, 
                "message": f"تمت العملية بنجاح لحساب {target_email}",
                "new_action": f"{t_type}: {amount}"
            }), 200
        
        return jsonify({"success": False, "message": message}), 400

    except Exception as e:
        print(f"❌ Admin Transaction Error: {str(e)}")
        return jsonify({"success": False, "message": "حدث خطأ أثناء معالجة العملية"}), 500

# ==========================================
# 3. الإحالات والمكافآت (تستخدم GemService داخلياً)
# ==========================================
@gems_bp.route('/add_by_ref', methods=['POST'])
@token_required
def add_gems_by_referral(user_email):
    data = request.get_json()
    success, message = GemService.process_referral(data.get('ref_code'), user_email)
    return jsonify({"success": success, "message": message}), (200 if success else 400)

@gems_bp.route('/claim-reward', methods=['POST'])
@token_required
def claim_task_reward(user_email):
    data = request.get_json()
    success, message = GemService.handle_profile_reward(user_email, data.get('field'))
    return jsonify({"success": success, "message": message}), (200 if success else 400)