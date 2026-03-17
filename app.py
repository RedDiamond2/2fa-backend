from flask import Flask, request, jsonify
from flask_cors import CORS
import random, time, smtplib, hashlib
from email.mime.text import MIMEText

app = Flask(__name__)
CORS(app)

# تخزين مؤقت (في الإنتاج استعمل Redis أو DB)
otp_store = {}
rate_limit = {}

# ✏️ عدل هذه البيانات
EMAIL = "ip8a2024@gmail.com"
PASSWORD = "lfyr mkds gioy ltlu"


# 🔐 توليد OTP
def generate_otp():
    return str(random.randint(100000, 999999))


# 🔐 تشفير OTP
def hash_otp(otp):
    return hashlib.sha256(otp.encode()).hexdigest()


# 📧 إرسال الإيميل
def send_email(to_email, otp):
    try:
        msg = MIMEText(f"Your OTP code is: {otp}\nValid for 5 minutes.")
        msg["Subject"] = "Your 2FA Code"
        msg["From"] = EMAIL
        msg["To"] = to_email

        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL, PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print("Email Error:", e)
        return False


# 🟢 اختبار السيرفر
@app.route("/")
def home():
    return "2FA API Working ✅"


# 🚀 إرسال OTP
@app.route("/send-otp", methods=["POST"])
def send_otp():
    data = request.json
    email = data.get("email")
    ip = request.remote_addr

    if not email:
        return jsonify({"error": "Email required"}), 400

    # 🔒 Rate limit (كل 60 ثانية)
    last_request = rate_limit.get(ip, 0)
    if time.time() - last_request < 60:
        return jsonify({"error": "Too many requests"}), 429

    rate_limit[ip] = time.time()

    otp = generate_otp()

    otp_store[email] = {
        "otp": hash_otp(otp),
        "exp": time.time() + 300,  # 5 دقائق
        "attempts": 0
    }

    if not send_email(email, otp):
        return jsonify({"error": "Failed to send email"}), 500

    return jsonify({"success": True})


# 🔍 التحقق من OTP
@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.json
    email = data.get("email")
    otp = data.get("otp")

    record = otp_store.get(email)

    if not record:
        return jsonify({"error": "No OTP found"}), 400

    # ⏰ انتهت الصلاحية
    if time.time() > record["exp"]:
        del otp_store[email]
        return jsonify({"error": "OTP expired"}), 400

    # 🔒 عدد المحاولات
    record["attempts"] += 1
    if record["attempts"] > 5:
        del otp_store[email]
        return jsonify({"error": "Too many attempts"}), 403

    # ❌ كود خاطئ
    if record["otp"] != hash_otp(otp):
        return jsonify({"error": "Invalid OTP"}), 400

    # ✅ نجاح
    del otp_store[email]

    return jsonify({
        "success": True,
        "message": "Authentication successful"
    })


# 🚀 تشغيل السيرفر
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
