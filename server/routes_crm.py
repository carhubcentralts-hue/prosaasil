# server/routes_crm.py
"""
CRM API routes for customer management, threads, and messages
Implements RBAC with business scoping as per guidelines
"""
from flask import Blueprint, jsonify, request, g
from server.routes_auth import require_api_auth
from server.models_sql import Business, Customer, WhatsAppMessage, CallLog
from server.db import db
from datetime import datetime
from sqlalchemy import or_, and_, func

crm_bp = Blueprint("crm_bp", __name__)

def get_business_id():
    """Get business_id based on user role and permissions"""
    user_role = g.user.get("role")
    if user_role in ("admin", "superadmin"):
        # Admin can access all businesses or specify business_id
        return request.args.get("business_id") or g.user.get("business_id")
    else:
        # Business/agent users are scoped to their business
        return g.user.get("business_id")

@crm_bp.get("/api/crm/threads")
@require_api_auth(["admin", "superadmin", "business", "agent"])
def api_threads():
    """Get communication threads (WhatsApp conversations)"""
    try:
        business_id = get_business_id()
        thread_type = request.args.get("type", "whatsapp")
        
        if thread_type == "whatsapp":
            # Get unique WhatsApp conversations
            threads = db.session.query(
                WhatsAppMessage.to_number,
                func.max(WhatsAppMessage.created_at).label('last_message'),
                func.count(WhatsAppMessage.id).label('message_count')
            ).filter_by(business_id=business_id).group_by(
                WhatsAppMessage.to_number
            ).order_by(
                func.max(WhatsAppMessage.created_at).desc()
            ).limit(20).all()
            
            threads_html = ""
            for thread in threads:
                threads_html += f"""
                <div class="p-4 cursor-pointer hover:bg-gray-50 border-b border-gray-100" 
                     onclick="selectThread('{thread.to_number}')">
                    <div class="flex justify-between items-center">
                        <div>
                            <p class="font-medium text-gray-900">{thread.to_number}</p>
                            <p class="text-sm text-gray-500">{thread.message_count} הודעות</p>
                        </div>
                        <span class="text-xs text-gray-400">
                            {thread.last_message.strftime('%d/%m %H:%M')}
                        </span>
                    </div>
                </div>
                """
            
            if not threads_html:
                threads_html = '<div class="p-4 text-center text-gray-500">אין שיחות</div>'
                
            return threads_html
        
        return '<div class="p-4 text-center text-gray-500">סוג לא נתמך</div>'
    except Exception as e:
        return f'<div class="p-4 text-center text-red-500">שגיאה: {str(e)}</div>'

@crm_bp.get("/api/crm/threads/<thread_id>/messages")
@require_api_auth(["admin", "superadmin", "business", "agent"])
def api_thread_messages(thread_id):
    """Get messages for a specific thread"""
    try:
        business_id = get_business_id()
        
        messages = WhatsAppMessage.query.filter_by(
            business_id=business_id,
            to_number=thread_id
        ).order_by(WhatsAppMessage.created_at.asc()).all()
        
        messages_html = ""
        for msg in messages:
            if msg.direction == "out":
                # Outgoing message (right side)
                messages_html += f"""
                <div class="flex justify-end mb-4">
                    <div class="bg-blue-500 text-white rounded-lg px-4 py-2 max-w-xs">
                        <p>{msg.body}</p>
                        <span class="text-xs opacity-75">{msg.created_at.strftime('%H:%M')}</span>
                    </div>
                </div>
                """
            else:
                # Incoming message (left side)
                messages_html += f"""
                <div class="flex justify-start mb-4">
                    <div class="bg-gray-200 text-gray-900 rounded-lg px-4 py-2 max-w-xs">
                        <p>{msg.body}</p>
                        <span class="text-xs text-gray-500">{msg.created_at.strftime('%H:%M')}</span>
                    </div>
                </div>
                """
        
        if not messages_html:
            messages_html = '<div class="text-center text-gray-500 mt-20">אין הודעות בשיחה זו</div>'
            
        return messages_html
    except Exception as e:
        return f'<div class="text-center text-red-500 mt-20">שגיאה: {str(e)}</div>'

@crm_bp.get("/api/crm/customers")
@require_api_auth(["admin", "superadmin", "business", "agent"])
def api_customers():
    """Get customers for CRM management"""
    try:
        business_id = get_business_id()
        
        customers = Customer.query.filter_by(
            business_id=business_id
        ).order_by(Customer.created_at.desc()).limit(50).all()
        
        customers_html = ""
        for customer in customers:
            status_class = {
                'new': 'bg-blue-100 text-blue-800',
                'contacted': 'bg-yellow-100 text-yellow-800',
                'qualified': 'bg-green-100 text-green-800',
                'lost': 'bg-red-100 text-red-800'
            }.get(customer.status, 'bg-gray-100 text-gray-800')
            
            customers_html += f"""
            <div class="bg-white border border-gray-200 rounded-lg p-4">
                <div class="flex justify-between items-start">
                    <div>
                        <h4 class="font-medium text-gray-900">{customer.name}</h4>
                        <p class="text-sm text-gray-500">{customer.phone or 'ללא טלפון'}</p>
                        {f'<p class="text-sm text-gray-500">{customer.email}</p>' if customer.email else ''}
                    </div>
                    <span class="px-2 py-1 text-xs font-medium rounded-full {status_class}">
                        {customer.status}
                    </span>
                </div>
                <div class="mt-2 text-xs text-gray-400">
                    נוצר: {customer.created_at.strftime('%d/%m/%Y')}
                </div>
            </div>
            """
        
        if not customers_html:
            customers_html = '<div class="text-center text-gray-500 py-8">אין לקוחות</div>'
            
        return customers_html
    except Exception as e:
        return f'<div class="text-center text-red-500 py-8">שגיאה: {str(e)}</div>'

@crm_bp.get("/api/calls/active")
@require_api_auth(["admin", "superadmin", "business", "agent"])
def api_active_calls():
    """Get active calls"""
    try:
        business_id = get_business_id()
        
        # Get calls in progress
        active_calls = CallLog.query.filter(
            and_(
                CallLog.business_id == business_id,
                CallLog.status.in_(['in-progress', 'ringing'])
            )
        ).order_by(CallLog.created_at.desc()).all()
        
        calls_html = ""
        for call in active_calls:
            calls_html += f"""
            <div class="flex items-center justify-between p-3 border-b border-gray-100">
                <div>
                    <p class="font-medium text-gray-900">{call.from_number or 'לא ידוע'}</p>
                    <p class="text-sm text-gray-500">{call.created_at.strftime('%H:%M:%S')}</p>
                </div>
                <span class="px-2 py-1 text-xs bg-green-100 text-green-800 rounded-full">
                    {call.status}
                </span>
            </div>
            """
        
        if not calls_html:
            calls_html = '<div class="text-center text-gray-500 py-4">אין שיחות פעילות</div>'
            
        return calls_html
    except Exception as e:
        return f'<div class="text-center text-red-500 py-4">שגיאה: {str(e)}</div>'

@crm_bp.get("/api/calls/history")
@require_api_auth(["admin", "superadmin", "business", "agent"])
def api_call_history():
    """Get call history"""
    try:
        business_id = get_business_id()
        
        calls = CallLog.query.filter_by(
            business_id=business_id
        ).order_by(CallLog.created_at.desc()).limit(20).all()
        
        calls_html = ""
        for call in calls:
            status_class = {
                'completed': 'bg-green-100 text-green-800',
                'failed': 'bg-red-100 text-red-800',
                'in-progress': 'bg-blue-100 text-blue-800'
            }.get(call.status, 'bg-gray-100 text-gray-800')
            
            calls_html += f"""
            <div class="flex items-center justify-between p-3 border-b border-gray-100">
                <div>
                    <p class="font-medium text-gray-900">{call.from_number or 'לא ידוע'}</p>
                    <p class="text-sm text-gray-500">{call.created_at.strftime('%d/%m/%Y %H:%M')}</p>
                    {f'<p class="text-xs text-gray-400 mt-1">{call.transcription[:100]}...</p>' if call.transcription else ''}
                </div>
                <span class="px-2 py-1 text-xs font-medium rounded-full {status_class}">
                    {call.status}
                </span>
            </div>
            """
        
        if not calls_html:
            calls_html = '<div class="text-center text-gray-500 py-4">אין שיחות</div>'
            
        return calls_html
    except Exception as e:
        return f'<div class="text-center text-red-500 py-4">שגיאה: {str(e)}</div>'