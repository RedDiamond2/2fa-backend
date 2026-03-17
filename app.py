from flask import Flask, request, jsonify
import random, time

app = Flask(__name__)

# تخزين OTP ووقت الانتهاء وعدد المحاولات
otp_store = {}        # email -> {"otp": str, "expires": timestamp}
attempts_store = {}   # email -> int
last_sent = {}        # email -> timestamp

OTP_EXPIRY = 300      # 5 دقائق
SEND_COOLDOWN = 60    # 1 دقيقة بين كل إرسال
MAX_ATTEMPTS = 5

def generate_otp():
    return str(random.randint(100000, 999999))

@app.route("/send-otp", methods=["POST"])
def send_otp():
    data = request.get_json()
    email = data.get("email")
    now = time.time()

    if not email:
        return jsonify({"success": False, "error": "Email required"}), 400

    # منع السبام
    if email in last_sent and now - last_sent[email] < SEND_COOLDOWN:
        wait = int(SEND_COOLDOWN - (now - last_sent[email]))
        return jsonify({"success": False, "error": f"Wait {wait}s before retry"}), 429

    code = generate_otp()
    otp_store[email] = {"otp": code, "expires": now + OTP_EXPIRY}
    attempts_store[email] = 0
    last_sent[email] = now

    # هنا مكان إرسال الإيميل الحقيقي، حالياً مجرد debug
    print(f"[DEBUG] OTP for {email}: {code}")

    return jsonify({"success": True})

@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json()
    email = data.get("email")
    otp = data.get("otp")
    now = time.time()

    if not email or not otp:
        return jsonify({"success": False, "error": "Email and OTP required"}), 400

    if email not in otp_store:
        return jsonify({"success": False, "error": "No OTP sent"}), 400

    if now > otp_store[email]["expires"]:
        del otp_store[email]
        return jsonify({"success": False, "error": "OTP expired"}), 400

    # عدد المحاولات
    attempts_store[email] += 1
    if attempts_store[email] > MAX_ATTEMPTS:
        return jsonify({"success": False, "error": "Too many attempts"}), 429

    if otp == otp_store[email]["otp"]:
        del otp_store[email]
        del attempts_store[email]
        return jsonify({"success": True})

    return jsonify({"success": False, "error": "Invalid OTP"}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
