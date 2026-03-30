# mongo_db.py
from pymongo import MongoClient
import os

# إعداد الاتصال (تأكد من وضع URI الخاص بك في إعدادات Render)
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://ip8a2024_db_user:t5Qq8VSmpSHAOqca@cluster0.eqswpgj.mongodb.net")
client = MongoClient(MONGO_URI)
db = client['RedDiamondDB']

# المجموعات الأساسية
users_col = db['users']           # بيانات المستخدمين والأرصدة
transactions_col = db['transactions'] # سجل العمليات (غير قابل للتعديل)
referrals_col = db['referrals']   # سجل الإحالات
