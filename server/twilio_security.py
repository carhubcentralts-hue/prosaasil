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
from urllib.parse import urlencode

def _effective_url(req):
    """
    Get effective URL for Twilio signature validation.
    ✅ BUILD 156: Support PUBLIC_BASE_URL override and GET query strings
    """
    # Check if PUBLIC_BASE_URL is set (for production/custom domains)
    public_base_url = os.getenv('PUBLIC_BASE_URL', '').rstrip('/')
    
    if public_base_url:
        # Use explicit public URL for signature validation
        base = public_base_url
    else:
        # Fall back to proxy headers
        scheme = (req.headers.get("X-Forwarded-Proto") or req.scheme).split(",")[0].strip()
        host = (req.headers.get("X-Forwarded-Host") or req.host).split(",")[0].strip()
        base = f"{scheme}://{host}"
    
    # For POST: URL without query string (params are in form body)
    # For GET: URL WITH query string (params are in URL)
    if req.method == "GET" and req.query_string:
        return f"{base}{req.path}?{req.query_string.decode('utf-8')}"
    return f"{base}{req.path}"

def require_twilio_signature(f):
    """Decorator to validate Twilio webhook signatures
    ✅ BUILD 156: Fixed GET request signature validation
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        flask_env = os.getenv('FLASK_ENV', 'production')
        
        # ✅ BUILD 153: SECURITY FIX - only skip validation in explicit development mode
        # VALIDATE_TWILIO_SIGNATURE only works when FLASK_ENV=development
        if flask_env == 'development':
            validate_signature_env = os.getenv('VALIDATE_TWILIO_SIGNATURE', 'true').lower()
            if validate_signature_env == 'false':
                print("⚠️ DEV MODE: VALIDATE_TWILIO_SIGNATURE=false - signature validation skipped")
                return f(*args, **kwargs)
            
        # Get Twilio auth token
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        if not auth_token:
            # ✅ BUILD 153 FINAL: SECURITY FIX - reject in production if no auth token
            if flask_env == 'development':
                print("⚠️ DEV MODE: TWILIO_AUTH_TOKEN not set - signature validation skipped")
                return f(*args, **kwargs)
            else:
                print("❌ PRODUCTION: TWILIO_AUTH_TOKEN not set - rejecting request")
                abort(403)
        
        # Get signature from header
        signature = request.headers.get('X-Twilio-Signature')
        if not signature:
            print("❌ Missing X-Twilio-Signature header")
            abort(403)
        
        # Get effective URL behind proxy
        url = _effective_url(request)
        
        # ✅ BUILD 156: For GET requests, params are in URL not form body
        if request.method == "GET":
            params = {}  # Params already in URL for GET
        else:
            params = request.form
        
        if not validate_signature(auth_token, signature, url, params):
            # ✅ BUILD 156: Try alternate URLs for signature validation
            # Sometimes proxy headers don't match what Twilio has configured
            alternate_urls = _get_alternate_urls(request, url)
            
            validated = False
            for alt_url in alternate_urls:
                if validate_signature(auth_token, signature, alt_url, params):
                    print(f"✅ Twilio signature validated with alternate URL: {alt_url}")
                    validated = True
                    break
            
            if not validated:
                print(f"❌ Invalid Twilio signature:")
                print(f"   URL calculated: {url}")
                print(f"   Alternate URLs tried: {alternate_urls}")
                print(f"   X-Twilio-Signature: {signature}")
                print(f"   Request method: {request.method}")
                print(f"   Request path: {request.path}")
                abort(403)
            
        return f(*args, **kwargs)
    return decorated_function

def _get_alternate_urls(req, primary_url):
    """
    Generate alternate URLs to try for signature validation.
    ✅ BUILD 156: Handle domain mismatches between Twilio config and actual request
    """
    alternate_urls = []
    
    # Get path and query
    path = req.path
    query = f"?{req.query_string.decode('utf-8')}" if req.method == "GET" and req.query_string else ""
    
    # Try different host sources
    hosts = set()
    
    # From X-Forwarded-Host (may have multiple values)
    fwd_host = req.headers.get("X-Forwarded-Host", "")
    for h in fwd_host.split(","):
        h = h.strip()
        if h:
            hosts.add(h)
    
    # From Host header
    if req.host:
        hosts.add(req.host.split(",")[0].strip())
    
    # From PUBLIC_BASE_URL
    public_url = os.getenv('PUBLIC_BASE_URL', '').rstrip('/')
    if public_url:
        # Extract host from PUBLIC_BASE_URL
        from urllib.parse import urlparse
        parsed = urlparse(public_url)
        if parsed.netloc:
            hosts.add(parsed.netloc)
    
    # Generate URLs for each host
    schemes = ['https', 'http']
    for host in hosts:
        for scheme in schemes:
            alt_url = f"{scheme}://{host}{path}{query}"
            if alt_url != primary_url:
                alternate_urls.append(alt_url)
    
    return alternate_urls

def validate_signature(auth_token, signature, url, params):
    """Validate Twilio webhook signature
    ✅ BUILD 156: Fixed for both GET and POST requests
    """
    try:
        # Create the string to sign
        # For POST: URL + sorted params
        # For GET: Just the full URL (params already in URL)
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
