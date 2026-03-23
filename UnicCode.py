#https://github.com/RedDiamond2/2fa-backend/edit/main/UnicCode.py
import secrets
import string
from flask import jsonify

# نفترض أن لديك دالة للاتصال بقاعدة البيانات (Firebase أو MongoDB أو SQL)
# سنقوم بمحاكاة التحقق هنا
def is_code_unique(code, db):
    # ابحث في قاعدة البيانات عن الكود
    # return True إذا كان غير موجود (فريد)
    # return False إذا كان موجوداً مسبقاً
    pass

def generate_secure_unic_code(length=8):
    # استخدام حروف وأرقام واضحة (تجنب O, 0, I, 1)
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        code = ''.join(secrets.choice(alphabet) for _ in range(length))
        # تحقق من التكرار في قاعدة البيانات (Logic)
        # if is_code_unique(code, db): 
        return code

def handle_unic_code_request(user_data, db):
    """
    المنطق: 
    1. التحقق هل المستخدم لديه كود سابق؟
    2. إذا لا: توليد كود جديد، حفظه، إرساله مع حالة 'new'.
    3. إذا نعم: إرسال حالة 'already_issued' دون إظهار الكود الأصلي.
    """
    email = user_data.get('email')
    
    # ابحث عن المستخدم في قاعدة البيانات
    user_record = db.users.find_one({"email": email})
    
    if user_record and user_record.get('unic_code'):
        return jsonify({
            "status": "already_issued",
            "message": "لقد تم توليد رمز لك مسبقاً في تاريخ " + user_record.get('issued_at'),
            "code": None # لا نرسل الكود مرة أخرى لأسباب أمنية
        }), 200
    
    # توليد كود جديد وفريد
    new_code = generate_secure_unic_code()
    
    # حفظ الكود في قاعدة البيانات مع طابع زمني
    db.users.update_one(
        {"email": email},
        {"$set": {
            "unic_code": new_code,
            "issued_at": user_data.get('timestamp'),
            "has_received": True
        }},
        upsert=True
    )
    
    return jsonify({
        "status": "success",
        "code": new_code,
        "message": "تم توليد الرمز بنجاح. احتفظ به جيداً."
    }), 201
