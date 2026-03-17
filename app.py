from flask import Flask, request, jsonify
from flask_cors import CORS
import random, time, smtplib, hashlib
from email.mime.text import MIMEText

app = Flask(__name__)
CORS(app)

otp_store = {}

EMAIL = "ip8a2024@gmail.com"
PASSWORD = "lfyr mkds gioy ltlu"

def hash_otp(otp):
    return hashlib.sha256(otp.encode()).hexdigest()

def send_email(to_email, otp):
    msg = MIMEText(f"Your OTP is: {otp}")
    msg["Subject"] = "Your Login Code"
    msg["From"] = EMAIL
    msg["To"] = to_email

    server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    server.login(EMAIL, PASSWORD)
    server.send_message(msg)
    server.quit()

@app.route("/send-otp", methods=["POST"])
def send_otp():
    email = request.json.get("email")

    otp = str(random.randint(100000, 999999))

    otp_store[email] = {
        "otp": hash_otp(otp),
        "exp": time.time() + 300
    }

    send_email(email, otp)

    return jsonify({"success": True})

@app.route("/verify-otp", methods=["POST"])
def verify_otp():
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
