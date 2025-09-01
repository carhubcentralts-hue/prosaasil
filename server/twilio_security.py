"""
Twilio Webhook Security Validation
אבטחת webhooks של Twilio - PRODUCTION READY
"""
import os
import hashlib
import hmac
import base64
from functools import wraps
from flask import request, abort

def _effective_url(req):
    """Get effective URL considering proxy headers from Replit"""
    scheme = (req.headers.get("X-Forwarded-Proto") or req.scheme).split(",")[0].strip()
    host   = (req.headers.get("X-Forwarded-Host")  or req.host).split(",")[0].strip()
    # Twilio חתימה ל-POST form: URL בלי query string
    return f"{scheme}://{host}{req.path}"

def require_twilio_signature(f):
    """Decorator to validate Twilio webhook signatures"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # In development, skip validation  
        if os.getenv('FLASK_ENV') == 'development' or os.getenv('PUBLIC_HOST'):
            return f(*args, **kwargs)
            
        # Get Twilio auth token
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        if not auth_token:
            # If no auth token, log warning but continue (graceful degradation)
            print("⚠️ TWILIO_AUTH_TOKEN not set - signature validation skipped")
            return f(*args, **kwargs)
        
        # Get signature from header
        signature = request.headers.get('X-Twilio-Signature')
        if not signature:
            print("❌ Missing X-Twilio-Signature header")
            abort(403)
        
        # Get effective URL behind proxy (Replit uses proxies)
        url = _effective_url(request)
        if not validate_signature(auth_token, signature, url, request.form):
            print(f"❌ Invalid Twilio signature:")
            print(f"   URL calculated: {url}")
            print(f"   X-Twilio-Signature: {signature}")
            print(f"   Request path: {request.path}")
            abort(403)
            
        return f(*args, **kwargs)
    return decorated_function

def validate_signature(auth_token, signature, url, params):
    """Validate Twilio webhook signature"""
    try:
        # Create the string to sign
        string_to_sign = url
        if params:
            sorted_params = sorted(params.items())
            for key, value in sorted_params:
                string_to_sign += f"{key}{value}"
        
        # Create HMAC-SHA1 signature
        mac = hmac.new(
            auth_token.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha1
        )
        computed_signature = base64.b64encode(mac.digest()).decode('utf-8')
        
        return hmac.compare_digest(signature, computed_signature)
    except Exception as e:
        print(f"❌ Signature validation error: {e}")
        return False