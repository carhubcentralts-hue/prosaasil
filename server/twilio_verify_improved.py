"""
אימות חתימת Twilio מושלם עם לוגים ודיבאג
"""
import os
from functools import wraps
from flask import request, abort, current_app
from twilio.request_validator import RequestValidator

def require_twilio_signature(fn):
    """Decorator לאימות חתימת Twilio עם אבטחה ודיבאג"""
    @wraps(fn)
    def _wrapper(*args, **kwargs):
        token = os.getenv("TWILIO_AUTH_TOKEN")
        
        if not token:
            # Development mode - אפשר לעבור בלי token
            current_app.logger.info("🔓 Twilio signature validation BYPASSED - no TWILIO_AUTH_TOKEN in Secrets")
            return fn(*args, **kwargs)
        
        # Production mode - אמת חתימה
        try:
            validator = RequestValidator(token)
            url = (os.getenv("PUBLIC_HOST", "").rstrip("/") + request.full_path).rstrip("?")
            signature = request.headers.get("X-Twilio-Signature", "")
            
            if not validator.validate(url, request.form, signature):
                current_app.logger.warning(
                    "❌ Twilio signature validation FAILED: url=%s signature=%s", 
                    url, 
                    signature[:20] + "..." if signature else "None"
                )
                abort(403)
            
            current_app.logger.debug("✅ Twilio signature validated successfully")
            return fn(*args, **kwargs)
            
        except Exception as e:
            current_app.logger.error("🔥 Twilio signature validation error: %s", e)
            abort(403)
    
    return _wrapper