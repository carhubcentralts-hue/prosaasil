import os
import json
import tempfile

REQUIRED = [
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "DATABASE_URL"
]

OPTIONAL_WITH_DEFAULTS = {
    "PUBLIC_HOST": "https://f6bc9e3d-e344-4c65-83e9-6679c9c65e69-00-30jsasmqh67fq.picard.replit.dev",
    "CORS_ORIGINS": "https://f6bc9e3d-e344-4c65-83e9-6679c9c65e69-00-30jsasmqh67fq.picard.replit.dev",
    "JWT_SECRET": "dev-jwt-secret-change-in-production"
}

def ensure_env():
    """וודא שכל הסודות הנדרשים קיימים במערכת - עם defaults לפיתוח"""
    # בדיקת סודות חובה
    missing = [k for k in REQUIRED if not os.getenv(k)]
    if missing:
        print(f"⚠️  Warning: Missing required secrets: {', '.join(missing)}")
        print("🔧 For production, set these in Replit Secrets")
    
    # הגדרת defaults לסודות אופציונליים
    for key, default_value in OPTIONAL_WITH_DEFAULTS.items():
        if not os.getenv(key):
            os.environ[key] = default_value
            print(f"🔧 Set {key} to default value for development")
    
    print("✅ Environment setup completed")

def ensure_google_creds_file():
    """המר JSON של Service Account לקובץ זמני עבור Google TTS"""
    # נסה קודם עם השם החדש, אז עם הישן
    sa_json = os.getenv("GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON") or os.getenv("GOOGLE_TTS_SA_JSON")
    if not sa_json:
        print("⚠️ GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON or GOOGLE_TTS_SA_JSON not set - TTS will not work")
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
        raise RuntimeError(f"Invalid Google TTS JSON format: {e}")