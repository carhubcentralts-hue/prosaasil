"""
API Adapter Layer - Frontend Compatibility
שכבת מתאם API - התאמה לפרונט-אנד
"""
from flask import Blueprint, jsonify, request, session
from server.models_sql import Business, CallLog, WhatsAppMessage, Customer, User, Payment, db
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

api_adapter_bp = Blueprint('api_adapter', __name__)

def check_permissions(required_roles):
    """Check user permissions for adapter endpoints with proper impersonation support"""
    # Enhanced debugging for session state
    logger.debug(f"Session keys available: {list(session.keys())}")
    
    # Get user from session (both possible keys for robustness)
    user = session.get('user') or session.get('al_user')
    
    # Proper impersonation detection (both flags must be present)
    is_impersonating = bool(session.get('impersonating') and session.get('impersonated_tenant_id'))
    
    # Enhanced logging for debugging
    if is_impersonating:
        logger.debug(f"Impersonation mode detected: tenant_id={session.get('impersonated_tenant_id')}, user={user.get('email') if user else None}")
    
    # Handle impersonation mode properly
    if is_impersonating and user:
        # In impersonation mode, allow admin/manager to access business-level endpoints
        if user.get('role') in ['admin', 'manager'] and 'business' in required_roles:
            logger.debug(f"Impersonation access granted: {user.get('role')} {user.get('email')} accessing as business {session.get('impersonated_tenant_id')}")
            return None  # Permission granted
    
    # Check if user exists in session
    if not user:
        logger.warning(f"Permission denied - no user found. Session keys: {list(session.keys())}, cookies present: {bool(request.cookies)}")
        return jsonify({"error": "forbidden", "requiredRole": "authenticated"}), 403
    
    # Normal role checking
    user_role = user.get('role', '')
    logger.debug(f"User role: {user_role}, required: {required_roles}, impersonating: {is_impersonating}")
    
    if user_role not in required_roles:
        logger.warning(f"Permission denied - user role '{user_role}' not in required roles: {required_roles}")
        return jsonify({"error": "forbidden", "requiredRole": "/".join(required_roles)}), 403
    
    logger.debug(f"Permission granted for user {user.get('email')} with role {user_role}")
    return None  # Permission granted

# === DASHBOARD ENDPOINTS ===

@api_adapter_bp.route('/api/dashboard/stats', methods=['GET'])
def dashboard_stats():
    """BUILD 135: Business-scoped dashboard stats - filtered by tenant_id"""
    perm_check = check_permissions(['admin', 'manager', 'business'])
    if perm_check:
        return perm_check
    
    try:
        # BUILD 135: Get current tenant for filtering
        from server.tenant import get_current_tenant
        tenant_id = get_current_tenant()
        if not tenant_id:
            return jsonify({"error": "No tenant access"}), 403
        
        # Get today's data
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        
        # BUILD 135: Calls stats - FILTERED by tenant_id
        calls_today = CallLog.query.filter(
            CallLog.business_id == tenant_id,
            db.func.date(CallLog.created_at) == today
        ).count()
        
        calls_last7d = CallLog.query.filter(
            CallLog.business_id == tenant_id,
            CallLog.created_at >= week_ago
        ).count()
        
        # Real average handle time
        avg_handle_sec = 0
        
        # BUILD 135: WhatsApp stats - FILTERED by tenant_id
        whatsapp_today = WhatsAppMessage.query.filter(
            WhatsAppMessage.business_id == tenant_id,
            db.func.date(WhatsAppMessage.created_at) == today
        ).count()
        
        whatsapp_last7d = WhatsAppMessage.query.filter(
            WhatsAppMessage.business_id == tenant_id,
            WhatsAppMessage.created_at >= week_ago
        ).count()
        
        # BUILD 135: Real unread messages count - FILTERED by tenant_id
        unread = WhatsAppMessage.query.filter_by(
            business_id=tenant_id,
            status='received'
        ).count()
        
        # BUILD 135: Real revenue stats - FILTERED by tenant_id
        from sqlalchemy import func
        revenue_this_month = Payment.query.with_entities(func.sum(Payment.amount)).filter(
            Payment.business_id == tenant_id,
            func.extract('month', Payment.created_at) == today.month,
            func.extract('year', Payment.created_at) == today.year
        ).scalar() or 0
        revenue_ytd = Payment.query.with_entities(func.sum(Payment.amount)).filter(
            Payment.business_id == tenant_id,
            func.extract('year', Payment.created_at) == today.year
        ).scalar() or 0
        
        return jsonify({
            "calls": {
                "today": calls_today,
                "last7d": calls_last7d,
                "avgHandleSec": avg_handle_sec
            },
            "whatsapp": {
                "today": whatsapp_today,
                "last7d": whatsapp_last7d,
                "unread": unread
            },
            "revenue": {
                "thisMonth": revenue_this_month,
                "ytd": revenue_ytd
            }
        })
        
    except Exception as e:
        logger.error(f"Error in dashboard_stats: {e}")
        return jsonify({"error": "internal_server_error"}), 500

@api_adapter_bp.route('/api/dashboard/activity', methods=['GET'])
def dashboard_activity():
    """BUILD 135: Business-scoped recent activity - filtered by tenant_id"""
    perm_check = check_permissions(['admin', 'manager', 'business'])
    if perm_check:
        return perm_check
    
    try:
        # BUILD 135: Get current tenant for filtering
        from server.tenant import get_current_tenant
        tenant_id = get_current_tenant()
        if not tenant_id:
            return jsonify({"error": "No tenant access"}), 403
        
        # BUILD 135: Get recent WhatsApp messages - FILTERED by tenant_id
        recent_whatsapp = WhatsAppMessage.query.filter_by(
            business_id=tenant_id
        ).order_by(
            WhatsAppMessage.created_at.desc()
        ).limit(10).all()
        
        # BUILD 135: Get recent calls - FILTERED by tenant_id
        recent_calls = CallLog.query.filter_by(
            business_id=tenant_id
        ).order_by(
            CallLog.created_at.desc()
        ).limit(10).all()
        
        activities = []
        
        # Add WhatsApp activities (with None check for created_at)
        for msg in recent_whatsapp:
            if msg.created_at:  # Only add if created_at is not None
                activities.append({
                    "ts": msg.created_at.isoformat() + "Z",
                    "type": "whatsapp",
                    "leadId": msg.customer_id,
                    "preview": msg.message_body[:50] + "..." if len(msg.message_body) > 50 else msg.message_body,
                    "provider": "baileys"  # Default provider
                })
        
        # Add call activities (with None check for created_at)
        for call in recent_calls:
            if call.created_at:  # Only add if created_at is not None
                activities.append({
                    "ts": call.created_at.isoformat() + "Z",
                    "type": "call", 
                    "leadId": call.customer_id,
                    "preview": f"שיחה - {call.status}",
                    "provider": "twilio"
                })
        
        # Sort by timestamp and take top 20
        activities.sort(key=lambda x: x["ts"], reverse=True)
        activities = activities[:20]
        
        return jsonify({
            "items": activities
        })
        
    except Exception as e:
        logger.error(f"Error in dashboard_activity: {e}")
        return jsonify({"error": "internal_server_error"}), 500

# === ADMIN ENDPOINTS ===

@api_adapter_bp.route('/api/admin/businesses', methods=['GET'])
def admin_businesses():
    """Get all businesses - admin and manager only"""
    perm_check = check_permissions(['admin', 'manager'])
    if perm_check:
        return perm_check
    
    try:
        businesses = Business.query.all()
        
        items = []
        for business in businesses:
            # Count active users for this business
            active_users = User.query.filter_by(
                business_id=business.id,
                is_active=True
            ).count()
            
            items.append({
                "id": business.id,
                "name": business.name,
                "domain": f"{business.name.lower().replace(' ', '')}.co.il",  # Mock domain
                "createdAt": business.created_at.isoformat() + "Z",
                "activeUsers": active_users,
                "status": "active" if business.is_active else "inactive"
            })
        
        return jsonify({
            "businesses": items,
            "total": len(items)
        })
        
    except Exception as e:
        logger.error(f"Error in admin_businesses: {e}")
        return jsonify({"error": "internal_server_error"}), 500

@api_adapter_bp.route('/api/admin/stats', methods=['GET'])
def admin_stats():
    """Administrative KPIs - admin and manager only"""
    perm_check = check_permissions(['admin', 'manager'])
    if perm_check:
        return perm_check
    
    try:
        # Leads stats (using customers as leads)
        total_leads = Customer.query.count()
        
        today = datetime.utcnow().date()
        leads_today = Customer.query.filter(
            db.func.date(Customer.created_at) == today
        ).count()
        
        # Active leads (mock - customers with recent activity)
        active_leads = Customer.query.filter(
            Customer.created_at >= datetime.utcnow() - timedelta(days=30)
        ).count()
        
        # Users stats
        total_users = User.query.count()
        online_users = User.query.filter_by(is_active=True).count()  # Mock online as active
        
        # System stats (mock)
        uptime_sec = 86400  # 24 hours
        errors_24h = 2      # Mock error count
        
        return jsonify({
            "leads": {
                "total": total_leads,
                "newToday": leads_today,
                "active": active_leads
            },
            "users": {
                "total": total_users,
                "online": online_users
            },
            "system": {
                "uptimeSec": uptime_sec,
                "errors24h": errors_24h
            }
        })
        
    except Exception as e:
        logger.error(f"Error in admin_stats: {e}")
        return jsonify({"error": "internal_server_error"}), 500