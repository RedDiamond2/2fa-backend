import os
from flask import Blueprint, request, jsonify
import requests
import time

google_api = Blueprint("google_api", __name__)

# تأكد من ضبط هذه المتغيرات في Render (Environment Variables)
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
# تأكد أن هذا الرابط مطابق تماماً لما هو مسجل في Google Console
REDIRECT_URI = "https://reddiamond2.github.io/oauth-callback.html"

@google_api.route("/google-token", methods=["POST"])
def google_token():
    data = request.get_json()
    code = data.get("code")
    phone = data.get("phone")
    email = data.get("email")

    if not code:
        return jsonify({"error": "No authorization code"}), 400

    # 1. تبادل الكود (Authorization Code) بالتوكنات الكاملة
    token_url = "https://oauth2.googleapis.com/token"
    token_payload = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }

    try:
        token_res = requests.post(token_url, data=token_payload)
        token_json = token_res.json()

        if "error" in token_json:
            return jsonify({"error": "Google Token Error", "details": token_json}), 400

        access_token = token_json.get("access_token")
        refresh_token = token_json.get("refresh_token") # سيصل هنا بفضل التعديل في app.js
        expires_in = token_json.get("expires_in")
        saved_at = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

        # 2. جلب بيانات المستخدم باستخدام الـ Access Token الجديد
        user_info_res = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user_json = user_info_res.json()

        # 3. الرد النهائي للمتصفح (سيتم حفظ هذه البيانات في LocalStorage ثم MongoDB)
        return jsonify({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in,
            "saved_at": saved_at,
            "user": {
                "name": user_json.get("name"),
                "email": user_json.get("email"),
                "picture": user_json.get("picture") # سيتم حفظه كـ userPhoto
            },
            "userPhone": phone
        })

    except Exception as e:
        print(f"Error in OAuth process: {str(e)}")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500
