from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import Flask

def init_rate_limiter(app: Flask):
    """Initialize rate limiting for security"""
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"]
    )
    
    # Apply specific limits after blueprints are registered
    @limiter.limit("100 per hour")
    def webhook_limit():
        pass
    
    return limiter