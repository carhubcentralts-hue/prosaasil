"""
Data API endpoints for UI
Based on attached instructions - missing API endpoints
"""
from flask import Blueprint, request, jsonify
from server.models_sql import User, Business, CallLog, WhatsAppMessage, Customer, db
from server.authz import auth_required, roles_required
from datetime import datetime, timedelta

data_api = Blueprint('data_api', __name__)

# ===== ADMIN ENDPOINTS =====

@data_api.route('/api/admin/kpis/calls', methods=['GET'])
@roles_required('admin')
def admin_kpis_calls():
    """Get calls count for today"""
    today = datetime.utcnow().date()
    count = CallLog.query.filter(
        db.func.date(CallLog.created_at) == today
    ).count()
    return str(count)

@data_api.route('/api/admin/kpis/whatsapp', methods=['GET'])
@roles_required('admin')
def admin_kpis_whatsapp():
    """Get WhatsApp messages count for today"""
    today = datetime.utcnow().date()
    count = WhatsAppMessage.query.filter(
        db.func.date(WhatsAppMessage.created_at) == today
    ).count()
    return str(count)

@data_api.route('/api/admin/kpis/businesses', methods=['GET'])
@roles_required('admin')
def admin_kpis_businesses():
    """Get active businesses count"""
    count = Business.query.filter_by(is_active=True).count()
    return str(count)

@data_api.route('/api/admin/kpis/revenue', methods=['GET'])
@roles_required('admin')
def admin_kpis_revenue():
    """Get revenue for this month"""
    # TODO: Implement revenue calculation from payments
    return "₪0"

@data_api.route('/api/admin/tenants', methods=['GET'])
@roles_required('admin')
def admin_tenants():
    """Get all businesses/tenants"""
    businesses = Business.query.all()
    
    tenants_html = ""
    for business in businesses:
        status_badge = "🟢 פעיל" if business.is_active else "🔴 לא פעיל"
        tenants_html += f"""
        <div class="border-b border-gray-200 py-4">
            <div class="flex justify-between items-center">
                <div>
                    <h4 class="font-medium text-gray-900">{business.name}</h4>
                    <p class="text-sm text-gray-500">{business.business_type}</p>
                </div>
                <div class="flex items-center space-x-2">
                    <span class="text-sm">{status_badge}</span>
                    <button class="text-blue-600 hover:text-blue-700 text-sm">עריכה</button>
                </div>
            </div>
        </div>
        """
    
    if not tenants_html:
        tenants_html = '<div class="text-center py-8 text-gray-500">אין עסקים רשומים</div>'
    
    return tenants_html

@data_api.route('/api/admin/calls', methods=['GET'])
@roles_required('admin')
def admin_calls():
    """Get recent calls for admin"""
    calls = CallLog.query.order_by(CallLog.created_at.desc()).limit(10).all()
    
    calls_html = ""
    for call in calls:
        business = Business.query.get(call.business_id)
        business_name = business.name if business else "לא ידוע"
        
        calls_html += f"""
        <div class="border-b border-gray-200 py-3">
            <div class="flex justify-between items-start">
                <div>
                    <p class="font-medium text-gray-900">{call.from_number or 'מספר לא ידוע'}</p>
                    <p class="text-sm text-gray-500">{business_name}</p>
                </div>
                <div class="text-left">
                    <p class="text-sm text-gray-900">{call.status or 'לא ידוע'}</p>
                    <p class="text-xs text-gray-500">{call.created_at.strftime('%H:%M %d/%m') if call.created_at else 'לא ידוע'}</p>
                </div>
            </div>
        </div>
        """
    
    if not calls_html:
        calls_html = '<div class="text-center py-8 text-gray-500">אין שיחות</div>'
    
    return calls_html

# ===== CRM ENDPOINTS =====

@data_api.route('/api/crm/threads', methods=['GET'])
@auth_required
def crm_threads():
    """Get WhatsApp/CRM threads"""
    # For now, return WhatsApp messages grouped by phone number
    messages = WhatsAppMessage.query.filter_by(
        business_id=1  # TODO: Get from session user
    ).order_by(WhatsAppMessage.created_at.desc()).limit(20).all()
    
    threads_html = ""
    seen_numbers = set()
    
    for msg in messages:
        if msg.to_number not in seen_numbers:
            seen_numbers.add(msg.to_number)
            
            # Get last message preview
            preview = msg.body[:50] + "..." if len(msg.body) > 50 else msg.body
            
            threads_html += f"""
            <div class="p-4 hover:bg-gray-50 cursor-pointer border-b" onclick="selectThread('{msg.to_number}')">
                <div class="flex justify-between items-start">
                    <div>
                        <p class="font-medium text-gray-900">{msg.to_number}</p>
                        <p class="text-sm text-gray-500">{preview}</p>
                    </div>
                    <span class="text-xs text-gray-400">{msg.created_at.strftime('%H:%M') if msg.created_at else 'לא ידוע'}</span>
                </div>
            </div>
            """
    
    if not threads_html:
        threads_html = '<div class="text-center py-8 text-gray-500">אין שיחות WhatsApp</div>'
    
    return threads_html

@data_api.route('/api/crm/threads/<thread_id>/messages', methods=['GET'])
@auth_required  
def crm_thread_messages(thread_id):
    """Get messages for a specific thread"""
    messages = WhatsAppMessage.query.filter_by(
        to_number=thread_id,
        business_id=1  # TODO: Get from session user
    ).order_by(WhatsAppMessage.created_at.asc()).all()
    
    messages_html = ""
    for msg in messages:
        direction_class = "justify-end" if msg.direction == "out" else "justify-start"
        bg_class = "bg-blue-500 text-white" if msg.direction == "out" else "bg-gray-200 text-gray-900"
        
        messages_html += f"""
        <div class="flex {direction_class} mb-4">
            <div class="max-w-xs lg:max-w-md px-4 py-2 rounded-lg {bg_class}">
                <p class="text-sm">{msg.body}</p>
                <p class="text-xs opacity-75 mt-1">{msg.created_at.strftime('%H:%M') if msg.created_at else 'לא ידוע'}</p>
            </div>
        </div>
        """
    
    if not messages_html:
        messages_html = '<div class="text-center py-8 text-gray-500">אין הודעות</div>'
    
    return messages_html

@data_api.route('/api/crm/customers', methods=['GET'])
@auth_required
def crm_customers():
    """Get customers for CRM"""
    customers = Customer.query.filter_by(
        business_id=1  # TODO: Get from session user
    ).limit(20).all()
    
    customers_html = '<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">'
    
    for customer in customers:
        status_color = {
            'new': 'bg-blue-100 text-blue-800',
            'active': 'bg-green-100 text-green-800', 
            'lead': 'bg-yellow-100 text-yellow-800'
        }.get(customer.status, 'bg-gray-100 text-gray-800')
        
        customers_html += f"""
        <div class="bg-white p-4 rounded-lg shadow">
            <div class="flex justify-between items-start mb-2">
                <h4 class="font-medium text-gray-900">{customer.name}</h4>
                <span class="px-2 py-1 text-xs rounded-full {status_color}">{customer.status}</span>
            </div>
            <p class="text-sm text-gray-500">{customer.phone or 'אין טלפון'}</p>
            <p class="text-sm text-gray-500">{customer.email or 'אין אימייל'}</p>
            <p class="text-xs text-gray-400 mt-2">{customer.created_at.strftime('%d/%m/%Y') if customer.created_at else 'לא ידוע'}</p>
        </div>
        """
    
    customers_html += '</div>'
    
    if not customers:
        customers_html = '<div class="text-center py-8 text-gray-500">אין לקוחות</div>'
    
    return customers_html

# ===== CALLS ENDPOINTS =====

@data_api.route('/api/calls/active', methods=['GET'])
@auth_required
def calls_active():
    """Get active calls"""
    # For now, show recent calls from last hour
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    calls = CallLog.query.filter(
        CallLog.created_at >= one_hour_ago,
        CallLog.business_id == 1  # TODO: Get from session user
    ).order_by(CallLog.created_at.desc()).all()
    
    calls_html = ""
    for call in calls:
        calls_html += f"""
        <div class="border-b border-gray-200 py-3">
            <div class="flex justify-between items-center">
                <div>
                    <p class="font-medium text-gray-900">{call.from_number or 'מספר לא ידוע'}</p>
                    <p class="text-sm text-gray-500">סטטוס: {call.status}</p>
                </div>
                <span class="text-xs text-gray-400">{call.created_at.strftime('%H:%M') if call.created_at else 'לא ידוע'}</span>
            </div>
        </div>
        """
    
    if not calls_html:
        calls_html = '<div class="text-center py-8 text-gray-500">אין שיחות פעילות</div>'
    
    return calls_html

@data_api.route('/api/calls/history', methods=['GET'])
@auth_required
def calls_history():
    """Get call history"""
    calls = CallLog.query.filter_by(
        business_id=1  # TODO: Get from session user
    ).order_by(CallLog.created_at.desc()).limit(20).all()
    
    calls_html = ""
    for call in calls:
        calls_html += f"""
        <div class="border-b border-gray-200 py-3">
            <div class="flex justify-between items-start">
                <div>
                    <p class="font-medium text-gray-900">{call.from_number or 'מספר לא ידוע'}</p>
                    <p class="text-sm text-gray-500">{call.transcription[:100] + '...' if call.transcription else 'אין תמלול'}</p>
                </div>
                <div class="text-left">
                    <p class="text-sm text-gray-900">{call.status or 'לא ידוע'}</p>
                    <p class="text-xs text-gray-500">{call.created_at.strftime('%H:%M %d/%m') if call.created_at else 'לא ידוע'}</p>
                </div>
            </div>
        </div>
        """
    
    if not calls_html:
        calls_html = '<div class="text-center py-8 text-gray-500">אין שיחות</div>'
    
    return calls_html

# ===== WHATSAPP ENDPOINTS =====

@data_api.route('/api/whatsapp/send', methods=['POST'])
@auth_required
def whatsapp_send():
    """Send WhatsApp message"""
    try:
        data = request.get_json()
        thread_id = data.get('thread_id')  # phone number
        text = data.get('text')
        
        if not thread_id or not text:
            return jsonify({'error': 'Missing thread_id or text'}), 400
        
        # Create outgoing message record
        message = WhatsAppMessage()
        message.business_id = 1  # TODO: Get from session user
        message.to_number = thread_id
        message.direction = 'out'
        message.body = text
        message.status = 'sent'
        message.provider = 'baileys'
        
        db.session.add(message)
        db.session.commit()
        
        # TODO: Actually send via WhatsApp provider
        print(f"📱 Would send WhatsApp to {thread_id}: {text}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500