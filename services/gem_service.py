# gem_service.py
from datetime import datetime
from models.mongo_db import users_col, transactions_col

class GemService:
    
    @staticmethod
    def update_gems(email, amount, reason, transaction_type="credit"):
        """
        تحديث الرصيد وتسجيل العملية في خطوة واحدة آمنة.
        amount: القيمة (موجبة دائماً)
        transaction_type: 'credit' (إضافة) أو 'debit' (خصم)
        """
        # 1. تحديد قيمة التغيير (موجب للإضافة، سالب للخصم)
        change = amount if transaction_type == "credit" else -amount

        # 2. تحديث رصيد المستخدم في MongoDB (عملية ذرية آمنة)
        # نستخدم $gte: 0 للتأكد من أن الرصيد لن يصبح سالباً عند الخصم
        query = {"email": email}
        if transaction_type == "debit":
            query["gems"] = {"$gte": amount}

        result = users_col.update_one(
            query,
            {"$inc": {"gems": change}}
        )

        if result.modified_count > 0:
            # 3. تسجيل العملية في جدول الـ Transactions إذا نجح التحديث
            transactions_col.insert_one({
                "email": email,
                "amount": amount,
                "type": transaction_type,
                "reason": reason,
                "timestamp": datetime.utcnow()
            })
            return True, "Operation successful"
        
        return False, "Insufficient balance or user not found"

    @staticmethod
    def get_user_stats(email):
        """جلب الرصيد الحالي وآخر 10 عمليات"""
        user = users_col.find_one({"email": email}, {"_id": 0, "gems": 1, "referral_code": 1})
        if not user:
            return None
        
        history = list(transactions_col.find(
            {"email": email}, 
            {"_id": 0}
        ).sort("timestamp", -1).limit(10))
        
        return {
            "balance": user.get("gems", 0),
            "referral_code": user.get("referral_code", ""),
            "history": history
        }

    @staticmethod
    def handle_profile_reward(email, field):
        """منح مكافأة (20 جوهرة) لإكمال معلومة في البروفايل"""
        user = users_col.find_one({"email": email})
        
        # التأكد أن المستخدم لم يأخذ المكافأة مسبقاً لهذه المعلومة
        if not user or user.get("profile_rewards", {}).get(field):
            return False, "Reward already claimed or user not found"

        # منح المكافأة وتحديث حالة المكافآت
        success, msg = GemService.update_gems(email, 20, f"Profile Completion: {field}", "credit")
        if success:
            users_col.update_one(
                {"email": email},
                {"$set": {f"profile_rewards.{field}": True}}
            )
        return success, msg
