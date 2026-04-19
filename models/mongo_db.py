# models/mongo_db.py
import os
import sys
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, OperationFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv

# 1. تحميل متغيرات البيئة (مهم للتطوير المحلي، ويتم تجاهله في Render إذا كانت المتغيرات مسجلة هناك)
load_dotenv()

# 2. جلب رابط الاتصال من متغيرات البيئة (السرية هي الأولوية)
MONGO_URI = os.environ.get("MONGO_URI")

# التأكد من وجود الرابط قبل محاولة الاتصال
if not MONGO_URI:
    print("❌ CRITICAL ERROR: MONGO_URI is not set in environment variables.")
    sys.exit(1)

try:
    # 3. إنشاء اتصال آمن واحترافي (Industrial-Grade Configuration)
    # serverSelectionTimeoutMS: 5 ثوانٍ كحد أقصى للاتصال الأولي
    # maxPoolSize: 50 اتصال متزامن لضمان السرعة عند ضغط الزوار
    # retryWrites: إعادة محاولة الكتابة تلقائياً في حال فشل الشبكة البسيط
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000,
        maxPoolSize=50,
        retryWrites=True,
        connect=True
    )
    
    # التحقق الفوري من صحة الاتصال (Heartbeat Check)
    client.admin.command('ping')

    # 4. اختيار قاعدة البيانات
    # ملاحظة: تأكد أن اسم القاعدة في MongoDB Atlas هو 'red_diamond'
    db = client.get_database("red_diamond")
    
    # 5. تعريف المجموعات (Collections) بأسماء موحدة للـ Import
    # تم استخدام الأسماء المختصرة (users_col) لضمان توافقها مع ملفات routes و services
    users_col = db.get_collection("users")
    gems_col = db.get_collection("gems")
    transactions_col = db.get_collection("transactions")
    fingerprints_col = db.get_collection("fingerprints")

    # 6. تحسين الأداء والأمن عبر الفهارس (Indexing)
    # الفهارس تمنع تكرار البيانات وتجعل عمليات البحث فائقة السرعة
    print("⚙️ Initializing Database Indexes...")

    # منع تكرار البريد الإلكتروني
    users_col.create_index([("email", ASCENDING)], unique=True)
    
    # ربط الجواهر بالإيميل ومنع تكرار كود الإحالة
    gems_col.create_index([("email", ASCENDING)], unique=True)
    gems_col.create_index([("referral_code", ASCENDING)], unique=True)
    
    # فهرس مركب لتسريع جلب "آخر العمليات" للمستخدم (حسب الوقت تنازلياً)
    transactions_col.create_index([("email", ASCENDING), ("timestamp", -1)])
    
    # فهرس فريد للبصمة الرقمية لمنع تكرار بيانات الجهاز الواحد
    fingerprints_col.create_index([("device_id", ASCENDING)], unique=True)

    print("✅ MongoDB Atlas: Connected & Indexed Successfully.")

except ServerSelectionTimeoutError:
    print("❌ MongoDB Error: Connection Timeout. Check if your IP is whitelisted in Atlas.")
    # إرجاع None لتجنب انهيار التطبيق والسماح بمعالجة الخطأ برمجياً
    users_col = gems_col = transactions_col = fingerprints_col = None

except OperationFailure as e:
    print(f"❌ MongoDB Error: Authentication or Permission failed: {e}")
    users_col = gems_col = transactions_col = fingerprints_col = None

except Exception as e:
    print(f"❌ MongoDB Unexpected Error: {str(e)}")
    users_col = gems_col = transactions_col = fingerprints_col = None

# 7. التصدير الآمن (Exports)
# يتم استدعاء هذه المتغيرات في الملفات الأخرى هكذا:
# from models.mongo_db import users_col, gems_col