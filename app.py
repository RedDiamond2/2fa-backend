import requests

RESEND_API_KEY = "re_4afPAkg6_8bkeMpmurKSGqcktpiQns1LZ"

def send_email(to_email, otp):
    try:
        print("Sending via RESEND API...")

        res = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "from": "onboarding@resend.dev",
                "to": [to_email],
                "subject": "Your OTP Code",
                "html": f"<h2>Your OTP is: {otp}</h2>"
            }
        )

        print("STATUS:", res.status_code)
        print("RESPONSE:", res.text)

    except Exception as e:
        print("EMAIL ERROR:", e)
        raise e
