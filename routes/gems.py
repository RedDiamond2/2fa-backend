# routes/gems.py
from flask import Blueprint, request, jsonify
import datetime
import uuid
from models.mongo_db import gems_collection, transactions_collection
from services.auth_service import decode_token

# تعريف الـ Blueprint بدون بادئة هنا لأننا سنحددها في app.py
gems_bp = Blueprint('gems', __name__)

def get_user_from_token():
    """استخراج البريد الإلكتروني من توكن JWT في الهيدر"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(" ")[1]
    # استخدام الدالة التي عرفتها أنت في auth_service
    result = decode_token(token)
    
    # التأكد أن النتيجة إيميل وليس رسالة خطأ نصية
    if isinstance(result, str) and "@" in result:
        return result
    return None

# --- المسارات (Endpoints) ---

# لاحظ: المسار هنا أصبح /status فقط لأن البادئة /api/gems مضافة في app.py
@gems_bp.route('/status', methods=['GET', 'OPTIONS'])
def get_gems_status():
    # معالجة طلب Preflight الخاص بـ CORS
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    email = get_user_from_token()
    if not email:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    # 1. البحث عن سجل الجواهر
    user_gems = gems_collection.find_one({"email": email})
    
    if not user_gems:
        # إنشاء حساب جديد بـ 50 جوهرة (هدية ترحيبية)
        user_gems = {
            "email": email,
            "balance": 50,
            "referral_code": str(uuid.uuid4())[:8].upper(),
            "created_at": datetime.datetime.utcnow()
        }
        gems_collection.insert_one(user_gems)
        
        # تسجيل العملية الأولى
        transactions_collection.insert_one({
            "email": email,
            "amount": 50,
            "type": "credit",
            "reason": "Welcome Bonus 🎁",
            "timestamp": datetime.datetime.utcnow()
        })

    # 2. جلب سجل العمليات وتحويل التاريخ لنص صالح للـ JSON
    raw_history = list(transactions_collection.find(
        {"email": email}, 
        {"_id": 0}
    ).sort("timestamp", -1).limit(10))

    # تحويل timestamp إلى صيغة ISO ليتمكن JavaScript من قراءتها
    history = []
    for trx in raw_history:
        if isinstance(trx['timestamp'], datetime.datetime):
            trx['timestamp'] = trx['timestamp'].isoformat()
        history.append(trx)

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

    referrer = gems_collection.find_one({"referral_code": ref_code})
    
    if referrer and referrer['email'] != new_user_email:
        # إضافة 30 جوهرة للمُحيل
        gems_collection.update_one(
            {"email": referrer['email']},
            {"$inc": {"balance": 30}}
        )
        
        transactions_collection.insert_one({
            "email": referrer['email'],
            "amount": 30,
            "type": "credit",
            "reason": "Referral Bonus 💎",
            "timestamp": datetime.datetime.utcnow()
        })
        
        return jsonify({"success": True, "message": "Bonus added"})
    
    return jsonify({"success": False, "message": "Invalid code"}), 404