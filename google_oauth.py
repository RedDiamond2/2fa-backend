import os
from flask import Blueprint, request, jsonify
import requests, time

google_api = Blueprint("google_api", __name__)

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = "https://RedDiamond2.github.io/oauth-callback.html"

@google_api.route("/google-token", methods=["POST"])
def google_token():
    data = request.get_json()
    code = data.get("code")
    phone = data.get("phone")
    email = data.get("email")

    if not code:
        return jsonify({"error":"No authorization code"}), 400

    token_res = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    })

    token_json = token_res.json()
    access_token = token_json.get("access_token")
    refresh_token = token_json.get("refresh_token")
    expires_in = token_json.get("expires_in")
    saved_at = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

    user_info = requests.get("https://www.googleapis.com/oauth2/v2/userinfo",
                             headers={"Authorization": f"Bearer {access_token}"})
    user_json = user_info.json()

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_in,
        "saved_at": saved_at,
        "user": user_json,
        "userPhone": phone
    })
