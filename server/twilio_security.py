"""
Twilio Security - Signature Validation for Webhooks
מודול אבטחה עבור Twilio - אימות חתימה לוובהוקים
"""
import os
import logging
from functools import wraps
from flask import request, abort, current_app

logger = logging.getLogger(__name__)

def require_twilio_signature(f):
    """
    Decorator to validate Twilio webhook signatures
    דקורטור לאימות חתימות וובהוק של Twilio
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        # Allow bypass in TESTING mode
        if current_app.config.get("TESTING"):
            logger.info("Bypassing Twilio signature validation in TESTING mode")
            return f(*args, **kwargs)

        # Check for development bypass
        if os.getenv("BYPASS_TWILIO_SIGNATURE") == "true":
            logger.warning("Bypassing Twilio signature validation - development mode")
            return f(*args, **kwargs)

        token = os.environ.get("TWILIO_AUTH_TOKEN")
        if not token:
            logger.error("TWILIO_AUTH_TOKEN not set - cannot validate signature")
            return abort(401)

        try:
            from twilio.request_validator import RequestValidator
            
            validator = RequestValidator(token)
            signature = request.headers.get("X-Twilio-Signature", "")
            
            # Handle Proxy/HTTPS forwarding
            url = request.url
            if request.environ.get('HTTP_X_FORWARDED_PROTO') == 'https':
                url = url.replace('http://', 'https://', 1)
            
            # Get form data for validation
            if request.method == "POST":
                params = request.form.to_dict()
            else:
                params = request.args.to_dict()

            if not validator.validate(url, params, signature):
                logger.error(f"Twilio signature validation failed for {url}")
                logger.debug(f"Expected signature validation for params: {params}")
                return abort(403)
            
            logger.info("Twilio signature validation successful")
            return f(*args, **kwargs)
            
        except ImportError:
            logger.error("twilio package not installed - cannot validate signature")
            return abort(500)
        except Exception as e:
            logger.error(f"Error validating Twilio signature: {e}")
            return abort(500)
            
    return wrapper