"""
Bootstrap secrets with graceful degradation
"""
import os
import json
import logging

log = logging.getLogger(__name__)

def check_secrets():
    """Check required secrets and set flags for graceful degradation"""
    
    # OpenAI API
    if not os.getenv("OPENAI_API_KEY"):
        log.warning("OPENAI_API_KEY missing - NLP will be disabled")
        os.environ["NLP_DISABLED"] = "true"
    else:
        log.info("OpenAI API key configured")
    
    # Google TTS
    if not os.getenv("GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON"):
        log.warning("GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON missing - TTS will be disabled") 
        os.environ["TTS_DISABLED"] = "true"
    else:
        try:
            # Validate JSON format
            json.loads(os.getenv("GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON"))
            log.info("Google TTS credentials configured")
        except json.JSONDecodeError:
            log.warning("Invalid GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON format - TTS will be disabled")
            os.environ["TTS_DISABLED"] = "true"
    
    # Twilio
    if not os.getenv("TWILIO_AUTH_TOKEN"):
        log.warning("TWILIO_AUTH_TOKEN missing - webhook signature validation disabled")
    
    # Payment providers
    paypal_configured = bool(os.getenv("PAYPAL_CLIENT_ID") and os.getenv("PAYPAL_CLIENT_SECRET"))
    tranzila_configured = bool(os.getenv("TRANZILA_TERMINAL"))
    
    if not paypal_configured:
        log.info("PayPal credentials missing - will use stub mode")
    if not tranzila_configured:
        log.info("Tranzila credentials missing - will use stub mode")
        
    return {
        "openai": not os.getenv("NLP_DISABLED", "false").lower() in ("true", "1"),
        "tts": not os.getenv("TTS_DISABLED", "false").lower() in ("true", "1"),
        "twilio": bool(os.getenv("TWILIO_AUTH_TOKEN")),
        "paypal": paypal_configured,
        "tranzila": tranzila_configured
    }

def ensure_google_creds_file():
    """Ensure Google credentials file exists if JSON is provided"""
    json_creds = os.getenv("GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON")
    if not json_creds:
        return None
        
    try:
        import tempfile
        creds_data = json.loads(json_creds)
        
        # Create temp file
        fd, path = tempfile.mkstemp(suffix='.json', prefix='gcp_sa_')
        with os.fdopen(fd, 'w') as f:
            json.dump(creds_data, f)
            
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
        log.info(f"Google credentials file created: {path}")
        return path
    except Exception as e:
        log.error(f"Failed to create Google credentials file: {e}")
        return None