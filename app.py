from flask import Flask, request, jsonify
from flask_cors import CORS
import random, time, hashlib, smtplib, threading
from email.mime.text import MIMEText

app = Flask(__name__)
CORS(app)

# ================================
# إعداد Gmail (⚠️ ضع بياناتك)
# ================================
GMAIL_USER = "ip8a2024@gmail.com"
GMAIL_PASS = "lfyr mkds gioy ltlu"

# ================================
# تخزين OTP
# ================================
otp_store = {}
rate_limit = {}

# ================================
# دوال مساعدة
# ================================
def hash_otp(otp):
    return hashlib.sha256(otp.encode()).hexdigest()

def generate_otp():
    return str(random.randint(100000, 999999))

def send_email(to_email, otp):
    try:
        msg = MIMEText(f"<h2>Your OTP is: {otp}</h2>", "html")
        msg['Subject'] = "Your OTP Code"
        msg['From'] = GMAIL_USER
        msg['To'] = to_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.send_message(msg)

        print(f"[OK] Sent to {to_email}")

    except Exception as e:
        print("[ERROR]", e)

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

@app.route("/send-otp", methods=["POST"])
def send_otp():
    data = request.json
    email = data.get("email")

    if not email or "@" not in email:
        return jsonify({"error": "Invalid email"}), 400

    # 🔥 Rate limit (30 ثانية)
    now = time.time()
    if email in rate_limit and now - rate_limit[email] < 30:
        return jsonify({"error": "Wait before retry"}), 429

    rate_limit[email] = now

    otp = generate_otp()

    otp_store[email] = {
        "otp": hash_otp(otp),
        "exp": now + 300
    }

    threading.Thread(target=send_email, args=(email, otp), daemon=True).start()

    return jsonify({"success": True})

@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.json
    email = data.get("email")
    otp = data.get("otp")

    if email not in otp_store:
        return jsonify({"error": "No OTP"}), 400

    record = otp_store[email]

    if time.time() > record["exp"]:
        del otp_store[email]
        return jsonify({"error": "Expired"}), 400

    if record["otp"] != hash_otp(otp):
        return jsonify({"error": "Wrong OTP"}), 400

    del otp_store[email]
    return jsonify({"success": True})

# ================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
