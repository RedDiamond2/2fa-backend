# routes/gems.py
import datetime
import uuid
from flask import Blueprint, request, jsonify
from models.mongo_db import gems_col, transactions_col
from middleware.auth_guard import token_required
from services.gem_service import GemService

# تعريف الـ Blueprint (يتم تحديد url_prefix='/api/gems' في app.py)
gems_bp = Blueprint('gems', __name__)

# ==========================================
# 1. مسار حالة الجواهر (Gems Status)
# ==========================================
@gems_bp.route('/status', methods=['GET'])
@token_required
def get_gems_status(user_email):
    """
    جلب رصيد الجواهر، كود الإحالة، وسجل آخر 10 عمليات.
    يتم تمرير user_email تلقائياً بواسطة @token_required.
    """
    try:
        # 1. البحث عن سجل الجواهر للمستخدم
        user_gems = gems_col.find_one({"email": user_email})
        
        # 2. إذا كان المستخدم جديداً (أول مرة يفتح البروفايل)
        if not user_gems:
            # توليد كود إحالة فريد
            new_ref_code = str(uuid.uuid4())[:8].upper()
            
            user_gems = {
                "email": user_email,
                "balance": 50,  # الهدية الترحيبية
                "referral_code": new_ref_code,
                "created_at": datetime.datetime.utcnow()
            }
            gems_col.insert_one(user_gems)
            
            # تسجيل العملية في جدول المعاملات
            transactions_col.insert_one({
                "email": user_email,
                "amount": 50,
                "type": "credit",
                "reason": "Welcome Bonus 🎁",
                "timestamp": datetime.datetime.utcnow()
            })

        # 3. جلب آخر 10 عمليات من السجل
        raw_history = list(transactions_col.find(
            {"email": user_email}, 
            {"_id": 0}
        ).sort("timestamp", -1).limit(10))

        # 4. تنسيق التاريخ ليكون صالحاً لـ JSON (ISO Format)
        formatted_history = []
        for trx in raw_history:
            if isinstance(trx.get('timestamp'), datetime.datetime):
                trx['timestamp'] = trx['timestamp'].isoformat()
            formatted_history.append(trx)

        return jsonify({
            "success": True,
            "balance": user_gems.get("balance", 0),
            "referral_code": user_gems.get("referral_code", "RD-NEW"),
            "history": formatted_history
        }), 200

    except Exception as e:
        print(f"❌ Gems Status Error: {str(e)}")
        return jsonify({"success": False, "message": "Failed to fetch gems data"}), 500

# ==========================================
# 2. مسار إضافة جواهر الإحالة (Referral)
# ==========================================
@gems_bp.route('/add_by_ref', methods=['POST'])
@token_required
def add_referral_gems(user_email):
    """
    إضافة جواهر للشخص الذي قام بدعوة المستخدم الحالي.
    """
    try:
        data = request.json
        ref_code = data.get('ref_code')

        if not ref_code:
            return jsonify({"success": False, "message": "Referral code is required"}), 400

        # البحث عن صاحب الكود (المُحيل)
        referrer = gems_col.find_one({"referral_code": ref_code})
        
        # التأكد من وجود الكود وأن المستخدم لا يحاول استخدام كوده الخاص
        if not referrer:
            return jsonify({"success": False, "message": "Invalid referral code"}), 404
            
        if referrer['email'] == user_email:
            return jsonify({"success": False, "message": "You cannot refer yourself!"}), 400

        # التحقق إذا كان هذا المستخدم قد استخدم كود إحالة سابقاً (اختياري حسب منطقك)
        # هنا سنقوم بإضافة 30 جوهرة للمُحيل (Referrer)
        gems_col.update_one(
            {"email": referrer['email']},
            {"$inc": {"balance": 30}}
        )
        
        # تسجيل العملية في سجل المُحيل
        transactions_col.insert_one({
            "email": referrer['email'],
            "amount": 30,
            "type": "credit",
            "reason": "Referral Bonus (New Friend) 💎",
            "timestamp": datetime.datetime.utcnow()
        })
        
        return jsonify({"success": True, "message": "Bonus added to your friend!"}), 200

    except Exception as e:
        print(f"❌ Referral Error: {str(e)}")
        return jsonify({"success": False, "message": "Processing referral failed"}), 500

# ==========================================
# 3. مسار المطالبة بجوائز المهام (Rewards)
# ==========================================
@gems_bp.route('/claim-reward', methods=['POST'])
@token_required
def claim_profile_reward(user_email):
    """
    استلام مكافأة عند إكمال بيانات معينة (مثل رقم الهاتف).
    """
    try:
        data = request.json
        field = data.get('field') # مثلاً: 'phone_verified'
        
        if not field:
            return jsonify({"success": False, "message": "Reward field is missing"}), 400
            
        # استدعاء الخدمة المختصة بمنطق الجواهر
        success, msg = GemService.handle_profile_reward(user_email, field)
        
        if success:
            return jsonify({"success": True, "message": msg}), 200
        else:
            return jsonify({"success": False, "message": msg}), 400

    except Exception as e:
        print(f"❌ Reward Claim Error: {str(e)}")
        return jsonify({"success": False, "message": "Reward processing error"}), 500