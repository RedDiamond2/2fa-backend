from flask import Flask, request, jsonify
from flask_cors import CORS
import random, time, hashlib
import requests

app = Flask(__name__)
CORS(app)

# ================================
# تخزين OTP مؤقت
# ================================
otp_store = {}

# ضع مفتاح Resend الخاص بك هنا
RESEND_API_KEY = "re_Q1ohZ7ic_PNgnrB8nuLd7fBniA5xF5Kd8"

# ================================
# دوال مساعدة
# ================================
def hash_otp(otp):
    """تشفير OTP باستخدام SHA256"""
    return hashlib.sha256(otp.encode()).hexdigest()

def send_email(to_email, otp):
    """إرسال OTP عبر Resend API"""
    res = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "from": "onboarding@resend.dev",
            "to": [to_email],
            "subject": "Your OTP Code",
            "html": f"<h2>Your OTP is: {otp}</h2>"
        }
    )
    print("Email sent:", res.status_code, res.text)

# ================================
# Routes
# ================================
@app.route("/ping")
def ping():
    """فحص حالة السيرفر"""
    return "pong", 200

@app.route("/send-otp", methods=["POST"])
def send_otp():
    """إرسال OTP إلى البريد"""
    email = request.json.get("email")
    if not email:
        return jsonify({"error": "Email required"}), 400

    otp = str(random.randint(100000, 999999))
    otp_store[email] = {
        "otp": hash_otp(otp),
        "exp": time.time() + 300  # صلاحية 5 دقائق
    }
    send_email(email, otp)
    return jsonify({"success": True})

@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    """التحقق من OTP"""
    email = request.json.get("email")
    otp = request.json.get("otp")
    data = otp_store.get(email)

    if not data:
        return jsonify({"error": "No OTP"}), 400
    if time.time() > data["exp"]:
        return jsonify({"error": "Expired"}), 400
    if data["otp"] != hash_otp(otp):
        return jsonify({"error": "Wrong OTP"}), 400

    del otp_store[email]
    return jsonify({"success": True})

# ================================
# Main
# ================================
if __name__ == "__main__":
    app.run(debug=True)
