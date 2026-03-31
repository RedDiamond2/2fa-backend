# services/mail_service.py
import requests
import os
from config import Config

class MailService:
    """
    خدمة إرسال البريد الإلكتروني باستخدام EasyEmailAPI.
    تعتمد على المفاتيح المعرفة في config.py
    """
    
    API_URL = "https://api.easyemailapi.com/v1/send" # تأكد من رابط الـ API الخاص بالخدمة
    API_KEY = Config.EMAIL_API_KEY or os.environ.get("API_KEY")

    @staticmethod
    def send_welcome_email(user_email, user_name):
        """إرسال رسالة ترحيبية للمستخدمين الجدد"""
        subject = "Welcome to Red Diamond! 💎"
        body = f"""
        Hi {user_name},
        
        Welcome to Red Diamond! We've added 50 Gems to your account as a welcome gift.
        Start sharing your referral code to earn more.
        
        Best regards,
        Red Diamond Team
        """
        return MailService._execute_send(user_email, subject, body)

    @staticmethod
    def send_otp_email(user_email, otp_code):
        """إرسال كود التحقق (OTP)"""
        subject = "Your Red Diamond Access Code"
        body = f"Your verification code is: {otp_code}. Do not share this code with anyone."
        return MailService._execute_send(user_email, subject, body)

    @staticmethod
    def _execute_send(to_email, subject, body):
        """الوظيفة الداخلية لتنفيذ طلب الـ HTTP"""
        if not MailService.API_KEY:
            print("❌ Mail Error: API_KEY is missing!")
            return False

        payload = {
            "api_key": MailService.API_KEY,
            "to": to_email,
            "subject": subject,
            "body": body
        }

        try:
            # نستخدم timeout لضمان عدم تعليق السيرفر إذا كانت خدمة البريد بطيئة
            response = requests.post(MailService.API_URL, json=payload, timeout=10)
            
            if response.status_code == 200:
                print(f"📧 Email sent successfully to {to_email}")
                return True
            else:
                print(f"❌ Mail API Error: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Mail Connection Error: {str(e)}")
            return False