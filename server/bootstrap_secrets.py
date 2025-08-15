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
    משתמש רק ב-GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON (הסוד הנכון).
    תומך בפורמטים: JSON ישיר או Base64.
    """
    # מחיקת כל GOOGLE_APPLICATION_CREDENTIALS ישן שגוי
    old_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if old_creds:
        print(f"🗑️ מחיקת GOOGLE_APPLICATION_CREDENTIALS ישן שגוי: {old_creds}")
        if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
            del os.environ['GOOGLE_APPLICATION_CREDENTIALS']
        # מחיקת קובץ ישן
        try:
            if os.path.exists(old_creds):
                os.remove(old_creds)
                print(f"✅ קובץ ישן נמחק")
        except:
            pass

    # משתמש רק ב-GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON (הסוד הנכון)
    raw = os.getenv("GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON")
    if not raw:
        print("⚠️ GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON לא מוגדר - Google TTS לא יעבוד")
        return False

    print(f"🔧 מעבד GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON ({len(raw)} תווים)")

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