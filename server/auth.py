"""
Authentication decorators for API routes
Provides require_auth decorator that wraps require_api_auth from auth_api.py
"""
from server.auth_api import require_api_auth

# Export require_auth as an alias to require_api_auth() with no role restrictions
def require_auth(f):
    """
    Simple authentication decorator that requires a logged-in user
    This is a wrapper around require_api_auth() with no role restrictions
    
    Usage:
        @some_bp.route('/api/endpoint', methods=['GET', 'POST'])
        @require_auth
        def my_endpoint():
            # Your code here
            pass
    """
    return require_api_auth()(f)
