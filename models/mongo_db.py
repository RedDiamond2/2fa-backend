# models/mongo_db.py
import os
from pymongo import MongoClient

# جلب الرابط من Render (مع توفير قيمة احتياطية للـ Local)
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://ip8a2024_db_user:t5Qq8VSmpSHAOqca@cluster0.eqswpgj.mongodb.net/red_diamond?retryWrites=true&w=majority")

try:
    # إنشاء الاتصال مع مهلة زمنية (Timeout) لكي لا يعلق السيرفر طويلاً
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    
    # التأكد من الاتصال
    client.server_info() 

    # تحديد قاعدة البيانات صراحة لضمان الدقة
    db = client.get_database("red_diamond") 
    
    # تعريف المجموعات
    users_collection = db.get_collection("users")
    gems_collection = db.get_collection("gems")
    transactions_collection = db.get_collection("transactions")

    print("✅ Connected to MongoDB Atlas: red_diamond")

except Exception as e:
    print(f"❌ MongoDB Connection Error: {e}")
    # بدلاً من None، نتركها فارغة لتجنب أخطاء برمجية في الملفات الأخرى
    users_collection = None
    gems_collection = None
    transactions_collection = None