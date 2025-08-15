# twilio_security.py
import os
from functools import wraps
from flask import request, abort
import logging

logger = logging.getLogger(__name__)

def require_twilio_signature(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        # In development or test mode, bypass signature validation with warning
        if os.environ.get("FLASK_ENV") == "development" or not os.environ.get("TWILIO_AUTH_TOKEN"):
            logger.warning("Twilio signature validation bypassed in development mode")
            return f(*args, **kwargs)
            
        try:
            from twilio.request_validator import RequestValidator
            token = os.environ.get("TWILIO_AUTH_TOKEN")
            validator = RequestValidator(token)
            signature = request.headers.get("X-Twilio-Signature", "")
            url = request.url
            if request.environ.get("HTTP_X_FORWARDED_PROTO") == "https":
                url = url.replace("http://", "https://", 1)
            params = request.form.to_dict() if request.method == "POST" else request.args.to_dict()
            
            if not validator.validate(url, params, signature):
                logger.error("Invalid Twilio signature for URL: %s", url)
                return abort(403)
                
            return f(*args, **kwargs)
            
        except ImportError:
            logger.error("Twilio package not available for signature validation")
            return abort(500)
        except Exception as e:
            logger.error("Signature validation error: %s", e)
            return abort(500)
            
    return wrapper