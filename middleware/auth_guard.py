# middleware/auth_guard.py
import os
import jwt # تأكد من إضافة pyjwt في requirements.txt
from flask import request, jsonify
from functools import wraps

SECRET_KEY = os.environ.get("LINK_SECRET_KEY", "RED_DIAMOND_SECURE_KEY_2026_X99")

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # البحث عن التوكن في الـ Headers
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        if not token:
            return jsonify({'error': 'Token is missing!'}), 401

        try:
            # فك تشفير التوكن لاستخراج البريد الإلكتروني
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            current_user_email = data['email']
        except Exception as e:
            return jsonify({'error': 'Token is invalid or expired!'}), 401

        return f(current_user_email, *args, **kwargs)

    return decorated