import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

API_KEY = os.environ.get("API_KEY")  # خذ مفتاح EasyEmailAPI من Environment Variables

@app.route("/check-email", methods=["POST"])
def check_email():
    data = request.json
    email = data.get("email")
    if not email:
        return jsonify({"success": False, "message": "لم يتم إدخال البريد"}), 400

    url = f"https://easyemailapi.com/api/verify/{email}"
    headers = {"Authorization": f"Bearer {API_KEY}"}

    try:
        r = requests.get(url, headers=headers, timeout=10)
        result = r.json()

        if result.get("disposable"):
            return jsonify({"success": False, "message": "هذا بريد مؤقت ❌ الرجاء استخدام بريد حقيقي"})

        if result.get("score", 0) < 60:
            return jsonify({"success": False, "message": "موثوقية البريد ضعيفة ⚠️ الرجاء استخدام بريد آخر"})

        if not result.get("valid_mx", False):
            return jsonify({"success": False, "message": "خادم البريد غير صالح"})

        return jsonify({"success": True, "message": "الإيميل صالح ويمكن استخدامه ✅"})

    except requests.exceptions.RequestException:
        return jsonify({"success": False, "message": "فشل التحقق من البريد"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
