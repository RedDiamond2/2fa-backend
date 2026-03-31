# app.py
# app.py
# Red Diamond v2.7 - Production Ready
# تم دمج إصلاحات CORS، المسارات المفقودة، وتوافق Blueprints

import os
import hmac
import hashlib
import base64
import json
import time
import datetime
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- 1. استيراد الإعدادات المركزية ---
from config import config

# --- 2. استيراد نماذج قاعدة البيانات ---
from models.mongo_db import fingerprints_col, db

# --- 3. استيراد المسارات (Blueprints) ---
from routes.auth import auth_bp
from routes.gems import gems_bp
from routes.user import user_bp
from routes.collect import collect_api
from routes.logout import logout_bp

# استيراد الملحقات الديناميكية (في الجذر)
try:
    from google_oauth import google_api
except ImportError:
    google_api = None
    print("⚠️ Warning: Google OAuth module not found.")

# ==========================================
# 4. تهيئة التطبيق (Initialization)
# ==========================================
app = Flask(__name__)
app.config.from_object(config)

# إعداد CORS الاحترافي لحل مشاكل الاتصال من GitHub Pages
CORS(app, resources={r"/*": {
    "origins": config.ALLOWED_ORIGINS,
    "methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"]
}})

# جلب المفاتيح من ملف config
LINK_SECRET_KEY = config.LINK_SECRET_KEY
API_KEY = config.EMAIL_API_KEY

# ==========================================
# 5. تسجيل المسارات (Registering Blueprints)
# ==========================================
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(gems_bp, url_prefix='/api/gems')
app.register_blueprint(user_bp, url_prefix='/api/user')
app.register_blueprint(collect_api, url_prefix='/api') # تم توحيدها تحت /api
app.register_blueprint(logout_bp, url_prefix='/api')

if google_api:
    try:
        app.register_blueprint(google_api, url_prefix='/auth/google')
    except Exception as e:
        print(f"❌ Google OAuth Blueprint Error: {e}")

# ==========================================
# 6. البيانات الثابتة والترجمة (Translations)
# ==========================================
ALLOWED_DOMAINS = [
    "gmail.com","yahoo.com","outlook.com","hotmail.com","protonmail.com",
    "icloud.com","zoho.com","aol.com","gmx.com","mail.com","yandex.com"
]

translations = {
    "ar": {
        "no_email":"لم يتم إدخال البريد", "unsupported":"هذا البريد غير مدعوم ❌",
        "disposable":"بريد مؤقت غير مقبول ❌", "low_score":"موثوقية البريد ضعيفة ⚠️",
        "valid":"الإيميل صالح ✅", "fail":"فشل التحقق", 
        "link_invalid":"رابط غير صالح ❌", "link_expired":"انتهت الصلاحية ⏰"
    },
    "en": {
        "no_email":"No email provided", "unsupported":"Unsupported email ❌",
        "disposable":"Disposable email ❌", "low_score":"Low reliability ⚠️",
        "valid":"Email is valid ✅", "fail":"Verification failed", 
        "link_invalid":"Invalid link ❌", "link_expired":"Link expired ⏰"
    },
    "fr": {
        "no_email":"Aucun email fourni", "unsupported":"Email non supporté ❌",
        "disposable":"Email temporaire ❌", "low_score":"Fiabilité faible ⚠️",
        "valid":"Email valide ✅", "fail":"Échec de vérification", 
        "link_invalid":"Lien invalide ❌", "link_expired":"Lien expiré ⏰"
    }
}

# ==========================================
# 7. الوظائف المساعدة (Utilities)
# ==========================================
def get_client_ip():
    """جلب الآي بي الحقيقي للمستخدم حتى خلف الـ Proxy"""
    return request.headers.get("CF-Connecting-IP") or \
           request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or \
           request.remote_addr

# ==========================================
# 8. المسارات الرئيسية (Core App Routes)
# ==========================================

@app.route("/api/geo-lite", methods=["GET"])
def detect_location():
    """تحديد الدولة والآي بي لخدمة واجهة المستخدم"""
    ip = get_client_ip()
    try:
        r = requests.get(f"https://ipwho.is/{ip}", timeout=5)
        res = r.json()
        return jsonify({
            "ip": ip,
            "country": res.get("country_code", "DZ"),
            "city": res.get("city", "Unknown")
        })
    except:
        return jsonify({"ip": ip, "country": "DZ", "status": "fallback"})

@app.route("/generate-unic", methods=["POST", "OPTIONS"])
@app.route("/api/generate-unic", methods=["POST", "OPTIONS"])
def generate_unic_code():
    """خدمة الرمز الموحد لملف OneTimeUnicCode.js"""
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
    import uuid
    code = str(uuid.uuid4())[:8].upper()
    return jsonify({"success": True, "code": code}), 200

@app.route("/verify-link", methods=["POST"])
def verify_link_hmac():
    """التحقق من صحة الروابط المشفرة"""
    data_in = request.json
    p_encoded = data_in.get("data")
    p_sig = data_in.get("sig")
    lang = data_in.get("lang", "ar")
    t = translations.get(lang, translations["ar"])

    if not p_encoded or not p_sig:
        return jsonify({"valid": False, "message": t["link_invalid"]}), 400

    expected = hmac.new(LINK_SECRET_KEY.encode(), p_encoded.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, p_sig):
        return jsonify({"valid": False, "message": t["link_invalid"]}), 403

    try:
        rem = len(p_encoded) % 4
        if rem: p_encoded += '=' * (4 - rem)
        payload = json.loads(base64.urlsafe_b64decode(p_encoded))
        if int(time.time()) > payload.get("e", 0):
            return jsonify({"valid": False, "message": t["link_expired"]}), 403
        return jsonify({"valid": True, "payload": payload})
    except:
        return jsonify({"valid": False, "message": t["link_invalid"]}), 400

@app.route("/check-email", methods=["POST"])
@app.route("/api/check-email", methods=["POST"])
def validate_user_email():
    """التحقق من صلاحية البريد الإلكتروني وبدء جلسة العمل"""
    data = request.json
    email = data.get("email")
    lang = data.get("lang", "ar")
    t = translations.get(lang, translations["ar"])

    if not email: 
        return jsonify({"success": False, "message": t["no_email"]}), 400

    domain = email.split("@")[-1].lower()
    if domain not in ALLOWED_DOMAINS:
        return jsonify({"success": False, "message": t["unsupported"]}), 400
    
    try:
        r = requests.get(f"https://easyemailapi.com/api/verify/{email}", 
                         headers={"Authorization": f"Bearer {API_KEY}"}, timeout=10)
        res = r.json()
        
        if res.get("disposable"): return jsonify({"success": False, "message": t["disposable"]})
        if res.get("score", 0) < 60: return jsonify({"success": False, "message": t["low_score"]})

        from services.auth_service import generate_token
        token = generate_token(email)
        
        return jsonify({
            "success": True, 
            "message": t["valid"], 
            "token": token
        })
    except Exception as e:
        print(f"❌ Email Verification Error: {e}")
        return jsonify({"success": False, "message": t["fail"]}), 500

@app.route("/health")
def health():
    """مسار Render للتأكد من عمل السيرفر"""
    return jsonify({
        "status": "online", 
        "db_connected": db is not None,
        "timestamp": datetime.datetime.utcnow().isoformat()
    }), 200

@app.route('/country', methods=['GET'])
def get_country():
    country = request.headers.get("CF-Ipcountry") or "DZ"
    return jsonify({"country": country, "success": True}), 200

# ==========================================
# 9. التشغيل (Run)
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)