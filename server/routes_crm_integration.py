"""
CRM Integration Routes - WhatsApp + Calls + Customer Management
Advanced integration endpoint for unified customer communication
"""

from flask import request, jsonify, Blueprint
from models import Business, Customer, WhatsAppMessage, CallLog, db
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

crm_integration = Blueprint('crm_integration', __name__)

@crm_integration.route('/api/crm/integration/whatsapp-calls', methods=['GET'])
def get_integrated_communications():
    """מחזיר רשימת לקוחות מאוחדת עם WhatsApp ושיחות"""
    try:
        # Get business ID from header or token
        business_id = request.headers.get('Business-ID', 1)
        
        # Get last 30 days data
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        # Get all customers for business with recent activity
        customers_query = db.session.query(Customer).filter(
            Customer.business_id == business_id
        ).all()
        
        integrated_data = []
        
        for customer in customers_query:
            # Count WhatsApp messages
            whatsapp_count = db.session.query(WhatsAppMessage).filter(
                WhatsAppMessage.business_id == business_id,
                WhatsAppMessage.from_number == customer.phone
            ).count()
            
            recent_whatsapp = db.session.query(WhatsAppMessage).filter(
                WhatsAppMessage.business_id == business_id,
                WhatsAppMessage.from_number == customer.phone,
                WhatsAppMessage.created_at >= thirty_days_ago
            ).count()
            
            # Count call logs
            call_count = db.session.query(CallLog).filter(
                CallLog.business_id == business_id,
                CallLog.from_number == customer.phone
            ).count()
            
            recent_calls = db.session.query(CallLog).filter(
                CallLog.business_id == business_id,
                CallLog.from_number == customer.phone,
                CallLog.created_at >= thirty_days_ago
            ).count()
            
            # Only include customers with some activity
            if whatsapp_count > 0 or call_count > 0:
                integrated_data.append({
                    'customer_id': customer.id,
                    'customer_name': customer.name,
                    'phone': customer.phone,
                    'email': customer.email,
                    'source': customer.source,
                    'created_at': customer.created_at.isoformat() if customer.created_at else None,
                    'stats': {
                        'whatsapp_messages': whatsapp_count,
                        'call_logs': call_count,
                        'recent_messages_30d': recent_whatsapp,
                        'recent_calls_30d': recent_calls
                    }
                })
        
        # Sort by total activity (most active first)
        integrated_data.sort(
            key=lambda x: x['stats']['whatsapp_messages'] + x['stats']['call_logs'], 
            reverse=True
        )
        
        return jsonify({
            'success': True,
            'integrated_communications': integrated_data,
            'total_customers': len(integrated_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting integrated communications: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@crm_integration.route('/api/customers/<int:customer_id>/advanced', methods=['GET'])
def get_customer_advanced_details(customer_id):
    """פרטי לקוח מתקדמים עם כל התקשורת"""
    try:
        business_id = request.headers.get('Business-ID', 1)
        
        # Get customer
        customer = Customer.query.filter_by(
            id=customer_id,
            business_id=business_id
        ).first()
        
        if not customer:
            return jsonify({
                'success': False,
                'error': 'Customer not found'
            }), 404
        
        # Get recent WhatsApp messages (last 10)
        recent_whatsapp = db.session.query(WhatsAppMessage).filter(
            WhatsAppMessage.business_id == business_id,
            WhatsAppMessage.from_number == customer.phone
        ).order_by(WhatsAppMessage.created_at.desc()).limit(10).all()
        
        # Get recent calls (last 10)
        recent_calls = db.session.query(CallLog).filter(
            CallLog.business_id == business_id,
            CallLog.from_number == customer.phone
        ).order_by(CallLog.created_at.desc()).limit(10).all()
        
        # Get statistics
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        total_messages = db.session.query(WhatsAppMessage).filter(
            WhatsAppMessage.business_id == business_id,
            WhatsAppMessage.from_number == customer.phone
        ).count()
        
        recent_messages_30d = db.session.query(WhatsAppMessage).filter(
            WhatsAppMessage.business_id == business_id,
            WhatsAppMessage.from_number == customer.phone,
            WhatsAppMessage.created_at >= thirty_days_ago
        ).count()
        
        total_calls = db.session.query(CallLog).filter(
            CallLog.business_id == business_id,
            CallLog.from_number == customer.phone
        ).count()
        
        recent_calls_30d = db.session.query(CallLog).filter(
            CallLog.business_id == business_id,
            CallLog.from_number == customer.phone,
            CallLog.created_at >= thirty_days_ago
        ).count()
        
        # Get last contact date
        last_message = db.session.query(WhatsAppMessage).filter(
            WhatsAppMessage.business_id == business_id,
            WhatsAppMessage.from_number == customer.phone
        ).order_by(WhatsAppMessage.created_at.desc()).first()
        
        last_call = db.session.query(CallLog).filter(
            CallLog.business_id == business_id,
            CallLog.from_number == customer.phone
        ).order_by(CallLog.created_at.desc()).first()
        
        last_contact_date = None
        if last_message and last_call:
            last_contact_date = max(last_message.created_at, last_call.created_at)
        elif last_message:
            last_contact_date = last_message.created_at
        elif last_call:
            last_contact_date = last_call.created_at
        
        # Format WhatsApp messages
        whatsapp_messages = []
        for msg in recent_whatsapp:
            whatsapp_messages.append({
                'id': msg.id,
                'message_body': msg.message_body,
                'direction': msg.direction,
                'message_status': getattr(msg, 'status', 'delivered'),
                'created_at': msg.created_at.isoformat() if msg.created_at else None
            })
        
        # Format call logs
        call_logs = []
        for call in recent_calls:
            call_logs.append({
                'id': call.id,
                'call_sid': call.call_sid,
                'call_status': call.call_status,
                'call_duration': call.call_duration,
                'transcription': call.transcription,
                'ai_response': call.ai_response,
                'created_at': call.created_at.isoformat() if call.created_at else None
            })
        
        # Get tasks (placeholder for now)
        tasks = []
        
        return jsonify({
            'success': True,
            'customer': {
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone,
                'email': customer.email,
                'source': customer.source,
                'status': getattr(customer, 'status', 'active'),
                'created_at': customer.created_at.isoformat() if customer.created_at else None,
                'stats': {
                    'total_messages': total_messages,
                    'recent_messages_30d': recent_messages_30d,
                    'total_calls': total_calls,
                    'recent_calls_30d': recent_calls_30d,
                    'open_tasks': 0  # Placeholder
                },
                'last_contact_date': last_contact_date.isoformat() if last_contact_date else None,
                'recent_whatsapp': whatsapp_messages,
                'recent_calls': call_logs,
                'tasks': tasks
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting customer advanced details: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@crm_integration.route('/api/customers/<int:customer_id>/contracts', methods=['POST'])
def create_customer_contract(customer_id):
    """יצירת חוזה דיגיטלי ללקוח"""
    try:
        business_id = request.headers.get('Business-ID', 1)
        data = request.get_json()
        
        # Validate customer exists
        customer = Customer.query.filter_by(
            id=customer_id,
            business_id=business_id
        ).first()
        
        if not customer:
            return jsonify({
                'success': False,
                'error': 'Customer not found'
            }), 404
        
        # Create contract (placeholder - would use actual contract system)
        contract_data = {
            'customer_id': customer_id,
            'business_id': business_id,
            'contract_type': data.get('contract_type', 'service'),
            'amount': data.get('amount', 0),
            'description': data.get('description', ''),
            'created_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Created contract for customer {customer_id}: {contract_data}")
        
        return jsonify({
            'success': True,
            'contract': contract_data,
            'message': 'Contract created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error creating contract: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@crm_integration.route('/api/customers/<int:customer_id>/invoices', methods=['POST'])
def create_customer_invoice(customer_id):
    """יצירת חשבונית ללקוח"""
    try:
        business_id = request.headers.get('Business-ID', 1)
        data = request.get_json()
        
        # Validate customer exists
        customer = Customer.query.filter_by(
            id=customer_id,
            business_id=business_id
        ).first()
        
        if not customer:
            return jsonify({
                'success': False,
                'error': 'Customer not found'
            }), 404
        
        # Create invoice (placeholder - would use actual invoice system)
        invoice_data = {
            'customer_id': customer_id,
            'business_id': business_id,
            'amount': data.get('amount', 0),
            'description': data.get('description', ''),
            'due_date': data.get('due_date'),
            'status': 'pending',
            'created_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Created invoice for customer {customer_id}: {invoice_data}")
        
        return jsonify({
            'success': True,
            'invoice': invoice_data,
            'message': 'Invoice created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error creating invoice: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500