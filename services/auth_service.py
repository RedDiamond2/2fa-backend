# services/auth_service.py
import jwt
import datetime
from flask import current_app

def generate_token(user_email):
    """توليد توكن JWT صالح لمدة 24 ساعة"""
    try:
        payload = {
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1),
            'iat': datetime.datetime.utcnow(),
            'sub': user_email
        }
        # SECRET_KEY يجب أن يكون معرفاً في config.py
        return jwt.encode(
            payload,
            current_app.config.get('SECRET_KEY', 'RD_SUPER_SECRET_2026'),
            algorithm='HS256'
        )
    except Exception as e:
        return str(e)

def decode_token(token):
    """التحقق من صحة التوكن واستخراج الإيميل منه"""
    try:
        payload = jwt.decode(
            token, 
            current_app.config.get('SECRET_KEY', 'RD_SUPER_SECRET_2026'), 
            algorithms=['HS256']
        )
        return payload['sub']
    except jwt.ExpiredSignatureError:
        return 'Signature expired. Please log in again.'
    except jwt.InvalidTokenError:
        return 'Invalid token. Please log in again.'