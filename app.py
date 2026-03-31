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
# تأكد من وجود هذه الملفات في مجلد routes أو المجلد الرئيسي
from routes.auth import auth_bp
from routes.gems import gems_bp
from routes.logout import logout_bp

try:
    from google_oauth import google_api
    from collect import collect_api
    from UnicCode import handle_unic_code_request
except ImportError as e:
    print(f"⚠️ تنبيه: تعذر تحميل بعض الملحقات البرمجية: {e}")

# ==========================================
# 2. الإعدادات والبيئة (Configuration)
# ==========================================
app = Flask(__name__)

# إعداد CORS للسماح بالاتصال من موقع GitHub ومن البيئة المحلية
CORS(app, resources={r"/*": {
    "origins": ["http://localhost:8000", "https://reddiamond2.github.io"],
    "methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["Content-Type", "Authorization"]
}})

# جلب مفاتيح البيئة من Render (تأكد من إضافتها في Environment Variables)
MONGO_URI = os.environ.get("MONGO_URI")
API_KEY = os.environ.get("API_KEY") 
LINK_SECRET_KEY = os.environ.get("LINK_SECRET_KEY", "RED_DIAMOND_SECURE_KEY_2026_X99")
app.config['SECRET_KEY'] = os.environ.get("APP_SECRET_KEY", "RD_SUPER_SECRET_2026")

# الاتصال بـ MongoDB Atlas
try:
    client = MongoClient(MONGO_URI)
    db = client.get_database() 
    fingerprints_col = db.fingerprints
    print("✅ Connected to MongoDB Atlas Successfully")
except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")

# ==========================================
# 3. تسجيل المسارات (Registering Blueprints)
# ==========================================
app.register_blueprint(auth_bp)
app.register_blueprint(gems_bp, url_prefix='/api/gems')
app.register_blueprint(logout_bp)

# تسجيل الملحقات الديناميكية
try:
    if 'google_api' in globals(): app.register_blueprint(google_api)
    if 'collect_api' in globals(): app.register_blueprint(collect_api)
except Exception as e:
    print(f"❌ Blueprint Registration Error: {e}")

# ==========================================
# 4. البيانات الثابتة والترجمة (Translations & Config)
# ==========================================
ALLOWED_DOMAINS = [
    "gmail.com","yahoo.com","outlook.com","hotmail.com","protonmail.com","icloud.com",
    "zoho.com","aol.com","gmx.com","mail.com","yandex.com","mail.ru"
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
    },
    "fr": {
        "no_email":"Aucun email fourni", "unsupported":"Email non supporté ❌",
        "disposable":"Email temporaire ❌", "low_score":"Fiabilité faible ⚠️",
        "invalid_mx":"Serveur email invalide", "valid":"Email valide ✅",
        "fail":"Échec de vérification", "link_invalid":"Lien invalide ❌", "link_expired":"Lien expiré ⏰"
    }
}

# ==========================================
# 5. الوظائف المساعدة (Utilities)
# ==========================================

def get_client_ip():
    """جلب الآي بي الحقيقي للمستخدم حتى خلف وكلاء الشحن (Proxy)"""
    if request.headers.get("CF-Connecting-IP"):
        return request.headers.get("CF-Connecting-IP")
    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr

# ==========================================
# 6. المسارات الرئيسية (Core Routes)
# ==========================================

@app.route("/country", methods=["GET"])
def detect_country():
    """تحديد الدولة بناءً على الـ IP (لحل خطأ 404 في الهاتف)"""
    try:
        ip = get_client_ip()
        r = requests.get(f"https://ipwho.is/{ip}", timeout=5)
        res = r.json()
        return jsonify({
            "ip": ip,
            "country": res.get("country_code", "DZ")
        })
    except:
        return jsonify({"ip": get_client_ip(), "country": "DZ"})

@app.route("/geo", methods=["GET"])
def geo_info():
    """جلب بيانات الموقع الجغرافي الكاملة (لحل خطأ 404 في info.js)"""
    ip = get_client_ip()
    try:
        r = requests.get(f"http://ip-api.com/json/{ip}?fields=66842623", timeout=5)
        return jsonify(r.json())
    except:
        return jsonify({"status": "fail", "query": ip})

@app.route("/verify-link", methods=["POST"])
def verify_link():
    """التحقق من صحة الروابط المشفرة بـ HMAC"""
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
def check_email():
    """التحقق من البريد الإلكتروني وتوليد جلسة المستخدم"""
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

        # إنشاء الجلسة وتوليد التوكن (استيراد محلي لتجنب التعارض)
        from routes.auth import setup_user_session
        token = setup_user_session(email, {}, data) 
        
        return jsonify({"success": True, "message": t["valid"], "token": token})
    except Exception as e:
        return jsonify({"success": False, "message": t["fail"]}), 500

@app.route("/fingerprints", methods=["GET"])
def list_fingerprints():
    """عرض سجلات البصمة الرقمية (للإدارة فقط)"""
    try:
        records = list(fingerprints_col.find({}, {"_id": 0}).sort("timestamp", -1).limit(50))
        return jsonify(records)
    except:
        return jsonify([])

@app.route("/health")
def health_check():
    return jsonify({"status": "healthy", "version": "2.0-Production"}), 200

# ==========================================
# 7. التشغيل (Final Execution)
# ==========================================
if __name__ == "__main__":
    # الحصول على المنفذ من Render أو استخدتم 5000 محلياً
    port = int(os.environ.get("PORT", 5000))
    # وضع debug=False ضروري لبيئة الإنتاج لضمان الأمان
    app.run(host="0.0.0.0", port=port, debug=False)