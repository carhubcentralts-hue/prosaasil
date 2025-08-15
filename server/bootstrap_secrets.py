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
    יוצר קובץ זמני עם hash כדי שתחלופות ייכנסו לתוקף מיד.
    """
    # אם כבר יש נתיב מפורש – נשארים איתו (אלא אם זה קובץ זמני ישן)
    existing_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if existing_creds and not existing_creds.startswith("/tmp/"):
        print(f"✅ משתמש ב-GOOGLE_APPLICATION_CREDENTIALS קיים: {existing_creds}")
        return True

    # משתמש רק ב-GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON (הסוד הנכון)
    raw = os.getenv("GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON")
    if not raw:
        print("⚠️ GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON לא מוגדר - Google TTS לא יעבוד")
        return False

    print(f"🔧 מעבד GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON ({len(raw)} תווים)")

    # נסיון 1: JSON ישיר
    try:
        cleaned_raw = raw.strip().replace('\n', '').replace('\r', '')
        obj = json.loads(cleaned_raw)
    except Exception:
        # נסיון 2: Base64 
        try:
            import base64
            decoded = base64.b64decode(raw).decode("utf-8")
            obj = json.loads(decoded)
        except Exception as e:
            print(f"❌ לא הצלחתי לפרש את GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON: {e}")
            return False

    # אימות project_id אופציונלי
    expected_project = os.getenv("GCP_PROJECT_ID")
    if expected_project and obj.get("project_id") != expected_project:
        print(f"⚠️ Project ID mismatch: expected {expected_project}, got {obj.get('project_id')}")
        return False

    # יצירת קובץ זמני עם hash לפי תוכן (למניעת קונפליקטים)
    import hashlib
    content_hash = hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:8]
    temp_path = os.path.join(tempfile.gettempdir(), f"gcp_sa_{content_hash}.json")
    
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2)
    
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = temp_path
    print(f"✅ Google credentials file created: {temp_path}")
    print(f"✅ Project ID: {obj.get('project_id', 'N/A')}")
    print(f"✅ Client email: {obj.get('client_email', 'N/A')}")
    return True

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