# models/mongo_db.py
import os
from pymongo import MongoClient

# جلب رابط الاتصال من Environment Variables في Render
# القيمة الثانية هي للاختبار المحلي فقط إذا لم يجد المتغير
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://ip8a2024_db_user:t5Qq8VSmpSHAOqca@cluster0.eqswpgj.mongodb.net/red_diamond?retryWrites=true&w=majority")

try:
    # إنشاء الاتصال
    client = MongoClient(MONGO_URI)
    
    # اختيار قاعدة البيانات (سيتم استخدام 'red_diamond' من الرابط تلقائياً)
    db = client.get_database() 
    
    # تعريف المجموعات (Collections) - تأكد من مطابقة الأسماء لما نطلبه في الـ routes
    users_collection = db.get_collection("users")
    gems_collection = db.get_collection("gems")
    transactions_collection = db.get_collection("transactions")

    print("✅ Connected to MongoDB Atlas: red_diamond")

except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")
    # لمنع توقف السيرفر عن العمل (Crash) عند فشل الاتصال، نضع قيم افتراضية
    users_collection = None
    gems_collection = None
    transactions_collection = None