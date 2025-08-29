# server/routes_admin.py
"""
Admin API routes for KPIs, tenant management, and system overview
Implements RBAC with multi-tenant support as per guidelines
"""
from flask import Blueprint, jsonify, request, g
from server.auth_api import require_api_auth
from server.models_sql import Business, User, CallLog, WhatsAppMessage, Customer
from server.db import db
from datetime import datetime, timedelta
from sqlalchemy import func

admin_bp = Blueprint("admin_bp", __name__)

@admin_bp.get("/api/admin/overview")
@require_api_auth(["admin", "superadmin"])
def api_overview():
    """System overview KPIs for admin dashboard"""
    try:
        today = datetime.utcnow().date()
        
        # Calls today
        calls_today = CallLog.query.filter(
            func.date(CallLog.created_at) == today
        ).count()
        
        # WhatsApp messages today
        whatsapp_today = WhatsAppMessage.query.filter(
            func.date(WhatsAppMessage.created_at) == today
        ).count()
        
        # Active businesses
        active_businesses = Business.query.filter_by(is_active=True).count()
        
        # Mock revenue for now - integrate with real payment data later
        revenue_month = 15000  # ₪15,000 mock
        
        return jsonify({
            "calls_today": calls_today,
            "whatsapp_today": whatsapp_today,
            "active_businesses": active_businesses,
            "revenue_month": f"₪{revenue_month:,}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@admin_bp.get("/api/admin/kpis/calls")
@require_api_auth(["admin", "superadmin"])
def api_kpis_calls():
    """Get calls KPI"""
    try:
        today = datetime.utcnow().date()
        count = CallLog.query.filter(func.date(CallLog.created_at) == today).count()
        return str(count)
    except Exception as e:
        return "0"

@admin_bp.get("/api/admin/kpis/whatsapp")
@require_api_auth(["admin", "superadmin"])
def api_kpis_whatsapp():
    """Get WhatsApp KPI"""
    try:
        today = datetime.utcnow().date()
        count = WhatsAppMessage.query.filter(func.date(WhatsAppMessage.created_at) == today).count()
        return str(count)
    except Exception as e:
        return "0"

@admin_bp.get("/api/admin/kpis/businesses")
@require_api_auth(["admin", "superadmin"])
def api_kpis_businesses():
    """Get active businesses KPI"""
    try:
        count = Business.query.filter_by(is_active=True).count()
        return str(count)
    except Exception as e:
        return "0"

@admin_bp.get("/api/admin/kpis/revenue")
@require_api_auth(["admin", "superadmin"])
def api_kpis_revenue():
    """Get revenue KPI"""
    try:
        # Mock revenue - integrate with Payment model later
        return "₪15,000"
    except Exception as e:
        return "₪0"

@admin_bp.get("/api/admin/tenants")
@require_api_auth(["admin", "superadmin"])
def api_tenants():
    """Get all businesses/tenants for admin management"""
    try:
        businesses = Business.query.order_by(Business.created_at.desc()).all()
        
        tenants_html = ""
        for business in businesses:
            status_class = "bg-green-100 text-green-800" if business.is_active else "bg-red-100 text-red-800"
            status_text = "פעיל" if business.is_active else "לא פעיל"
            
            tenants_html += f"""
            <div class="flex items-center justify-between p-4 border-b border-gray-100 hover:bg-gray-50">
                <div>
                    <h4 class="font-medium text-gray-900">{business.name}</h4>
                    <p class="text-sm text-gray-500">{business.business_type}</p>
                </div>
                <div class="flex items-center space-x-2">
                    <span class="px-2 py-1 text-xs font-medium rounded-full {status_class}">{status_text}</span>
                    <button onclick="editBusiness({business.id})" class="text-blue-600 hover:text-blue-800 text-sm mr-2">עריכה</button>
                    <button onclick="loginAsBusiness({business.id})" class="text-green-600 hover:text-green-800 text-sm mr-2">התחבר כעסק</button>
                    <button onclick="changePassword({business.id})" class="text-purple-600 hover:text-purple-800 text-sm">שנה סיסמה</button>
                </div>
            </div>
            """
        
        if not tenants_html:
            tenants_html = '<div class="text-center text-gray-500 py-8">אין עסקים במערכת</div>'
            
        return tenants_html
    except Exception as e:
        return f'<div class="text-center text-red-500 py-8">שגיאה: {str(e)}</div>'

@admin_bp.get("/api/admin/calls")
@require_api_auth(["admin", "superadmin"])
def api_admin_calls():
    """Get recent calls for admin dashboard"""
    try:
        calls = CallLog.query.order_by(CallLog.created_at.desc()).limit(10).all()
        
        calls_html = ""
        for call in calls:
            # Get business name
            business = Business.query.get(call.business_id) if call.business_id else None
            business_name = business.name if business else "לא ידוע"
            
            status_class = {
                'completed': 'bg-green-100 text-green-800',
                'failed': 'bg-red-100 text-red-800',
                'in-progress': 'bg-blue-100 text-blue-800'
            }.get(call.status, 'bg-gray-100 text-gray-800')
            
            calls_html += f"""
            <div class="flex items-center justify-between p-4 border-b border-gray-100">
                <div>
                    <div class="flex items-center space-x-2">
                        <span class="font-medium text-gray-900">{call.from_number or 'לא ידוע'}</span>
                        <span class="text-sm text-gray-500">→ {business_name}</span>
                    </div>
                    <p class="text-sm text-gray-500">{call.created_at.strftime('%d/%m/%Y %H:%M') if call.created_at else 'לא ידוע'}</p>
                </div>
                <span class="px-2 py-1 text-xs font-medium rounded-full {status_class}">{call.status}</span>
            </div>
            """
        
        if not calls_html:
            calls_html = '<div class="text-center text-gray-500 py-8">אין שיחות</div>'
            
        return calls_html
    except Exception as e:
        return f'<div class="text-center text-red-500 py-8">שגיאה: {str(e)}</div>'