"""
Feature Flags System - Business Permission Management
מערכת דגלי תכונות - ניהול הרשאות עסק
"""
from functools import wraps
from flask import jsonify, g, request
import logging

logger = logging.getLogger(__name__)

# Feature mapping to database columns
FEATURE_MAP = {
    'crm': 'crm_enabled',
    'whatsapp': 'whatsapp_enabled', 
    'calls': 'calls_enabled',
    'signatures': 'signature_enabled',
    'invoices': 'invoice_enabled',
    'contracts': 'contracts_enabled',
    'analytics': 'analytics_enabled',
    'ai_assistant': 'ai_enabled'
}

def require_feature(feature_key: str):
    """
    Decorator to require specific business feature to be enabled
    דקורטור הדורש תכונה עסקית ספציפית להיות מופעלת
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Get business context
            business = getattr(g, 'business', None)
            
            if not business:
                logger.warning(f"Feature check '{feature_key}' failed - no business context")
                return jsonify({
                    'error': 'no_business_context',
                    'message': 'לא נמצא הקשר עסקי',
                    'detail': 'Business context required'
                }), 403
            
            # Check feature flag
            flag_column = FEATURE_MAP.get(feature_key)
            if not flag_column:
                logger.error(f"Unknown feature key: {feature_key}")
                return jsonify({
                    'error': 'unknown_feature',
                    'message': f'תכונה לא ידועה: {feature_key}', 
                    'feature': feature_key
                }), 400
            
            feature_enabled = getattr(business, flag_column, False)
            
            if not feature_enabled:
                logger.info(f"Feature '{feature_key}' disabled for business {business.id}")
                return jsonify({
                    'error': 'feature_disabled',
                    'message': f'התכונה {feature_key} לא מופעלת לעסק זה',
                    'feature': feature_key,
                    'upgrade_required': True
                }), 403
            
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def get_business_features(business):
    """
    Get enabled features for a business
    קבלת תכונות מופעלות לעסק
    """
    if not business:
        return []
    
    enabled_features = []
    for feature_key, column_name in FEATURE_MAP.items():
        if getattr(business, column_name, False):
            enabled_features.append(feature_key)
    
    return enabled_features

def check_feature_access(business, feature_key: str) -> bool:
    """
    Check if business has access to specific feature
    בדיקה אם לעסק יש גישה לתכונה ספציפית
    """
    if not business:
        return False
    
    flag_column = FEATURE_MAP.get(feature_key)
    if not flag_column:
        return False
    
    return getattr(business, flag_column, False)

# Middleware for feature context
def load_feature_context():
    """
    Load feature context for current request
    טעינת הקשר תכונות עבור בקשה נוכחית
    """
    business = getattr(g, 'business', None)
    if business:
        g.enabled_features = get_business_features(business)
    else:
        g.enabled_features = []

# Feature-specific decorators for common use cases
def require_crm(fn):
    """Require CRM feature"""
    return require_feature('crm')(fn)

def require_whatsapp(fn):
    """Require WhatsApp feature"""  
    return require_feature('whatsapp')(fn)

def require_calls(fn):
    """Require Calls feature"""
    return require_feature('calls')(fn)

def require_signatures(fn):
    """Require Digital Signatures feature"""
    return require_feature('signatures')(fn)

def require_invoices(fn):
    """Require Invoices feature"""
    return require_feature('invoices')(fn)

def require_contracts(fn):
    """Require Contracts feature"""
    return require_feature('contracts')(fn)

def require_analytics(fn):
    """Require Analytics feature"""
    return require_feature('analytics')(fn)

def require_ai_assistant(fn):
    """Require AI Assistant feature"""
    return require_feature('ai_assistant')(fn)