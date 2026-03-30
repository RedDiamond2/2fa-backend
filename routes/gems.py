# routes/gems.py
from flask import Blueprint, request, jsonify
import datetime
import uuid
from models.mongo_db import gems_collection, transactions_collection, users_collection
from services.auth_service import decode_token

gems_bp = Blueprint('gems', __name__)

def get_user_from_token():
    """استخراج البريد الإلكتروني من توكن JWT"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    token = auth_header.split(" ")[1]
    result = decode_token(token)
    return result if isinstance(result, str) and "@" in result else None

@gems_bp.route('/status', methods=['GET', 'OPTIONS'])
def get_gems_status():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    email = get_user_from_token()
    if not email:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    # 1. محاولة جلب البيانات من مجموعة الجواهر
    user_gems = gems_collection.find_one({"email": email})
    
    # 2. إذا لم يجد في gems، نبحث في users (توافق مع النظام القديم)
    if not user_gems:
        user_info = users_collection.find_one({"email": email})
        
        # إنشاء سجل جواهر جديد
        user_gems = {
            "email": email,
            "balance": 50,
            "referral_code": (user_info.get("unic_code") if user_info else str(uuid.uuid4())[:8].upper()),
            "created_at": datetime.datetime.utcnow()
        }
        gems_collection.insert_one(user_gems)
        
        # تسجيل هدية الترحيب
        transactions_collection.insert_one({
            "email": email,
            "amount": 50,
            "type": "credit",
            "reason": "Welcome Bonus 🎁",
            "timestamp": datetime.datetime.utcnow()
        })

    # 3. جلب سجل العمليات
    history = list(transactions_collection.find(
        {"email": email}, {"_id": 0}
    ).sort("timestamp", -1).limit(10))

    # تحويل التواريخ لنصوص
    for trx in history:
        if isinstance(trx.get('timestamp'), datetime.datetime):
            trx['timestamp'] = trx['timestamp'].isoformat()

    return jsonify({
        "success": True,
        "balance": user_gems.get("balance", 0),
        "referral_code": user_gems.get("referral_code", "RD-NEW"),
        "history": history
    })

@gems_bp.route('/add_by_ref', methods=['POST'])
def add_referral_gems():
    data = request.json
    ref_code = data.get('ref_code')
    new_user_email = get_user_from_token()

    if not ref_code or not new_user_email:
        return jsonify({"success": False, "message": "Invalid request"}), 400

    # البحث عن صاحب الكود في مجموعة الجواهر
    referrer = gems_collection.find_one({"referral_code": ref_code})
    
    if referrer and referrer['email'] != new_user_email:
        # إضافة 30 جوهرة للمُحيل
        gems_collection.update_one(
            {"email": referrer['email']},
            {"$inc": {"balance": 30}}
        )
        
        # تسجيل العملية
        transactions_collection.insert_one({
            "email": referrer['email'],
            "amount": 30,
            "type": "credit",
            "reason": f"Referral Bonus (New User) 💎",
            "timestamp": datetime.datetime.utcnow()
        })
        
        return jsonify({"success": True, "message": "Bonus added to referrer"})
    
    return jsonify({"success": False, "message": "Invalid or self-referral code"}), 400