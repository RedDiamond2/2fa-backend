from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

API_TOKEN = "86|8oqIuj6JBVKxqFM8lm4zYUSNerhtr6n6b3bzOda28fb1f382"

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

        if result.get("valid"):
            return jsonify({
                "success": True,
                "email": email
            })

        return jsonify({
            "success": False,
            "error": "Email not valid"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(port=5000)
