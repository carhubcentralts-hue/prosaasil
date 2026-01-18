"""
User context API - Provides user permissions and page access information
"""
from flask import Blueprint, jsonify, session, g
from server.auth_api import require_api_auth
from server.models_sql import Business
from server.security.page_registry import PAGE_REGISTRY, get_all_page_keys, get_page_config, ROLE_HIERARCHY
from server.db import db
import logging

logger = logging.getLogger(__name__)

context_bp = Blueprint("context_bp", __name__)

@context_bp.get("/api/me/context")
@require_api_auth()
def get_user_context():
    """
    GET /api/me/context
    
    Returns user context including:
    - User info (id, email, role)
    - Business info (id, name)
    - Enabled pages for the business
    - Page registry subset (pages user can access)
    
    This is used by frontend to:
    - Build dynamic sidebar
    - Configure route guards
    - Show/hide features
    """
    try:
        user = session.get('user')
        if not user:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user_role = user.get('role')
        user_business_id = user.get('business_id')
        
        # Handle system_admin with impersonation
        if user_role == 'system_admin':
            if hasattr(g, 'tenant') and g.tenant:
                business_id = g.tenant.id if hasattr(g.tenant, 'id') else g.tenant
            elif session.get('impersonated_tenant_id'):
                business_id = session['impersonated_tenant_id']
            else:
                # System admin without tenant context
                # Return admin pages only
                admin_pages = [
                    key for key, config in PAGE_REGISTRY.items()
                    if config.is_system_admin_only
                ]
                
                return jsonify({
                    'user': {
                        'id': user.get('id'),
                        'email': user.get('email'),
                        'name': user.get('name'),
                        'role': user_role
                    },
                    'business': None,
                    'enabled_pages': admin_pages,
                    'page_registry': {
                        key: config.to_dict() 
                        for key, config in PAGE_REGISTRY.items()
                        if config.is_system_admin_only
                    },
                    'is_impersonating': False
                })
        else:
            business_id = user_business_id
        
        if not business_id:
            return jsonify({'error': 'No business context'}), 403
        
        # Get business info
        business = Business.query.get(business_id)
        if not business:
            return jsonify({'error': 'Business not found'}), 404
        
        # Get enabled pages for business
        enabled_pages = business.enabled_pages or []
        
        # Filter pages by role permissions
        user_level = ROLE_HIERARCHY.get(user_role, 0)
        
        # Get accessible pages (enabled + role-appropriate)
        accessible_pages = []
        page_registry_subset = {}
        
        for page_key in enabled_pages:
            page_config = get_page_config(page_key)
            if page_config:
                required_level = ROLE_HIERARCHY.get(page_config.min_role, 0)
                if user_level >= required_level:
                    accessible_pages.append(page_key)
                    page_registry_subset[page_key] = page_config.to_dict()
        
        # Add system_admin pages if user is system_admin
        if user_role == 'system_admin':
            for key, config in PAGE_REGISTRY.items():
                if config.is_system_admin_only:
                    accessible_pages.append(key)
                    page_registry_subset[key] = config.to_dict()
        
        return jsonify({
            'user': {
                'id': user.get('id'),
                'email': user.get('email'),
                'name': user.get('name'),
                'role': user_role
            },
            'business': {
                'id': business.id,
                'name': business.name,
                'business_type': business.business_type
            },
            'enabled_pages': accessible_pages,
            'page_registry': page_registry_subset,
            'is_impersonating': session.get('impersonating', False)
        })
        
    except Exception as e:
        logger.error(f"Error getting user context: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
