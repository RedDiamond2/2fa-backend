import os
import hmac
import hashlib
import base64
import json
import time
import requests

from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient

# =======================
# Blueprints
# =======================

from collect import collect_api
from google_oauth import google_api
from UnicCode import handle_unic_code_request

# =======================
# إنشاء التطبيق
# =======================

app = Flask(__name__)

CORS(app, resources={r"/*": {
    "origins": "*",
    "methods": ["GET","POST","OPTIONS"],
    "allow_headers": ["Content-Type","Authorization"]
}})

# =======================
# Environment Variables
# =======================

API_KEY = os.environ.get("API_KEY")
MONGO_URI = os.environ.get("MONGO_URI")
SECRET_KEY = os.environ.get("LINK_SECRET_KEY", "RED_DIAMOND_SECURE_KEY_2026_X99")

# =======================
# MongoDB
# =======================

client = MongoClient(MONGO_URI)
db = client.red_diamond
collection = db.fingerprints

# =======================
# Register Blueprints
# =======================

app.register_blueprint(google_api)
app.register_blueprint(collect_api)

# =======================
# Email Providers
# =======================

ALLOWED_DOMAINS = [
"gmail.com","yahoo.com","outlook.com","hotmail.com","protonmail.com","icloud.com",
"zoho.com","aol.com","gmx.com","mail.com","yandex.com","fastmail.com","tutanota.com",
"inbox.com","hushmail.com","mail.ru","lycos.com","rambler.ru","posteo.de","runbox.com",
"gmx.net","rediffmail.com","excite.com","mailfence.com","luxsci.com","lavabit.com",
"countermail.com","startmail.com","openmailbox.org","postfixmail.com","kolabnow.com",
"neomailbox.com","vfemail.net","safe-mail.net","migadu.com","disroot.org","thexyz.com",
"ipage.com","godaddy.com","bluehost.com","dreamhost.com","mailbox.org","netcourrier.com",
"seznam.cz","web.de","terra.com","zoho.workplace","fastmail.business"
]

# =======================
# Translations
# =======================

translations = {

"ar":{
"no_email":"لم يتم إدخال البريد",
"unsupported":"هذا البريد غير مدعوم ❌",
"disposable":"هذا بريد مؤقت ❌ الرجاء استخدام بريد حقيقي",
"low_score":"موثوقية البريد ضعيفة ⚠️",
"invalid_mx":"خادم البريد غير صالح",
"valid":"الإيميل صالح ويمكن استخدامه ✅",
"fail":"فشل التحقق من البريد",
"link_invalid":"رابط غير صالح أو تم التلاعب به ❌",
"link_expired":"هذا الرابط انتهت صلاحيته ⏰"
},

"en":{
"no_email":"No email provided",
"unsupported":"This email is not supported ❌",
"disposable":"Disposable email ❌",
"low_score":"Email reliability is low ⚠️",
"invalid_mx":"Invalid email server",
"valid":"Email is valid ✅",
"fail":"Email verification failed",
"link_invalid":"Invalid link ❌",
"link_expired":"Link expired ⏰"
},

"fr":{
"no_email":"Aucun email fourni",
"unsupported":"Email non supporté ❌",
"disposable":"Email temporaire ❌",
"low_score":"Fiabilité faible ⚠️",
"invalid_mx":"Serveur email invalide",
"valid":"Email valide ✅",
"fail":"Échec de vérification",
"link_invalid":"Lien invalide ❌",
"link_expired":"Lien expiré ⏰"
}

}

# =======================
# Get Real IP
# =======================

def get_real_ip():

    if request.headers.get("CF-Connecting-IP"):
        return request.headers.get("CF-Connecting-IP")

    if request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()

    return request.remote_addr


# =======================
# Generate Unique Code
# =======================

@app.route('/generate-unic', methods=['POST','OPTIONS'])
def generate_unic():

    if request.method == "OPTIONS":
        return jsonify({"status":"ok"}),200

    data = request.json
    return handle_unic_code_request(data, db)


# =======================
# Verify Secure Link
# =======================

@app.route("/verify-link", methods=["POST"])
def verify_link():

    input_data = request.json
    payload_encoded = input_data.get("data")
    provided_sig = input_data.get("sig")
    lang = input_data.get("lang","ar")

    t = translations.get(lang, translations["ar"])

    if not payload_encoded or not provided_sig:
        return jsonify({"valid":False,"message":t["link_invalid"]}),400

    expected_sig = hmac.new(
        SECRET_KEY.encode(),
        payload_encoded.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, provided_sig):
        return jsonify({"valid":False,"message":t["link_invalid"]}),403

    try:

        missing_padding = len(payload_encoded) % 4
        if missing_padding:
            payload_encoded += '='*(4-missing_padding)

        decoded_bytes = base64.urlsafe_b64decode(payload_encoded)

        payload = json.loads(decoded_bytes)

        if int(time.time()) > payload.get("e",0):
            return jsonify({"valid":False,"message":t["link_expired"]}),403

        return jsonify({"valid":True,"payload":payload})

    except Exception as e:

        print("Decode error:",e)

        return jsonify({"valid":False,"message":t["link_invalid"]}),400


# =======================
# Email Verification
# =======================

@app.route("/check-email", methods=["POST"])
def check_email():

    data = request.json
    email = data.get("email")
    lang = data.get("lang","ar")

    t = translations.get(lang, translations["ar"])

    if not email:
        return jsonify({"success":False,"message":t["no_email"]}),400

    domain = email.split("@")[-1].lower()

    if domain not in ALLOWED_DOMAINS:
        return jsonify({"success":False,"message":t["unsupported"]}),400

    url = f"https://easyemailapi.com/api/verify/{email}"

    headers={"Authorization":f"Bearer {API_KEY}"}

    try:

        r=requests.get(url,headers=headers,timeout=10)

        result=r.json()

        if result.get("disposable"):
            return jsonify({"success":False,"message":t["disposable"]})

        if result.get("score",0) < 60:
            return jsonify({"success":False,"message":t["low_score"]})

        if not result.get("valid_mx",False):
            return jsonify({"success":False,"message":t["invalid_mx"]})

        return jsonify({"success":True,"message":t["valid"]})

    except Exception as e:

        print("Email API error:",e)

        return jsonify({"success":False,"message":t["fail"]}),500


# =======================
# Country Detection
# =======================

@app.route("/country", methods=["GET"])
def detect_country():

    try:

        ip = get_real_ip()

        r = requests.get(f"https://ipwho.is/{ip}", timeout=5)

        data = r.json()

        if data.get("success"):

            return jsonify({
                "ip":ip,
                "country":data.get("country_code","DZ")
            })

    except Exception as e:

        print("Country error:",e)

    return jsonify({"ip":get_real_ip(),"country":"DZ"})


# =======================
# Geo Location
# =======================

@app.route("/geo", methods=["GET"])
def geo_info():

    ip = get_real_ip()

    try:

        r = requests.get(
        f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,query",
        timeout=5
        )

        return jsonify(r.json())

    except Exception:

        return jsonify({
        "status":"fail",
        "query":ip
        })


# =======================
# Fingerprints Viewer
# =======================

@app.route("/fingerprints", methods=["GET"])
def list_fingerprints():

    records=list(

    collection
    .find({},{"_id":0})
    .sort("timestamp",-1)
    .limit(100)

    )

    return jsonify(records)


# =======================
# Health Check
# =======================

@app.route("/health")
def health():

    return "OK",200


# =======================
# Run Server
# =======================

if __name__=="__main__":

    port=int(os.environ.get("PORT",5000))

    app.run(host="0.0.0.0",port=port)
