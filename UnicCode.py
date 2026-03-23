#https://github.com/RedDiamond2/2fa-backend/edit/main/UnicCode.py
import secrets
from datetime import datetime
from flask import jsonify

def generate_unique_secure_code(db, length=7):
    """توليد كود آمن والتأكد من عدم وجوده مسبقاً في قاعدة البيانات"""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789" # استبعاد الأحرف المتشابهة O, 0, I, 1
    while True:
        code = ''.join(secrets.choice(alphabet) for _ in range(length))
        # التأكد من أن الكود غير مستخدم من قبل أي مستخدم آخر
        if not db.users.find_one({"unic_code": code}):
            return code

def handle_unic_code_request(data, db):
    email = data.get("email")
    if not email:
        return jsonify({"status": "error", "message": "Email is required"}), 400

    # 1. التحقق هل المستخدم حصل على كود مسبقاً؟
    user = db.users.find_one({"email": email})
    
    if user and user.get("unic_code_issued"):
        return jsonify({
            "status": "already_issued",
            "message": "تم إرسال كود لهذا الحساب مسبقاً."
        }), 200

    # 2. توليد كود فريد تماماً
    new_code = generate_unique_secure_code(db)

    # 3. حفظ الحالة في قاعدة البيانات
    db.users.update_one(
        {"email": email},
        {
            "$set": {
                "unic_code": new_code,
                "unic_code_issued": True,
                "issued_at": datetime.utcnow()
            }
        },
        upsert=True
    )

    return jsonify({
        "status": "success",
        "code": new_code
    }), 201
