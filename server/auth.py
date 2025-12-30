"""
Authentication decorators for API routes
Provides require_auth decorator that wraps require_api_auth from auth_api.py
"""
from functools import wraps
from flask import g, session
from server.auth_api import require_api_auth
import logging

log = logging.getLogger(__name__)

def get_current_tenant():
    """
    Get current tenant ID from Flask g context or session.
    
    This function provides a safe way to retrieve the tenant ID that works
    with the @require_auth/@require_api_auth decorator which sets g.tenant.
    
    Priority order:
    1. g.tenant (set by @require_api_auth decorator) - MOST RELIABLE
    2. impersonated_tenant_id from session (for system_admin)
    3. business_id from user session (backward compatibility)
    4. None for system_admin without impersonation
    
    Returns:
        int or None: The tenant ID (always an integer), or None if system_admin without tenant
    """
    # Priority 1: Use g.tenant if available (set by @require_api_auth) - MOST RELIABLE
    if hasattr(g, 'tenant') and g.tenant is not None:
        tenant_id = g.tenant.id if hasattr(g.tenant, 'id') else g.tenant
        log.debug(f"get_current_tenant(): Using g.tenant={tenant_id}")
        return int(tenant_id) if tenant_id else None
    
    # Priority 2: Check if impersonating (for system_admin)
    if session.get('impersonating') and session.get('impersonated_tenant_id'):
        tenant_id = session['impersonated_tenant_id']
        log.debug(f"get_current_tenant(): Impersonating tenant_id={tenant_id}")
        return int(tenant_id) if tenant_id else None
    
    # Priority 3: Fallback to impersonated session WITHOUT flag (backward compat)
    impersonated_id = session.get('impersonated_tenant_id')
    if impersonated_id:
        log.debug(f"get_current_tenant(): Using impersonated_tenant_id={impersonated_id}")
        return int(impersonated_id)
    
    # Priority 4: Get from user session - try both session keys
    user = session.get('user') or session.get('al_user')
    if user and user.get('business_id'):
        business_id = user.get('business_id')
        log.debug(f"get_current_tenant(): Using user.business_id={business_id}")
        return int(business_id) if business_id else None
    
    # No tenant found - OK for system_admin, error for others
    user_role = user.get('role') if user else None
    if user_role == 'system_admin':
        log.debug(f"get_current_tenant(): system_admin with no tenant (OK)")
        return None
    
    log.error(f"get_current_tenant(): No tenant found! g.tenant={getattr(g, 'tenant', None)}, user={user}")
    return None

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
    # Apply the require_api_auth decorator with no role restrictions
    # This properly preserves function metadata through the wraps decorator inside require_api_auth
    return require_api_auth()(f)
