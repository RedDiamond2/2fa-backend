# routes/gems.py
from flask import Blueprint, request, jsonify
import datetime
import uuid
from models.mongo_db import users_collection, gems_collection, transactions_collection
from services.auth_service import decode_token

gems_bp = Blueprint('gems', __name__)

# --- وظائف مساعدة ---

def get_user_from_token():
    """استخراج المستخدم من التوكن الموجود في الـ Header"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(" ")[1]
    email = decode_token(token)
    
    if isinstance(email, str) and "@" in email:
        return email
    return None

# --- المسارات (Endpoints) ---

@gems_bp.route('/api/gems/status', methods=['GET'])
def get_gems_status():
    """جلب رصيد الجواهر، كود الإحالة، وسجل العمليات"""
    email = get_user_from_token()
    if not email:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    # 1. البحث عن رصيد المستخدم أو إنشاؤه إذا كان جديداً (ترحيب بـ 50 جوهرة)
    user_gems = gems_collection.find_one({"email": email})
    
    if not user_gems:
        # إنشاء سجل جواهر جديد (هدية التسجيل 50 جوهرة)
        new_status = {
            "email": email,
            "balance": 50,
            "referral_code": str(uuid.uuid4())[:8].upper(), # كود إحالة فريد
            "created_at": datetime.datetime.utcnow()
        }
        gems_collection.insert_one(new_status)
        
        # تسجيل عملية الهدية في السجل
        transactions_collection.insert_one({
            "email": email,
            "amount": 50,
            "type": "credit",
            "reason": "هدية ترحيبية 🎁",
            "timestamp": datetime.datetime.utcnow()
        })
        user_gems = new_status

    # 2. جلب آخر 10 عمليات من السجل
    history = list(transactions_collection.find(
        {"email": email}, 
        {"_id": 0}
    ).sort("timestamp", -1).limit(10))

    return jsonify({
        "success": True,
        "balance": user_gems.get("balance", 0),
        "referral_code": user_gems.get("referral_code", "RD-NEW"),
        "history": history
    })

@gems_bp.route('/api/gems/add_by_ref', methods=['POST'])
def add_referral_gems():
    """إضافة جواهر عند استخدام رابط إحالة (30 جوهرة)"""
    data = request.json
    ref_code = data.get('ref_code')
    new_user_email = get_user_from_token()

    if not ref_code or not new_user_email:
        return jsonify({"success": False, "message": "Invalid request"}), 400

    # البحث عن صاحب الكود
    referrer = gems_collection.find_one({"referral_code": ref_code})
    
    if referrer and referrer['email'] != new_user_email:
        # إضافة 30 جوهرة لصاحب الكود
        gems_collection.update_one(
            {"email": referrer['email']},
            {"$inc": {"balance": 30}}
        )
        
        # تسجيل العملية لصاحب الكود
        transactions_collection.insert_one({
            "email": referrer['email'],
            "amount": 30,
            "type": "credit",
            "reason": f"مكافأة دعوة مستخدم جديد 💎",
            "timestamp": datetime.datetime.utcnow()
        })
        
        return jsonify({"success": True, "message": "Referral bonus added"})
    
    return jsonify({"success": False, "message": "Invalid referral code"}), 404