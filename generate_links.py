import hmac
import hashlib
import base64
import json
import time
from urllib.parse import quote

# الإعدادات الأمنية - غير هذا المفتاح في الإنتاج
SECRET_KEY = "RED_DIAMOND_SECURE_KEY_2026_X99"
BASE_URL = "https://RedDiamond2.github.io/welcome.html"

def generate_secure_link(ref, service, track, days_valid=30):
    """توليد رابط مشفر لا يمكن التلاعب به"""
    
    # 1. تجهيز البيانات (Payload)
    # نستخدم اختصارات لتقليل طول الرابط
    expiry = int(time.time()) + (days_valid * 86400)
    payload_dict = {
        "r": ref,      # ref
        "s": service,  # service
        "t": track,    # track
        "e": expiry    # expiry date
    }
    
    # 2. تحويل البيانات إلى Base64
    payload_json = json.dumps(payload_dict, separators=(',', ':'))
    payload_encoded = base64.urlsafe_b64encode(payload_json.encode()).decode().rstrip("=")
    
    # 3. إنشاء التوقيع الرقمي (Signature) باستخدام HMAC-SHA256
    signature = hmac.new(
        SECRET_KEY.encode(),
        payload_encoded.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # 4. الرابط النهائي
    return f"{BASE_URL}?data={payload_encoded}&sig={signature}"

# --- توليد الروابط التي طلبتها بنظام الحماية الجديد ---
links_to_generate = [
    ("email", "trial", "678678"),
    ("reddit", "premium", "789789"),
    ("direct", "basic", "890890"),
    ("telegram", "premium", "147258"),
    ("facebook", "basic", "258369"),
    ("twitter", "trial", "369147"),
    ("linkedin", "premium", "963852")
]

print("=== RedDiamond2 Secure Links Generator ===")
for ref, svc, trk in links_to_generate:
    secure_link = generate_secure_link(ref, svc, trk)
    print(f"[{ref.upper()}]: {secure_link}\n")
