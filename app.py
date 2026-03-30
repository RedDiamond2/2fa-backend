# app.py
import os
import hmac
import hashlib
import base64
import json
import time
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient

# --- 1. استيراد المسارات (Blueprints) ---
from routes.auth import auth_bp
from routes.gems import gems_bp

# محاولة استيراد الملحقات الإضافية (تأكد من وجود هذه الملفات في المجلد الرئيسي)
try:
    from google_oauth import google_api
    from collect import collect_api
    from UnicCode import handle_unic_code_request
except ImportError as e:
    print(f"⚠️ تنبيه: تعذر تحميل بعض الملحقات، تأكد من وجود الملفات المطلوبة: {e}")

# ==========================================
# 2. الإعدادات والبيئة (Configuration)
# ==========================================
app = Flask(__name__)

# إعداد CORS للسماح بالاتصال من موقعك ومن المتصفح المحلي
CORS(app, resources={r"/*": {
    "origins": ["http://localhost:8000", "https://RedDiamond2.github.io"],
    "methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"]
}})

# جلب مفاتيح البيئة من Render
MONGO_URI = os.environ.get("MONGO_URI")
API_KEY = os.environ.get("API_KEY") # مفتاح EasyEmailAPI
LINK_SECRET_KEY = os.environ.get("LINK_SECRET_KEY", "RED_DIAMOND_SECURE_KEY_2026_X99")
app.config['SECRET_KEY'] = os.environ.get("APP_SECRET_KEY", "RD_SUPER_SECRET_2026")

# الاتصال بـ MongoDB Atlas
try:
    client = MongoClient(MONGO_URI)
    db = client.get_database() # سيستخدم الاسم الموجود في الرابط تلقائياً
    fingerprints_col = db.fingerprints
    print("✅ Connected to MongoDB Atlas Successfully")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")

# ==========================================
# 3. تسجيل المسارات (Registering Blueprints)
# ==========================================
# ملاحظة: تم تسجيل كل Blueprint مرة واحدة فقط لتجنب خطأ "already registered"
app.register_blueprint(auth_bp) # المسارات: /collect و غيرها
app.register_blueprint(gems_bp, url_prefix='/api/gems') # المسارات: /api/gems/status

# تسجيل الملحقات إذا تم تحميلها بنجاح
try:
    if 'google_api' in globals(): app.register_blueprint(google_api)
    if 'collect_api' in globals(): app.register_blueprint(collect_api)
except Exception as e:
    print(f"❌ Blueprint Registration Error: {e}")

# ==========================================
# 4. البيانات الثابتة والترجمة (Translations)
# ==========================================
ALLOWED_DOMAINS = [
    "gmail.com","yahoo.com","outlook.com","hotmail.com","protonmail.com","icloud.com",
    "zoho.com","aol.com","gmx.com","mail.com","yandex.com"
]

translations = {
    "ar": {
        "no_email":"لم يتم إدخال البريد", "unsupported":"هذا البريد غير مدعوم ❌",
        "disposable":"بريد مؤقت غير مقبول ❌", "low_score":"موثوقية البريد ضعيفة ⚠️",
        "invalid_mx":"خادم البريد غير صالح", "valid":"الإيميل صالح ✅",
        "fail":"فشل التحقق", "link_invalid":"رابط غير صالح ❌", "link_expired":"انتهت الصلاحية ⏰"
    },
    "en": {
        "no_email":"No email provided", "unsupported":"Unsupported email ❌",
        "disposable":"Disposable email ❌", "low_score":"Low reliability ⚠️",
        "invalid_mx":"Invalid mail server", "valid":"Email is valid ✅",
        "fail":"Verification failed", "link_invalid":"Invalid link ❌", "link_expired":"Link expired ⏰"
    }
}

# ==========================================
# 5. المسارات والخدمات (Main Routes)
# ==========================================

def get_client_ip():
    """جلب الآي بي الحقيقي للمستخدم حتى خلف Proxy"""
    return request.headers.get("CF-Connecting-IP") or \
           request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or \
           request.remote_addr

@app.route('/generate-unic', methods=['POST', 'OPTIONS'])
def generate_unic():
    if request.method == "OPTIONS": return jsonify({"status":"ok"}), 200
    try:
        return handle_unic_code_request(request.json, db)
    except NameError:
        return jsonify({"error": "UnicCode module not loaded"}), 500

@app.route("/verify-link", methods=["POST"])
def verify_link():
    data_in = request.json
    p_encoded = data_in.get("data")
    p_sig = data_in.get("sig")
    lang = data_in.get("lang", "ar")
    t = translations.get(lang, translations["ar"])

    if not p_encoded or not p_sig:
        return jsonify({"valid": False, "message": t["link_invalid"]}), 400

    # التحقق من صحة التوقيع (HMAC)
    expected = hmac.new(LINK_SECRET_KEY.encode(), p_encoded.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, p_sig):
        return jsonify({"valid": False, "message": t["link_invalid"]}), 403

    try:
        # إضافة Padding للـ Base64 إذا لزم الأمر
        rem = len(p_encoded) % 4
        if rem: p_encoded += '=' * (4 - rem)
        
        payload = json.loads(base64.urlsafe_b64decode(p_encoded))
        if int(time.time()) > payload.get("e", 0):
            return jsonify({"valid": False, "message": t["link_expired"]}), 403
            
        return jsonify({"valid": True, "payload": payload})
    except:
        return jsonify({"valid": False, "message": t["link_invalid"]}), 400

@app.route("/check-email", methods=["POST"])
def check_email():
    data = request.json
    email = data.get("email")
    lang = data.get("lang", "ar")
    t = translations.get(lang, translations["ar"])

    if not email: return jsonify({"success": False, "message": t["no_email"]}), 400

    domain = email.split("@")[-1].lower()
    if domain not in ALLOWED_DOMAINS:
        return jsonify({"success": False, "message": t["unsupported"]}), 400

    try:
        r = requests.get(f"https://easyemailapi.com/api/verify/{email}", 
                         headers={"Authorization": f"Bearer {API_KEY}"}, timeout=10)
        res = r.json()
        if res.get("disposable"): return jsonify({"success": False, "message": t["disposable"]})
        if res.get("score", 0) < 60: return jsonify({"success": False, "message": t["low_score"]})
        return jsonify({"success": True, "message": t["valid"]})
    except:
        return jsonify({"success": False, "message": t["fail"]}), 500

@app.route("/health")
def health_check():
    return jsonify({"status": "healthy", "server": "Red Diamond v2.0"}), 200

# ==========================================
# 6. التشغيل (Final Execution)
# ==========================================
if __name__ == "__main__":
    # Render يطلب الاستماع على البورت الممرر في متغيرات البيئة
    port = int(os.environ.get("PORT", 5000))
    # نستخدم debug=False في الإنتاج لضمان أداء مستقر وأمان عالٍ
    app.run(host="0.0.0.0", port=port, debug=False)