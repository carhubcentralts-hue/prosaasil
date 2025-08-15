"""
Twilio security utilities for webhook signature validation
Production-ready security for Twilio webhook endpoints
"""
import os
from functools import wraps
from flask import request, abort, current_app
try:
    from twilio.request_validator import RequestValidator
    TWILIO_SECURITY_AVAILABLE = True
except ImportError:
    RequestValidator = None
    TWILIO_SECURITY_AVAILABLE = False

def require_twilio_signature(f):
    """
    Decorator to validate Twilio webhook signatures
    Skips validation in testing mode
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        # Skip validation in testing mode
        if current_app and current_app.config.get("TESTING"):
            return f(*args, **kwargs)
        
        if not TWILIO_SECURITY_AVAILABLE:
            # Log warning but allow in development
            if os.getenv("FLASK_ENV") != "production":
                return f(*args, **kwargs)
            else:
                return abort(503)  # Service unavailable in production without security
        
        token = os.getenv("TWILIO_AUTH_TOKEN")
        if not token:
            return abort(401)
        
        if not RequestValidator:
            return abort(503)  # Service unavailable without Twilio validator
        
        validator = RequestValidator(token)
        signature = request.headers.get("X-Twilio-Signature", "")
        url = request.url
        params = request.form.to_dict() if request.method == "POST" else request.args.to_dict()
        
        if not validator.validate(url, params, signature):
            return abort(403)
        
        return f(*args, **kwargs)
    return wrapper