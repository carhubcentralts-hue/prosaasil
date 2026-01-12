from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import Flask
import os

def init_rate_limiter(app: Flask):
    """
    Initialize rate limiting for security.
    
    Rate limits:
    - Default: 200/day, 50/hour for all endpoints
    - Login: 5/minute (brute force protection)
    - API: 100/minute for authenticated users
    - Webhooks: 1000/hour (high volume expected)
    - WhatsApp: 60/minute per endpoint
    """
    
    # Use Redis in production for distributed rate limiting
    storage_uri = os.getenv('REDIS_URL', 'memory://')
    
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri=storage_uri,
        strategy="fixed-window",  # Use fixed window for predictable behavior
    )
    
    # ⚠️ Rate limit decorators are applied in individual route files
    # This function returns the limiter instance for use elsewhere
    
    return limiter

# Rate limit presets for use in route decorators
RATE_LIMITS = {
    'login': "5 per minute",           # Brute force protection
    'password_reset': "3 per minute",   # Password reset protection  
    'api_default': "100 per minute",    # Authenticated API calls
    'webhook': "1000 per hour",         # Webhook endpoints (high volume)
    'whatsapp': "60 per minute",        # WhatsApp operations
    'search': "30 per minute",          # Search operations
    'export': "10 per minute",          # Data export (resource intensive)
}