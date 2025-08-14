# server/environment_check.py - Environment Variables Setup
import os

def setup_environment():
    """Setup critical environment variables for production"""
    
    # Set HOST if not already set
    if not os.getenv('HOST'):
        replit_domain = os.getenv('REPLIT_DEV_DOMAIN')
        if replit_domain:
            host_url = f"https://{replit_domain}"
            os.environ['HOST'] = host_url
            print(f"✅ HOST set to: {host_url}")
        else:
            print("⚠️ REPLIT_DEV_DOMAIN not available, HOST not set")
    
    # Verify critical variables
    critical_vars = {
        'HOST': 'Audio file serving',
        'OPENAI_API_KEY': 'AI conversations and Whisper transcription',
        'GOOGLE_APPLICATION_CREDENTIALS': 'Hebrew text-to-speech'
    }
    
    all_good = True
    for var, purpose in critical_vars.items():
        if os.getenv(var):
            print(f"✅ {var}: Available for {purpose}")
        else:
            print(f"❌ {var}: MISSING - needed for {purpose}")
            all_good = False
    
    return all_good

if __name__ == "__main__":
    setup_environment()