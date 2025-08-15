import os
from flask import request, abort
from twilio.request_validator import RequestValidator

def require_twilio_signature(fn):
    """Decorator to verify Twilio webhook signatures for security"""
    from functools import wraps
    
    @wraps(fn)
    def twilio_verified_wrapper(*args, **kwargs):
        token = os.getenv("TWILIO_AUTH_TOKEN")
        
        # DEVELOPMENT MODE: Skip validation if no token is set
        if not token:
            from flask import current_app
            current_app.logger.info("🔓 Twilio signature validation BYPASSED - no TWILIO_AUTH_TOKEN in environment")
            return fn(*args, **kwargs)
        
        # PRODUCTION MODE: Validate signature
        try:
            validator = RequestValidator(token)
            url = (os.getenv("PUBLIC_HOST", "").rstrip("/") + request.full_path).rstrip("?")
            sig = request.headers.get("X-Twilio-Signature", "")
            
            if not validator.validate(url, request.form, sig):
                from flask import current_app
                current_app.logger.warning("❌ Twilio signature validation failed: url=%s sig=%s", url, sig[:20] + "..." if sig else "None")
                abort(403)
                
            return fn(*args, **kwargs)
            
        except Exception as e:
            from flask import current_app
            current_app.logger.error("🔥 Twilio signature validation error: %s", e)
            abort(403)
    return twilio_verified_wrapper