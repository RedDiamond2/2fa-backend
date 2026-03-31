# models/mongo_db.py
# models/mongo_db.py
import os
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, OperationFailure

# 1. جلب رابط الاتصال من متغيرات البيئة (Render)
# ملاحظة: تأكد من إضافة MONGO_URI في إعدادات Render
MONGO_URI = os.environ.get("MONGO_URI")

try:
    # 2. إنشاء اتصال آمن مع إعدادات تحسين الأداء (Connection Pooling)
    # serverSelectionTimeoutMS: مهلة الانتظار قبل إعلان فشل الاتصال (5 ثوانٍ)
    # maxPoolSize: عدد الاتصالات المتزامنة المسموح بها لتحسين السرعة
    client = MongoClient(
        MONGO_URI, 
        serverSelectionTimeoutMS=5000,
        maxPoolSize=50,
        retryWrites=True
    )
    
    # التحقق الفوري من صحة الاتصال
    client.admin.command('ping')

    # 3. تحديد قاعدة البيانات (red_diamond)
    db = client.get_database("red_diamond")
    
    # 4. تعريف المجموعات (Collections)
    users_collection = db.get_collection("users")
    gems_collection = db.get_collection("gems")
    transactions_collection = db.get_collection("transactions")
    fingerprints_collection = db.get_collection("fingerprints")

    # 5. تحسين الأداء والأمان عبر الفهارس (Indexing)
    # هذه الخطوة تمنع إنشاء أكثر من حساب لنفس الإيميل وتسرع عملية البحث
    users_collection.create_index([("email", ASCENDING)], unique=True)
    gems_collection.create_index([("email", ASCENDING)], unique=True)
    gems_collection.create_index([("referral_code", ASCENDING)], unique=True)
    
    # فهرس لتسريع جلب سجل العمليات حسب الوقت
    transactions_collection.create_index([("email", ASCENDING), ("timestamp", -1)])
    
    # فهرس لمنع تكرار بيانات الأجهزة في نظام البصمة الرقمية
    fingerprints_collection.create_index([("device_id", ASCENDING)], unique=True)

    print("✅ MongoDB Atlas: Connected & Indexed Successfully.")

except ConnectionFailure:
    print("❌ MongoDB Error: Could not connect to the server (Timeout).")
    db = None
except OperationFailure as e:
    print(f"❌ MongoDB Error: Authentication or Permission failed: {e}")
    db = None
except Exception as e:
    print(f"❌ MongoDB Unexpected Error: {e}")
    db = None

# تصدير المجموعات لاستخدامها في الملفات الأخرى
# في حال فشل الاتصال، سيتم إرجاع None لتجنب انهيار التطبيق بالكامل
if db is None:
    users_collection = None
    gems_collection = None
    transactions_collection = None
    fingerprints_collection = None