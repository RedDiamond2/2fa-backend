# google_oauth.py - Production Version 3.0 (Ultimate)
# الوصف: المسؤول عن تبادل كود جوجل، إدارة جلسة المستخدم، ومزامنة البيانات مع المونغو دي بي.

import os
import requests
import time
import datetime
import uuid
from flask import Blueprint, request, jsonify
from models.mongo_db import users_col, gems_col, transactions_col
from services.auth_service import generate_token
from config import Config

google_api = Blueprint("google_api", __name__)

# --- إعدادات البيئة (تُجلب من Render Environment Variables) ---
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
# تأكد أن هذا الرابط مطابق تماماً لإعدادات Google Console
REDIRECT_URI = os.environ.get("REDIRECT_URI", "https://reddiamond2.github.io/oauth-callback.html")

@google_api.route("/google-token", methods=["POST"])
def google_token():
    """
    النقطة المركزية: تبادل كود جوجل -> جلب بيانات المستخدم -> 
    تحديث قاعدة البيانات -> إصدار توكن Red Diamond.
    """
    data = request.get_json()
    code = data.get("code")
    # استقبال بيانات إضافية إذا وجدت (مثل الهاتف من خطوات سابقة)
    phone_from_client = data.get("phone")

    if not code:
        return jsonify({"success": False, "error": "Authorization code is missing"}), 400

    # 1. تبادل الكود (Authorization Code) بالتوكنات من جوجل
    token_url = "https://oauth2.googleapis.com/token"
    token_payload = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }

    try:
        # طلب التوكن من سيرفرات جوجل
        token_res = requests.post(token_url, data=token_payload, timeout=10)
        token_json = token_res.json()

        if "error" in token_json:
            return jsonify({
                "success": False, 
                "error": "Google Exchange Failed", 
                "details": token_json.get("error_description")
            }), 400

        google_access_token = token_json.get("access_token")
        google_refresh_token = token_json.get("refresh_token")
        
        # 2. جلب بيانات هوية المستخدم الشخصية من جوجل
        user_info_res = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {google_access_token}"},
            timeout=10
        )
        user_info = user_info_res.json()
        
        user_email = user_info.get("email")
        if not user_email:
            return jsonify({"success": False, "error": "Email not provided by Google"}), 400

        # 3. إدارة المستخدم في قاعدة البيانات (Persistence Logic)
        now = datetime.datetime.utcnow()
        
        # تحديث بيانات المستخدم أو إنشاؤه إذا لم يوجد (Upsert)
        users_col.update_one(
            {"email": user_email},
            {"$set": {
                "name": user_info.get("name"),
                "photo": user_info.get("picture"),
                "last_login": now,
                "is_active": True
            }, "$setOnInsert": {
                "created_at": now,
                "phone": phone_from_client,
                "provider": "google"
            }},
            upsert=True
        )

        # التأكد من وجود محفظة جواهر للمستخدم (ترحيب خاص)
        gem_wallet = gems_col.find_one({"email": user_email})
        if not gem_wallet:
            new_ref_code = str(uuid.uuid4())[:8].upper()
            gems_col.insert_one({
                "email": user_email,
                "balance": 50, # رصيد ترحيبي 50 جوهرة
                "referral_code": new_ref_code,
                "created_at": now,
                "history": []
            })
            # تسجيل عملية الإضافة في السجل
            transactions_col.insert_one({
                "email": user_email,
                "amount": 50,
                "type": "credit",
                "reason": "Welcome Gift via Google Login 💎",
                "timestamp": now
            })

        # 4. إصدار توكن النظام الخاص بنا (JWT) لفك التشفير في auth_guard.py
        # هذا السطر هو الذي يمنع خطأ 401 Unauthorized مستقبلاً
        local_rd_token = generate_token(user_email)

        # 5. الرد النهائي المتوافق مع فرونت إند Red Diamond
        return jsonify({
            "success": True,
            "token": local_rd_token, # التوكن المطلوب للعمليات اللاحقة
            "google_access_token": google_access_token, # للعمليات الخاصة بجوجل مستقبلاً
            "user": {
                "name": user_info.get("name"),
                "email": user_email,
                "picture": user_info.get("picture")
            },
            "server_time": now.isoformat()
        }), 200

    except requests.exceptions.RequestException as e:
        print(f"❌ Network Error (Google OAuth): {str(e)}")
        return jsonify({"success": False, "error": "Connection to Google failed"}), 503
    except Exception as e:
        print(f"❌ Critical Internal Error: {str(e)}")
        return jsonify({"success": False, "error": "Authentication processing failed"}), 500