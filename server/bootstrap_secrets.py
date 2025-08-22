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
    
    # Google TTS - handle both JSON and credentials file
    google_json = os.getenv("GOOGLE_TTS_SA_JSON") or os.getenv("GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON")
    if not google_json:
        log.warning("Google TTS credentials missing - TTS will be disabled") 
        os.environ["TTS_DISABLED"] = "true"
    else:
        try:
            # Validate JSON format and create credentials file
            creds_data = json.loads(google_json)
            
            # Create credentials file if GOOGLE_APPLICATION_CREDENTIALS not set
            if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                creds_path = ensure_google_creds_file()
                if creds_path:
                    log.info(f"Google TTS credentials file created: {creds_path}")
                else:
                    log.warning("Failed to create Google credentials file")
                    os.environ["TTS_DISABLED"] = "true"
            else:
                log.info("Google TTS credentials configured")
                
        except json.JSONDecodeError:
            log.warning("Invalid Google credentials JSON format - TTS will be disabled")
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
    # Try both possible environment variable names
    json_creds = os.getenv("GOOGLE_TTS_SA_JSON") or os.getenv("GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON")
    if not json_creds:
        return None
        
    try:
        import tempfile
        creds_data = json.loads(json_creds)
        
        # Create persistent file in /tmp for deployment
        creds_path = "/tmp/google_service_account.json"
        with open(creds_path, 'w') as f:
            json.dump(creds_data, f)
            
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
        log.info(f"Google credentials file created: {creds_path}")
        return creds_path
    except Exception as e:
        log.error(f"Failed to create Google credentials file: {e}")
        return None