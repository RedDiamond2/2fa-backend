from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

# ضع التوكن في Environment Variable في Render
API_TOKEN = os.getenv("EMAIL_API_TOKEN")


@app.route("/")
def home():
    return "Email verification API running"


@app.route("/check-email", methods=["POST"])
def check_email():

    data = request.json
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email required"}), 400

    try:

        r = requests.get(
            "https://easyemailapi.com/api/v1/verify",
            params={"email": email},
            headers={"Authorization": f"Bearer {API_TOKEN}"}
        )

        result = r.json()

        # النتيجة من API
        if result.get("valid") == True:

            return jsonify({
                "success": True,
                "email": email,
                "message": "Email exists"
            })

        return jsonify({
            "success": False,
            "error": "Email not valid"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
