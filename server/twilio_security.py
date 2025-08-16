"""
Twilio webhook signature validation for production security
"""
import os
import hashlib
import hmac
import base64
from flask import request
from functools import wraps
import logging

log = logging.getLogger(__name__)

def require_twilio_signature(f):
    """Decorator to validate Twilio webhook signatures"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        if not auth_token:
            log.warning("Twilio signature validation disabled - TWILIO_AUTH_TOKEN not set")
            return f(*args, **kwargs)
            
        signature = request.headers.get('X-Twilio-Signature', '')
        if not signature:
            log.error("Missing Twilio signature header")
            return ("Unauthorized", 401)
            
        # Compute expected signature
        url = request.url
        if request.form:
            params = ''.join(f'{k}{v}' for k, v in sorted(request.form.items()))
        else:
            params = ''
            
        expected = base64.b64encode(
            hmac.new(
                auth_token.encode('utf-8'),
                (url + params).encode('utf-8'),
                hashlib.sha1
            ).digest()
        ).decode()
        
        if not hmac.compare_digest(signature, expected):
            log.error("Invalid Twilio signature for %s", request.path)
            return ("Unauthorized", 401)
            
        return f(*args, **kwargs)
    return decorated_function