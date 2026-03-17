from flask import Flask, request, jsonify
from flask_cors import CORS
import random, time, hashlib
import smtplib
from email.mime.text import MIMEText
import threading

# ================================
# إعدادات Flask
# ================================
app = Flask(__name__)
CORS(app)  # السماح بالوصول من أي نطاق

# ================================
# إعدادات Gmail SMTP
# ================================
GMAIL_USER = "ip8a2024@gmail.com"            # ضع هنا بريدك
GMAIL_PASS = "lfyr mkds gioy ltlu"          # ضع هنا App Password من Gmail

# ================================
# تخزين OTP مؤقت
# ================================
otp_store = {}  # الشكل: {email: {"otp": hashed, "exp": timestamp}}

# ================================
# دوال مساعدة
# ================================
def hash_otp(otp: str) -> str:
    """تشفير OTP باستخدام SHA256"""
    return hashlib.sha256(otp.encode()).hexdigest()

def send_email(to_email: str, otp: str):
    """إرسال OTP باستخدام Gmail SMTP"""
    try:
        msg = MIMEText(f"<h2>Your OTP is: {otp}</h2>", "html")
        msg['Subject'] = "Your OTP Code"
        msg['From'] = GMAIL_USER
        msg['To'] = to_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.send_message(msg)

        print(f"[INFO] OTP sent successfully to {to_email}")

    except Exception as e:
        print(f"[ERROR] Failed to send OTP to {to_email}: {e}")

def cleanup_expired_otps():
    """تنظيف OTP المنتهية صلاحيتها كل دقيقة"""
    now = time.time()
    expired = [email for email, data in otp_store.items() if now > data["exp"]]
    for email in expired:
        del otp_store[email]
    threading.Timer(60, cleanup_expired_otps).start()  # استدعاء كل دقيقة

# بدء التنظيف الدوري
cleanup_expired_otps()

# ================================
# Routes
# ================================
@app.route("/ping")
def ping():
    return "pong", 200

@app.route("/send-otp", methods=["POST"])
def send_otp():
    """إرسال OTP إلى البريد"""
    data = request.json
    email = data.get("email")
    if not email:
        return jsonify({"error": "Email required"}), 400

    otp = str(random.randint(100000, 999999))
    otp_store[email] = {
        "otp": hash_otp(otp),
        "exp": time.time() + 300  # صلاحية 5 دقائق
    }

    # إرسال البريد في Thread لتجنب تأخير الطلب
    threading.Thread(target=send_email, args=(email, otp), daemon=True).start()
    return jsonify({"success": True})

@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    """التحقق من OTP"""
    data = request.json
    email = data.get("email")
    otp = data.get("otp")
    stored = otp_store.get(email)

    if not stored:
        return jsonify({"error": "No OTP"}), 400
    if time.time() > stored["exp"]:
        del otp_store[email]
        return jsonify({"error": "Expired"}), 400
    if stored["otp"] != hash_otp(otp):
        return jsonify({"error": "Wrong OTP"}), 400

    # حذف OTP بعد التحقق
    del otp_store[email]
    return jsonify({"success": True})

# ================================
# تشغيل السيرفر
# ================================
if __name__ == "__main__":
    # debug=False لمنع إعادة التشغيل المتكرر في Free Instances
    app.run(debug=False, host="0.0.0.0", port=8000)
