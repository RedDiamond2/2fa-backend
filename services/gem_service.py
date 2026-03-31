# services/gem_service.py
# Red Diamond Project - Production Version 2026
# الوصف: العقل الحسابي لإدارة الجواهر، الإحالات، وسجل العمليات المالي.

from datetime import datetime
from models.mongo_db import users_col, transactions_col, gems_col

class GemService:
    """
    خدمة إدارة الجواهر المركزية.
    تعتمد هذه الخدمة مسمى 'balance' لتمثيل رصيد المستخدم لضمان التوافق مع الواجهة الأمامية.
    """

    @staticmethod
    def update_gems(email, amount, reason, transaction_type="credit"):
        """
        تحديث الرصيد وتسجيل العملية في خطوة واحدة آمنة (Atomic Operation).
        
        :param email: البريد الإلكتروني للمستخدم.
        :param amount: قيمة الجواهر (يجب أن تكون موجبة).
        :param reason: سبب العملية (يظهر في سجل العمليات).
        :param transaction_type: 'credit' للإضافة، 'debit' للخصم.
        :return: (bool, str) نجاح العملية ورسالة الحالة.
        """
        # 1. تحديد قيمة التغيير (موجب للإضافة، سالب للخصم)
        change = amount if transaction_type == "credit" else -amount

        # 2. بناء الاستعلام (Query)
        # في حالة الخصم، نتحقق أن الرصيد الحالي أكبر من أو يساوي القيمة المطلوبة لمنع الرصيد السالب
        query = {"email": email}
        if transaction_type == "debit":
            query["balance"] = {"$gte": amount}

        try:
            # 3. تحديث الرصيد في مجموعة الجواهر (gems_col)
            # ملاحظة: نستخدم 'balance' بناءً على طلبك لتوحيد المسميات
            result = gems_col.update_one(
                query,
                {"$inc": {"balance": change}}
            )

            if result.modified_count > 0:
                # 4. تسجيل العملية في جدول الـ Transactions لضمان الأرشفة المالية
                transactions_col.insert_one({
                    "email": email,
                    "amount": amount,
                    "type": transaction_type,
                    "reason": reason,
                    "timestamp": datetime.utcnow()
                })
                return True, "Balance updated successfully"
            
            return False, "Insufficient balance or user record not found"

        except Exception as e:
            print(f"❌ Critical Error in update_gems: {str(e)}")
            return False, "Internal database error"

    @staticmethod
    def get_user_stats(email):
        """
        جلب الرصيد الحالي، كود الإحالة، وآخر 10 عمليات مالية للمستخدم.
        يستخدم هذا التابع لتغذية صفحة البروفايل بالبيانات.
        """
        try:
            # جلب بيانات الجواهر (الرصيد وكود الإحالة)
            user_gems = gems_col.find_one(
                {"email": email}, 
                {"_id": 0, "balance": 1, "referral_code": 1}
            )
            
            if not user_gems:
                return None
            
            # جلب آخر 10 عمليات مرتبة من الأحدث إلى الأقدم
            history = list(transactions_col.find(
                {"email": email}, 
                {"_id": 0}
            ).sort("timestamp", -1).limit(10))
            
            return {
                "balance": user_gems.get("balance", 0),
                "referral_code": user_gems.get("referral_code", ""),
                "history": history
            }
        except Exception as e:
            print(f"❌ Error fetching user stats: {str(e)}")
            return None

    @staticmethod
    def handle_profile_reward(email, field):
        """
        منح مكافأة (مثلاً 20 جوهرة) عند إكمال المستخدم لبيانات معينة في البروفايل.
        تمنع هذه الوظيفة تكرار الحصول على المكافأة لنفس الحقل.
        """
        try:
            # التحقق من أن المستخدم لم يحصل على المكافأة مسبقاً لهذا الحقل
            user_data = users_col.find_one({"email": email})
            
            if not user_data:
                return False, "User not found"

            # التحقق داخل قاموس profile_rewards في وثيقة المستخدم
            rewards_status = user_data.get("profile_rewards", {})
            if rewards_status.get(field):
                return False, "Reward already claimed for this task"

            # 1. منح المكافأة (20 جوهرة كمثال)
            reward_amount = 20
            success, msg = GemService.update_gems(
                email, 
                reward_amount, 
                f"Task Completed: {field.replace('_', ' ').title()} 🏆", 
                "credit"
            )

            if success:
                # 2. تحديث حالة المهام في سجل المستخدم لمنع التكرار مستقبلاً
                users_col.update_one(
                    {"email": email},
                    {"$set": {f"profile_rewards.{field}": True}}
                )
                return True, f"Congratulations! You earned {reward_amount} Gems"
            
            return False, "Failed to apply reward"

        except Exception as e:
            print(f"❌ Error in handle_profile_reward: {str(e)}")
            return False, "Error processing reward"

    @staticmethod
    def process_referral(referrer_code, new_user_email):
        """
        معالجة عملية الإحالة عند استخدام كود صديق.
        يتم منح المحيل (صاحب الكود) مكافأة.
        """
        try:
            # البحث عن صاحب الكود
            referrer = gems_col.find_one({"referral_code": referrer_code})
            
            if not referrer:
                return False, "Invalid referral code"
            
            if referrer['email'] == new_user_email:
                return False, "You cannot use your own referral code"

            # منح صاحب الكود 30 جوهرة
            bonus_amount = 30
            success, msg = GemService.update_gems(
                referrer['email'],
                bonus_amount,
                f"Referral Bonus (New Friend: {new_user_email}) 💎",
                "credit"
            )
            
            return success, msg
        except Exception as e:
            print(f"❌ Referral processing error: {str(e)}")
            return False, "Referral failed"