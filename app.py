from flask import Flask, request, jsonify
from flask_cors import CORS
import random, time, hashlib, smtplib, threading, os
from email.mime.text import MIMEText

app = Flask(__name__)
CORS(app)

# ================================
# إعداد Gmail (آمن)
# ================================
GMAIL_USER = "ip8f2024@gmail.com"
GMAIL_PASS = os.environ.get("GMAIL_PASS")

if not GMAIL_PASS:
    raise Exception("GMAIL_PASS not set in environment variables")

# ================================
# تخزين OTP + محاولات
# ================================
otp_store = {}
rate_limit = {}
try_limit = {}

# ================================
# دوال مساعدة
# ================================
def hash_otp(otp):
    return hashlib.sha256(otp.encode()).hexdigest()

def generate_otp():
    return str(random.randint(100000, 999999))

def send_email(to_email, otp):
    msg_content = f"""
    <html>
    <body style='font-family: Arial, sans-serif;'>
      <h2 style='color: #333;'>رمز التحقق (OTP)</h2>
      <p>لقد طلبت تسجيل الدخول باستخدام هذا الإيميل.</p>
      <h3 style='background: #f0f0f0; padding: 10px; border-radius: 6px;'>كودك هو:</h3>
      <h1 style='color: #007bff;'>{otp}</h1>
      <p>إذا لم تطلب هذا، فتجاهل هذه الرسالة.</p>
      <hr>
      <small>Powered by RedDiamond2</small>
    </body>
    </html>
    """

    try:
        msg = MIMEText(msg_content, "html")
        msg['Subject'] = "🔐 رمز التحقق الخاص بك (OTP)"
        msg['From'] = GMAIL_USER
        msg['To'] = to_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.send_message(msg)

        print(f"[OK] Sent to {to_email}")

    except Exception as e:
        print("[ERROR] Sending email:", e)

# ================================
# تنظيف الأكواد المنتهية
# ================================
def cleanup():
    now = time.time()
    for email in list(otp_store.keys()):
        if now > otp_store[email]["exp"]:
            del otp_store[email]
    threading.Timer(60, cleanup).start()

cleanup()

# ================================
# Routes
# ================================
@app.route("/ping")
def ping():
    return "pong"

# ================================
# إرسال OTP
# ================================
@app.route("/send-otp", methods=["POST"])
def send_otp():
    data = request.json
    email = data.get("email")
    ip = request.remote_addr

    if not email or "@" not in email:
        return jsonify({"error": "Invalid email"}), 400

    now = time.time()

    # Rate limit
    if email in rate_limit and now - rate_limit[email] < 30:
        return jsonify({"error": "Wait before retry"}), 429

    # Anti brute-force
    if email in try_limit and try_limit[email] >= 5:
        return jsonify({"error": "Too many attempts"}), 429

    rate_limit[email] = now
    try_limit[email] = try_limit.get(email, 0) + 1

    otp = generate_otp()

    otp_store[email] = {
        "otp": hash_otp(otp),
        "exp": now + 300,
        "ip": ip
    }

    threading.Thread(target=send_email, args=(email, otp), daemon=True).start()

    return jsonify({"success": True})

# ================================
# التحقق من OTP
# ================================
@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.json
    email = data.get("email")
    otp = data.get("otp")

    if not email or email not in otp_store:
        return jsonify({"error": "No OTP"}), 400

    record = otp_store[email]

    if time.time() > record["exp"]:
        del otp_store[email]
        return jsonify({"error": "Expired"}), 400

    if record["otp"] != hash_otp(otp):
        return jsonify({"error": "Wrong OTP"}), 400

    del otp_store[email]
    try_limit[email] = 0

    return jsonify({"success": True})

# ================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
