"""
Page-level permission enforcement
Backend decorator for checking business page access and user roles
"""
from functools import wraps
from flask import session, jsonify, g
from server.models_sql import Business
from server.db import db
from server.security.page_registry import PAGE_REGISTRY, get_page_config
import logging

logger = logging.getLogger(__name__)

def require_page_access(page_key: str):
    """
    Decorator to enforce page-level permissions
    
    Checks:
    1. User is authenticated
    2. Page is enabled for the business (business.enabled_pages)
    3. User role meets minimum requirements for the page
    4. Cross-tenant protection (user belongs to the business)
    
    Args:
        page_key: The page key from PAGE_REGISTRY
        
    Returns:
        403 JSON response if access denied
        Continues to route handler if access granted
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # 1. Check authentication
            user = session.get('user')
            if not user:
                return jsonify({
                    'error': 'unauthorized',
                    'message': 'Authentication required'
                }), 401
            
            user_role = user.get('role')
            user_business_id = user.get('business_id')
            
            # 2. System admin has access to everything
            if user_role == 'system_admin':
                # Check if this is a system_admin-only page
                page_config = get_page_config(page_key)
                if page_config and page_config.is_system_admin_only:
                    # System admin accessing admin pages - allowed
                    return f(*args, **kwargs)
                
                # System admin accessing business pages requires tenant context
                if hasattr(g, 'tenant') and g.tenant:
                    # Use impersonated/selected tenant
                    business_id = g.tenant.id if hasattr(g.tenant, 'id') else g.tenant
                elif session.get('impersonated_tenant_id'):
                    business_id = session['impersonated_tenant_id']
                else:
                    # No tenant context - only allow admin pages
                    if page_config and page_config.is_system_admin_only:
                        return f(*args, **kwargs)
                    return jsonify({
                        'error': 'forbidden',
                        'reason': 'no_tenant_context',
                        'message': 'System admin must select a business to access this page'
                    }), 403
            else:
                # Regular user - must have business_id
                if not user_business_id:
                    return jsonify({
                        'error': 'forbidden',
                        'reason': 'no_business',
                        'message': 'User does not belong to any business'
                    }), 403
                business_id = user_business_id
            
            # 3. Get page configuration
            page_config = get_page_config(page_key)
            if not page_config:
                logger.error(f"Page key '{page_key}' not found in registry")
                return jsonify({
                    'error': 'internal_error',
                    'message': 'Invalid page configuration'
                }), 500
            
            # 4. Skip business permissions check for system_admin-only pages
            if page_config.is_system_admin_only:
                # These pages don't need business.enabled_pages check
                # Only role check matters
                pass
            else:
                # 5. Check if page is enabled for the business
                business = Business.query.get(business_id)
                if not business:
                    return jsonify({
                        'error': 'forbidden',
                        'reason': 'business_not_found',
                        'message': 'Business not found'
                    }), 403
                
                enabled_pages = business.enabled_pages or []
                if page_key not in enabled_pages:
                    logger.warning(f"Page '{page_key}' not enabled for business {business_id}")
                    return jsonify({
                        'error': 'forbidden',
                        'reason': 'page_not_enabled',
                        'message': f'This page is not enabled for your business'
                    }), 403
            
            # 6. Check role permissions
            role_hierarchy = {
                "agent": 0,
                "manager": 1,
                "admin": 2,
                "owner": 3,
                "system_admin": 4
            }
            
            user_level = role_hierarchy.get(user_role, 0)
            required_level = role_hierarchy.get(page_config.min_role, 0)
            
            if user_level < required_level:
                logger.warning(f"User role '{user_role}' insufficient for page '{page_key}' (requires '{page_config.min_role}')")
                return jsonify({
                    'error': 'forbidden',
                    'reason': 'insufficient_role',
                    'message': f'This page requires {page_config.min_role} role or higher'
                }), 403
            
            # 7. All checks passed - allow access
            return f(*args, **kwargs)
        
        return wrapper
    return decorator

def check_api_endpoint_permission(request_path: str, user_role: str, business_id: int = None) -> tuple[bool, str]:
    """
    Check if user has permission to access an API endpoint
    
    This is a helper function for middleware/gateway implementation
    Maps endpoints to page keys using api_tags
    
    Args:
        request_path: The API endpoint path
        user_role: User's role
        business_id: Business ID (optional for system_admin)
        
    Returns:
        (is_allowed, reason) tuple
    """
    # Extract base path
    path_parts = request_path.strip('/').split('/')
    
    # System admin accessing admin endpoints
    if user_role == 'system_admin' and len(path_parts) > 1 and path_parts[1] == 'admin':
        return True, "system_admin_access"
    
    # Map common API paths to page keys
    path_to_page = {
        'leads': 'crm_leads',
        'customers': 'crm_customers',
        'crm': 'crm_customers',
        'calls': 'calls_inbound',
        'outbound': 'calls_outbound',
        'whatsapp': 'whatsapp_inbox',
        'broadcast': 'whatsapp_broadcast',
        'emails': 'emails',
        'calendar': 'calendar',
        'statistics': 'statistics',
        'invoices': 'invoices',
        'contracts': 'contracts',
        'settings': 'settings',
        'users': 'users',
    }
    
    # Try to find matching page
    for path_segment in path_parts:
        if path_segment in path_to_page:
            page_key = path_to_page[path_segment]
            
            # Check business permissions
            if business_id:
                business = Business.query.get(business_id)
                if business:
                    enabled_pages = business.enabled_pages or []
                    if page_key not in enabled_pages:
                        return False, f"page_not_enabled:{page_key}"
            
            # Check role permissions
            page_config = get_page_config(page_key)
            if page_config:
                role_hierarchy = {
                    "agent": 0,
                    "manager": 1,
                    "admin": 2,
                    "owner": 3,
                    "system_admin": 4
                }
                user_level = role_hierarchy.get(user_role, 0)
                required_level = role_hierarchy.get(page_config.min_role, 0)
                
                if user_level < required_level:
                    return False, f"insufficient_role:{page_config.min_role}"
            
            return True, "allowed"
    
    # No matching page found - allow by default (for non-page-specific endpoints)
    return True, "no_page_match"
