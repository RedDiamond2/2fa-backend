import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from collect import collect_api

# إنشاء التطبيق
app = Flask(__name__)
CORS(app)

# تسجيل API جمع البيانات
app.register_blueprint(collect_api)

API_KEY = os.environ.get("API_KEY")  # ضع مفتاح EasyEmailAPI في Environment Variables


# أفضل 50 مزود بريد عالمي
ALLOWED_DOMAINS = [
    "yahoo.com","outlook.com","hotmail.com","protonmail.com","icloud.com",
    "zoho.com","aol.com","gmx.com","mail.com","yandex.com","fastmail.com","tutanota.com",
    "inbox.com","hushmail.com","mail.ru","lycos.com","rambler.ru","posteo.de","runbox.com",
    "gmx.net","rediffmail.com","excite.com","mailfence.com","luxsci.com","lavabit.com",
    "countermail.com","startmail.com","openmailbox.org","postfixmail.com","kolabnow.com",
    "neomailbox.com","vfemail.net","safe-mail.net","migadu.com","disroot.org","thexyz.com",
    "ipage.com","godaddy.com","bluehost.com","dreamhost.com","mailbox.org","netcourrier.com",
    "seznam.cz","web.de","terra.com","zoho.workplace","fastmail.business"
]


# الترجمات
translations = {

    "ar": {
        "no_email": "لم يتم إدخال البريد",
        "unsupported": "هذا البريد غير مدعوم ❌",
        "disposable": "هذا بريد مؤقت ❌ الرجاء استخدام بريد حقيقي",
        "low_score": "موثوقية البريد ضعيفة ⚠️ الرجاء استخدام بريد آخر",
        "invalid_mx": "خادم البريد غير صالح",
        "valid": "الإيميل صالح ويمكن استخدامه ✅",
        "fail": "فشل التحقق من البريد"
    },

    "en": {
        "no_email": "No email provided",
        "unsupported": "This email is not supported ❌",
        "disposable": "This is a disposable email ❌ Please use a real email",
        "low_score": "Email reliability is low ⚠️ Please use another email",
        "invalid_mx": "Invalid email server",
        "valid": "Email is valid ✅",
        "fail": "Failed to verify email"
    },

    "fr": {
        "no_email": "Aucun email fourni",
        "unsupported": "Cet email n'est pas pris en charge ❌",
        "disposable": "Ceci est un email temporaire ❌ Veuillez utiliser un email réel",
        "low_score": "Fiabilité de l'email faible ⚠️ Veuillez utiliser un autre email",
        "invalid_mx": "Serveur email invalide",
        "valid": "L'email est valide ✅",
        "fail": "Échec de la vérification de l'email"
    }
}


def get_translation(lang_code: str, key: str) -> str:
    return translations.get(lang_code, translations["ar"]).get(key, key)


@app.route("/check-email", methods=["POST"])
def check_email():

    data = request.json
    email = data.get("email")
    lang = data.get("lang", "ar")

    t = translations.get(lang, translations["ar"])

    if not email:
        return jsonify({
            "success": False,
            "message": t["no_email"]
        }), 400

    domain = email.split("@")[-1].lower()

    if domain not in ALLOWED_DOMAINS:
        return jsonify({
            "success": False,
            "message": t["unsupported"]
        }), 400

    url = f"https://easyemailapi.com/api/verify/{email}"

    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }

    try:

        r = requests.get(url, headers=headers, timeout=10)
        result = r.json()

        if result.get("disposable"):
            return jsonify({
                "success": False,
                "message": t["disposable"]
            })

        if result.get("score", 0) < 60:
            return jsonify({
                "success": False,
                "message": t["low_score"]
            })

        if not result.get("valid_mx", False):
            return jsonify({
                "success": False,
                "message": t["invalid_mx"]
            })

        return jsonify({
            "success": True,
            "message": t["valid"]
        })

    except requests.exceptions.RequestException:

        return jsonify({
            "success": False,
            "message": t["fail"]
        }), 500


# Keep Alive لمنع sleep في Render
@app.route("/health")
def health():
    return "OK", 200


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port
    )
