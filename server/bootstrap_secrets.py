import os
import json
import tempfile

REQUIRED = [
    "PUBLIC_HOST",
    "CORS_ORIGINS", 
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "DATABASE_URL",
    "JWT_SECRET"
]

def ensure_env():
    """וודא שכל הסודות הנדרשים קיימים במערכת"""
    missing = [k for k in REQUIRED if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing required secrets: {', '.join(missing)}")

def ensure_google_creds_file():
    """המר JSON של Service Account לקובץ זמני עבור Google TTS"""
    sa_json = os.getenv("GOOGLE_TTS_SA_JSON")
    if not sa_json:
        print("⚠️ GOOGLE_TTS_SA_JSON not set - TTS will not work")
        return
    
    try:
        data = json.loads(sa_json)  # יזרוק אם לא JSON תקין
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(data, tmp)
        tmp.flush()
        tmp.close()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name
        print(f"✅ Google credentials file created: {tmp.name}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid GOOGLE_TTS_SA_JSON format: {e}")