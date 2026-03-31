# config.py
import os
from datetime import timedelta

class Config:
    """
    الإعدادات المركزية لتطبيق Red Diamond v2.0
    يتم جلب القيم من متغيرات البيئة (Environment Variables) في Render.
    """
    
    # --- إعدادات قاعدة البيانات ---
    MONGO_URI = os.environ.get("MONGO_URI")
    DB_NAME = "red_diamond"

    # --- مفاتيح الأمان والتشفير ---
    # المفتاح الأساسي لتشفير جلسات Flask
    SECRET_KEY = os.environ.get("APP_SECRET_KEY", "RD_SUPER_SECRET_2026_JWT_KEY")
    
    # المفتاح المستخدم لتوقيع روابط الجواهر والـ HMAC
    LINK_SECRET_KEY = os.environ.get("LINK_SECRET_KEY", "RED_DIAMOND_SECURE_KEY_2026_X99")
    
    # --- إعدادات توكن المصادقة (JWT) ---
    # مدة صلاحية التوكن قبل أن يحتاج المستخدم لتسجيل الدخول مرة أخرى
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=7)
    JWT_ALGORITHM = "HS256"

    # --- تكامل الخدمات الخارجية ---
    # مفتاح EasyEmailAPI للتحقق من البريد
    EMAIL_API_KEY = os.environ.get("API_KEY")
    
    # --- إعدادات السيرفر والـ CORS ---
    PORT = int(os.environ.get("PORT", 5000))
    DEBUG = True  # دائماً False في بيئة الإنتاج
    ALLOWED_ORIGINS = [
        "http://localhost:8000",
        "https://reddiamond2.github.io"
    ]

    # --- إعدادات الجواهر (Gems Logic) ---
    WELCOME_BONUS = 50
    REFERRAL_BONUS = 30
    PROFILE_COMPLETION_BONUS = 20

    @staticmethod
    def init_app(app):
        """وظيفة اختيارية لتنفيذ عمليات تهيئة إضافية عند تشغيل التطبيق"""
        pass

# نسخة من الإعدادات لاستخدامها مباشرة
config = Config()