"""
Internal Authentication for Operational Endpoints

This module provides authentication for internal/operational endpoints that should not
be publicly accessible without proper authorization. These endpoints typically expose
operational data like job queues, system health, or worker configurations.

The require_internal_secret decorator validates requests using a shared secret passed
via the X-Internal-Secret header. This prevents information leakage while allowing
internal services (monitoring, health checks) to access these endpoints.

Usage:
    from server.security.internal_auth import require_internal_secret
    
    @app.route('/api/jobs/health')
    @require_internal_secret()
    def jobs_health():
        return jsonify({"status": "ok"})

Environment Variables:
    INTERNAL_SECRET: Required secret for internal endpoints. Server will abort with
                     500 if this is not set in production.
"""
import os
import logging
import secrets
from functools import wraps
from flask import request, abort, jsonify

logger = logging.getLogger(__name__)


def require_internal_secret():
    """
    Decorator to protect internal/operational endpoints with a shared secret.
    
    Validates the X-Internal-Secret header against INTERNAL_SECRET environment variable.
    
    Returns:
        403: If the header is missing or incorrect
        500: If INTERNAL_SECRET is not configured (misconfiguration)
        
    Example:
        @require_internal_secret()
        def protected_endpoint():
            return {"data": "sensitive"}
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Get expected secret from environment
            expected = (os.getenv("INTERNAL_SECRET") or "").strip()
            
            # Fail fast if secret is not configured
            if not expected:
                logger.error("[INTERNAL-AUTH] INTERNAL_SECRET not configured - cannot authenticate")
                return jsonify({
                    "error": "internal_configuration_error",
                    "message": "Internal authentication not configured"
                }), 500
            
            # Get provided secret from request header
            provided = (request.headers.get("X-Internal-Secret") or "").strip()
            
            # Validate secret using constant-time comparison (timing attack protection)
            if not provided or not secrets.compare_digest(provided, expected):
                logger.warning(
                    f"[INTERNAL-AUTH] Unauthorized access attempt to {request.path} "
                    f"from {request.remote_addr}"
                )
                return jsonify({
                    "error": "forbidden",
                    "message": "Invalid or missing internal secret"
                }), 403
            
            # Secret is valid, proceed with request
            return fn(*args, **kwargs)
        
        return wrapper
    return decorator
