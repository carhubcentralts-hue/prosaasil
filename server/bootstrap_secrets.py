import os
import json
import tempfile
import pathlib
import base64

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

def ensure_google_creds_file() -> bool:
    """
    מגדיר GOOGLE_APPLICATION_CREDENTIALS כך ש-Google TTS יעבוד.
    תומך בשלושה פורמטים:
    1) GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON = תוכן JSON מלא
    2) GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON = תוכן Base64 של ה-JSON
    3) GOOGLE_APPLICATION_CREDENTIALS = נתיב לקובץ JSON קיים
    """
    # אם כבר יש נתיב מוגדר – נכבד אותו
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        print(f"✅ Google credentials already set: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")
        return True

    raw = os.getenv("GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON") or os.getenv("GOOGLE_TTS_SA_JSON")
    if not raw:
        print("⚠️ GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON or GOOGLE_TTS_SA_JSON not set - TTS will not work")
        return False  # לא נגדיר כלום – הקולר צריך להגדיר ידנית GOOGLE_APPLICATION_CREDENTIALS

    # נסה לזהות האם זה JSON ישיר, Base64 או נתיב
    def _set_creds_path(p: pathlib.Path) -> bool:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(p)
        print(f"✅ Google credentials file created: {p}")
        return True

    # 3) אולי זה נתיב לקובץ? (רק אם זה לא JSON ארוך)
    if len(raw) < 500 and not raw.strip().startswith('{'):  # נתיב קובץ לא יהיה ארוך מ-500 תווים
        try:
            possible_path = pathlib.Path(raw)
            if possible_path.exists() and possible_path.is_file():
                return _set_creds_path(possible_path)
        except OSError:
            # אם זה לא נתיב תקין, נמשיך לנסיונות הבאים
            pass

    # 1) JSON ישיר
    try:
        # Clean and normalize the JSON first
        cleaned_raw = raw.strip().replace('\n', '').replace('\r', '')
        obj = json.loads(cleaned_raw)
        
        # Use tempfile for safe file creation
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(obj, f, indent=2)
            temp_path = f.name
        
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_path
        print(f"✅ Google credentials file created: {temp_path}")
        return True
    except Exception:
        pass

    # 2) Base64 → JSON
    try:
        decoded = base64.b64decode(raw).decode("utf-8")
        cleaned_decoded = decoded.strip().replace('\n', '').replace('\r', '')
        obj = json.loads(cleaned_decoded)
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(obj, f, indent=2)
            temp_path = f.name
            
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_path
        print(f"✅ Google credentials file created from Base64: {temp_path}")
        return True
    except Exception:
        print("❌ Failed to parse GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON - invalid format")
        return False