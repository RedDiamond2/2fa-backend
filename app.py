from flask import Flask, request, jsonify
from flask_cors import CORS
import random, time, hashlib
import requests

app = Flask(__name__)
CORS(app)

otp_store = {}

RESEND_API_KEY = "re_Q1ohZ7ic_PNgnrB8nuLd7fBniA5xF5Kd8"  # ضع مفتاحك هنا

def hash_otp(otp):
    return hashlib.sha256(otp.encode()).hexdigest()

def send_email(to_email, otp):
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

if __name__ == "__main__":
    app.run(debug=True)
