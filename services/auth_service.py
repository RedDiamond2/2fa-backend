# services/auth_service.py
import jwt
import datetime
import os
from flask import current_app

def get_secret_key():
    """
    جلب المفتاح السري بأمان:
    1. نبحث في متغيرات البيئة الخاصة بـ Render (LINK_SECRET_KEY).
    2. إذا لم يوجد، نبحث في إعدادات Flask (SECRET_KEY).
    3. كخيار أخير، نستخدم مفتاحاً افتراضياً (للتطوير المحلي فقط).
    """
    return os.getenv("LINK_SECRET_KEY") or \
           current_app.config.get('SECRET_KEY') or \
           "RD_SUPER_SECRET_2026_PROD_KEY"

def generate_token(user_email):
    """
    توليد توكن JWT مشفر للمستخدم.
    - الصلاحية: 24 ساعة من لحظة الإنشاء.
    - البيانات: يحتوي على البريد الإلكتروني (sub).
    """
    try:
        payload = {
            # وقت انتهاء الصلاحية: بعد 24 ساعة
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1),
            # وقت الإصدار: الآن
            'iat': datetime.datetime.utcnow(),
            # صاحب التوكن: البريد الإلكتروني
            'sub': str(user_email)
        }
        
        token = jwt.encode(
            payload,
            get_secret_key(),
            algorithm='HS256'
        )
        
        # التأكد من إعادة التوكن كـ string (في بعض إصدارات المكتبة القديمة)
        return token if isinstance(token, str) else token.decode('utf-8')
        
    except Exception as e:
        print(f"❌ Error generating token: {e}")
        return None

def decode_token(token):
    """
    فك تشفير التوكن والتحقق من صحته.
    - يعيد البريد الإلكتروني إذا كان التوكن صالحاً.
    - يعيد رسالة خطأ إذا كان منتهياً أو مزوراً.
    """
    try:
        # إزالة كلمة 'Bearer ' إذا كانت موجودة في التوكن المرسل
        if token.startswith('Bearer '):
            token = token.split(" ")[1]

        payload = jwt.decode(
            token, 
            get_secret_key(), 
            algorithms=['HS256']
        )
        
        return payload['sub']

    except jwt.ExpiredSignatureError:
        return "Signature expired. Please log in again."
    except jwt.InvalidTokenError:
        return "Invalid token. Please log in again."
    except Exception as e:
        return f"Authentication error: {str(e)}"

def verify_user_token(token):
    """
    دالة مساعدة سريعة للتحقق مما إذا كان التوكن يعيد إيميلاً صالحاً أم لا.
    """
    result = decode_token(token)
    if isinstance(result, str) and "@" in result:
        return True, result
    return False, result