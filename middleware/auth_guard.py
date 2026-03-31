# middleware/auth_guard.py
import os
import jwt  # يجب أن يكون PyJWT مثبتًا في السيرفر
from flask import request, jsonify
from functools import wraps
from config import config

# استبدل السطر القديم بـ:

# جلب المفتاح السري من بيئة التشغيل (Render) لضمان أعلى مستويات الأمان
# ملاحظة: يجب أن يتطابق هذا المفتاح مع المفتاح المستخدم عند إنشاء التوكن في auth_service
# SECRET_KEY = os.environ.get("LINK_SECRET_KEY", "RED_DIAMOND_SECURE_KEY_2026_X99")
SECRET_KEY = config.LINK_SECRET_KEY

def token_required(f):
    """
    ميدل وير (Decorator) للتحقق من هوية المستخدم عبر JWT Token.
    يتم وضعه فوق المسارات التي تتطلب تسجيل دخول مثل جلب الجواهر أو تحديث البروفايل.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # 1. استخراج التوكن من ترويسة المصادقة (Authorization Header)
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            # التنسيق القياسي هو "Bearer <token>"
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        # 2. التحقق من وجود التوكن
        if not token:
            return jsonify({
                'status': 'fail',
                'message': 'Token is missing! Please login again.'
            }), 401

        try:
            # 3. فك تشفير التوكن والتحقق من صحته ومن تاريخ الانتهاء (exp) تلقائياً
            # نستخدم خوارزمية HS256 لضمان التوافق والأداء
            decoded_data = jwt.decode(
                token, 
                SECRET_KEY, 
                algorithms=["HS256"]
            )
            
            # استخراج البريد الإلكتروني (المعرف الأساسي للمستخدم في نظامنا)
            current_user_email = decoded_data.get('email')
            
            if not current_user_email:
                raise ValueError("Token does not contain user email.")

        except jwt.ExpiredSignatureError:
            # حالة انتهاء صلاحية التوكن (تحتاج لإعادة تسجيل دخول)
            return jsonify({
                'status': 'expired',
                'message': 'Your session has expired. Please log in again.'
            }), 401
            
        except jwt.InvalidTokenError:
            # حالة التلاعب بالتوكن أو استخدام توكن غير صالح
            return jsonify({
                'status': 'fail',
                'message': 'Invalid token. Access denied.'
            }), 401
            
        except Exception as e:
            # معالجة أي خطأ تقني آخر أثناء التحقق
            print(f"🔒 AuthGuard Security Alert: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': 'Authentication failed.'
            }), 401

        # 4. تمرير البريد الإلكتروني للمستخدم إلى الدالة الأصلية (الـ Route)
        return f(current_user_email, *args, **kwargs)

    return decorated