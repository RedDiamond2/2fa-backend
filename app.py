from flask import Flask, request, jsonify
from flask_cors import CORS
import random, time, smtplib, hashlib, traceback
from email.mime.text import MIMEText

app = Flask(__name__)
CORS(app)

otp_store = {}

EMAIL = "ip8a2024@gmail.com"
PASSWORD = "lfyr mkds gioy ltlu"

def hash_otp(otp):
    return hashlib.sha256(otp.encode()).hexdigest()


def send_email(to_email, otp):
    try:
        print("=== START SENDING EMAIL ===")
        print("TO:", to_email)
        print("OTP:", otp)

        msg = MIMEText(f"Your OTP is: {otp}")
        msg["Subject"] = "Your Login Code"
        msg["From"] = EMAIL
        msg["To"] = to_email

        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.set_debuglevel(1)  # 👈 مهم: يظهر كل شيء
        server.login(EMAIL, PASSWORD)
        server.send_message(msg)
        server.quit()

        print("=== EMAIL SENT SUCCESS ===")

    except Exception as e:
        print("=== EMAIL ERROR ===")
        print(str(e))
        traceback.print_exc()
        raise e


@app.route("/")
def home():
    return "SERVER WORKING"


@app.route("/send-otp", methods=["POST"])
def send_otp():
    try:
        print("\n=== /send-otp CALLED ===")

        data = request.get_json()
        print("REQUEST DATA:", data)

        email = data.get("email")

        if not email:
            return jsonify({"error": "Email missing"}), 400

        otp = str(random.randint(100000, 999999))

        otp_store[email] = {
            "otp": hash_otp(otp),
            "exp": time.time() + 300
        }

        print("OTP GENERATED:", otp)

        send_email(email, otp)

        return jsonify({
            "success": True,
            "message": "OTP sent"
        })

    except Exception as e:
        print("=== ERROR IN /send-otp ===")
        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(e),
            "type": type(e).__name__
        }), 500


@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    try:
        print("\n=== /verify-otp CALLED ===")

        data = request.get_json()
        print("REQUEST DATA:", data)

        email = data.get("email")
        otp = data.get("otp")

        if not email or not otp:
            return jsonify({"error": "Missing fields"}), 400

        stored = otp_store.get(email)

        if not stored:
            return jsonify({"error": "No OTP found"}), 400

        if time.time() > stored["exp"]:
            return jsonify({"error": "OTP expired"}), 400

        if stored["otp"] != hash_otp(otp):
            return jsonify({"error": "Wrong OTP"}), 400

        del otp_store[email]

        return jsonify({
            "success": True,
            "message": "Login success"
        })

    except Exception as e:
        print("=== ERROR IN /verify-otp ===")
        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(e),
            "type": type(e).__name__
        }), 500


if __name__ == "__main__":
    app.run(debug=True)
