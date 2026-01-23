from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import Flask, request
import os

def get_real_ip():
    """
    Get real client IP from behind proxy (nginx, cloudflare, etc.)
    Respects X-Forwarded-For header for rate limiting accuracy
    """
    # Trust the rightmost IP in X-Forwarded-For (proxy adds IPs from left to right)
    # This assumes ProxyFix is configured correctly in app_factory.py
    if request.headers.get('X-Forwarded-For'):
        # Get the rightmost IP (closest to the actual client)
        forwarded_ips = request.headers.get('X-Forwarded-For').split(',')
        return forwarded_ips[-1].strip()
    return get_remote_address()

def init_rate_limiter(app: Flask):
    """
    Initialize rate limiting for security.
    
    🔒 P1 Security: Rate limiting with proxy awareness
    - Uses get_real_ip() to get correct IP behind nginx/proxy
    - NO default limits (avoids breaking UI/API)
    - Limits applied per-endpoint in route files
    
    Rate limit presets (see RATE_LIMITS dict):
    - Login: 5/minute (brute force protection)
    - Password reset: 3/minute (abuse prevention)
    - Webhooks: 200/minute (high volume, per IP)
    - Public APIs: 100/minute (general usage)
    """
    
    # Use Redis in production for distributed rate limiting
    storage_uri = os.getenv('REDIS_URL', 'memory://')
    
    limiter = Limiter(
        app=app,
        key_func=get_real_ip,  # 🔒 P1: Use proxy-aware IP detection
        default_limits=[],  # 🔒 P1: No default limits (apply per-endpoint)
        storage_uri=storage_uri,
        strategy="fixed-window",
    )
    
    # ⚠️ Rate limit decorators must be applied in individual route files
    # Example usage:
    #   from server.rate_limiter import RATE_LIMITS
    #   @limiter.limit(RATE_LIMITS['login'])
    #   def login():
    #       ...
    
    return limiter

# 🔒 P1: Rate limit presets for sensitive endpoints
# Apply these selectively in route files using @limiter.limit(RATE_LIMITS['key'])
RATE_LIMITS = {
    'login': "5 per minute",              # Brute force protection
    'password_reset': "3 per minute",      # Password reset abuse prevention
    'webhook_twilio': "200 per minute",    # Twilio webhooks (high volume)
    'webhook_whatsapp': "200 per minute",  # WhatsApp webhooks (high volume)
    'api_authenticated': "100 per minute", # Authenticated API endpoints (general)
    'search': "30 per minute",             # Search operations
    'export': "10 per minute",             # Data export (resource intensive)
}