"""
Advanced CRM API Routes for React Frontend
Enhanced Hebrew CRM with Monday.com level functionality
"""

from flask import request, jsonify
from app import app, db
from models import Business, CallLog, Customer, WhatsAppMessage
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, func
import logging

logger = logging.getLogger(__name__)

@app.route("/api/crm/customers", methods=["GET"])
def api_get_crm_customers():
    """
    Get customers with advanced filtering and search
    """
    try:
        business_id = request.args.get('business_id', type=int)
        if not business_id:
            return jsonify({"error": "Missing business_id"}), 400
            
        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Filters
        search = request.args.get('search', '').strip()
        status_filter = request.args.get('status', '').strip()
        source_filter = request.args.get('source', '').strip()
        
        # Build query
        query = Customer.query.filter_by(business_id=business_id)
        
        # Search across multiple fields
        if search:
            search_term = f"%{search}%"
            search_filters = []
            if hasattr(Customer, 'name') and Customer.name is not None:
                search_filters.append(Customer.name.ilike(search_term))
            if hasattr(Customer, 'phone') and Customer.phone is not None:
                search_filters.append(Customer.phone.ilike(search_term))
            if hasattr(Customer, 'email') and Customer.email is not None:
                search_filters.append(Customer.email.ilike(search_term))
            
            if search_filters:
                query = query.filter(or_(*search_filters))
            
        # Status filter
        if status_filter:
            query = query.filter(Customer.status == status_filter)
            
        # Source filter
        if source_filter:
            query = query.filter(Customer.source == source_filter)
        
        # AgentLocator v42: Replace customers_paginate with proper pagination
        total = query.count()
        items = query.order_by(Customer.created_at.desc()).offset((page-1)*per_page).limit(per_page).all()
        
        # Convert to dict with Hebrew labels
        customers_data = []
        for customer in items:
            customer_dict = {
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone,
                'email': customer.email,
                'company': getattr(customer, 'company', ''),
                'status': customer.status,
                'status_hebrew': get_status_hebrew(customer.status),
                'source': customer.source,
                'source_hebrew': get_source_hebrew(customer.source),
                'created_at': customer.created_at.isoformat() if customer.created_at else None,
                'updated_at': customer.updated_at.isoformat() if customer.updated_at else None,
                'notes': getattr(customer, 'notes', ''),
                'tags': getattr(customer, 'tags', '').split(',') if getattr(customer, 'tags', '') else [],
                'last_contact': getattr(customer, 'last_contact', None).isoformat() if hasattr(customer, 'last_contact') and getattr(customer, 'last_contact', None) is not None else None
            }
            customers_data.append(customer_dict)
        
        # v42 format - consistent with document requirements
        response = {
            'page': page,
            'limit': per_page, 
            'total': total,
            'items': customers_data
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting CRM customers: {e}")
        return jsonify({"error": "Failed to get customers"}), 500

@app.route("/api/crm/stats", methods=["GET"])
def api_get_crm_stats():
    """
    Get CRM statistics dashboard
    """
    try:
        business_id = request.args.get('business_id', type=int)
        if not business_id:
            return jsonify({"error": "Missing business_id"}), 400
        
        # Current date calculations
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        month_start = today.replace(day=1)
        
        # Basic counts
        total_customers = Customer.query.filter_by(business_id=business_id).count()
        active_customers = Customer.query.filter_by(
            business_id=business_id, 
            status='active'
        ).count()
        
        # New leads this week
        new_leads = Customer.query.filter(
            Customer.business_id == business_id,
            Customer.created_at >= week_ago
        ).count()
        
        # Conversion rate calculation (simplified)
        qualified_customers = Customer.query.filter_by(
            business_id=business_id,
            status='active'
        ).count()
        
        closed_won = total_customers  # Simplified for now
        
        conversion_rate = 0
        if qualified_customers > 0:
            conversion_rate = round((closed_won / qualified_customers) * 100, 1)
        
        # Additional stats
        contacted_this_month = Customer.query.filter(
            Customer.business_id == business_id,
            Customer.last_contact_date >= month_start
        ).count()
        
        stats = {
            'total_customers': total_customers,
            'active_customers': active_customers,
            'new_leads': new_leads,
            'conversion_rate': conversion_rate,
            'contacted_this_month': contacted_this_month,
            'qualified_leads': qualified_customers,
            'closed_won': closed_won,
            'updated_at': datetime.utcnow().isoformat()
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting CRM stats: {e}")
        return jsonify({"error": "Failed to get stats"}), 500

@app.route("/api/calls/list", methods=["GET"])
def api_get_calls_list():
    """
    Get calls list with filtering and transcriptions
    """
    try:
        business_id = request.args.get('business_id', type=int)
        if not business_id:
            return jsonify({"error": "Missing business_id"}), 400
            
        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Filters
        search = request.args.get('search', '').strip()
        status_filter = request.args.get('status', '').strip()
        date_filter = request.args.get('date', '').strip()
        
        # Build query
        query = CallLog.query.filter_by(business_id=business_id)
        
        # Search by phone number
        if search:
            search_term = f"%{search}%"
            search_filters = []
            if hasattr(CallLog, 'from_number') and CallLog.from_number is not None:
                search_filters.append(CallLog.from_number.ilike(search_term))
            if hasattr(CallLog, 'to_number') and CallLog.to_number is not None:
                search_filters.append(CallLog.to_number.ilike(search_term))
            if search_filters:
                query = query.filter(or_(*search_filters))
            
        # Status filter
        if status_filter and hasattr(CallLog, 'call_status'):
            query = query.filter(CallLog.call_status == status_filter)
            
        # Date filter
        if date_filter:
            today = datetime.utcnow().date()
            if date_filter == 'today':
                query = query.filter(func.date(CallLog.created_at) == today)
            elif date_filter == 'yesterday':
                yesterday = today - timedelta(days=1)
                query = query.filter(func.date(CallLog.created_at) == yesterday)
            elif date_filter == 'week':
                week_ago = today - timedelta(days=7)
                query = query.filter(CallLog.created_at >= week_ago)
            elif date_filter == 'month':
                month_start = today.replace(day=1)
                query = query.filter(CallLog.created_at >= month_start)
        
        # Execute query with pagination
        calls_paginated = query.order_by(CallLog.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Convert to dict with Hebrew labels
        calls_data = []
        for call in calls_paginated.items:
            
            # Try to get customer name
            customer_name = None
            if call.from_number:
                customer = Customer.query.filter_by(
                    business_id=business_id,
                    phone=call.from_number
                ).first()
                if customer:
                    customer_name = customer.name
            
            call_dict = {
                'id': call.id,
                'from_number': call.from_number,
                'to_number': call.to_number,
                'customer_name': customer_name,
                'status': getattr(call, 'call_status', 'completed'),
                'status_hebrew': get_call_status_hebrew(getattr(call, 'call_status', 'completed')),
                'direction': 'inbound',  # Default to inbound
                'duration': getattr(call, 'call_duration', 0) or 0,
                'created_at': call.created_at.isoformat() if call.created_at else None,
                'recording_url': getattr(call, 'recording_url', None),
                'transcription': getattr(call, 'transcription', None),
                'ai_response': getattr(call, 'ai_response', None),
                'call_sid': getattr(call, 'call_sid', None)
            }
            calls_data.append(call_dict)
        
        response = {
            'calls': calls_data,
            'pagination': {
                'page': calls_paginated.page,
                'per_page': calls_paginated.per_page,
                'total': calls_paginated.total,
                'pages': calls_paginated.pages,
                'has_next': calls_paginated.has_next,
                'has_prev': calls_paginated.has_prev
            }
        }
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting calls list: {e}")
        return jsonify({"error": "Failed to get calls"}), 500

@app.route("/api/calls/stats", methods=["GET"])
def api_get_calls_stats():
    """
    Get calls statistics dashboard
    """
    try:
        business_id = request.args.get('business_id', type=int)
        if not business_id:
            return jsonify({"error": "Missing business_id"}), 400
        
        # Current date calculations
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        
        # Basic counts
        total_calls = CallLog.query.filter_by(business_id=business_id).count()
        
        today_calls = CallLog.query.filter(
            CallLog.business_id == business_id,
            func.date(CallLog.created_at) == today
        ).count()
        
        # Average duration (only for completed calls)  
        avg_duration_result = 0
        if hasattr(CallLog, 'call_duration'):
            avg_duration_result = db.session.query(
                func.avg(CallLog.call_duration)
            ).filter(
                CallLog.business_id == business_id,
                CallLog.call_status == 'completed',
                CallLog.call_duration.isnot(None)
            ).scalar()
        
        avg_duration = int(avg_duration_result) if avg_duration_result else 0
        
        # Answer rate calculation
        answered_calls = CallLog.query.filter_by(
            business_id=business_id,
            call_status='completed'
        ).count()
        
        answer_rate = 0
        if total_calls > 0:
            answer_rate = round((answered_calls / total_calls) * 100, 1)
        
        # Additional stats
        missed_calls = CallLog.query.filter_by(
            business_id=business_id,
            call_status='no-answer'
        ).count()
        
        calls_with_transcription = CallLog.query.filter(
            CallLog.business_id == business_id,
            CallLog.conversation_summary.isnot(None)
        ).count()
        
        stats = {
            'total_calls': total_calls,
            'today_calls': today_calls,
            'avg_duration': avg_duration,
            'answer_rate': answer_rate,
            'missed_calls': missed_calls,
            'answered_calls': answered_calls,
            'calls_with_transcription': calls_with_transcription,
            'updated_at': datetime.utcnow().isoformat()
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting calls stats: {e}")
        return jsonify({"error": "Failed to get stats"}), 500

# Helper functions for Hebrew translations
def get_status_hebrew(status):
    """Convert status to Hebrew"""
    status_map = {
        'new': 'חדש',
        'contacted': 'יצירת קשר',
        'qualified': 'מוכשר',
        'proposal': 'הצעה',
        'negotiation': 'משא ומתן',
        'closed_won': 'נסגר - הצליח',
        'closed_lost': 'נסגר - נכשל',
        'active': 'פעיל',
        'inactive': 'לא פעיל'
    }
    return status_map.get(status, status)

def get_source_hebrew(source):
    """Convert source to Hebrew"""
    source_map = {
        'website': 'אתר',
        'phone': 'טלפון',
        'whatsapp': 'WhatsApp',
        'referral': 'הפניה',
        'social': 'רשתות חברתיות',
        'email': 'אימייל',
        'walk_in': 'הגעה ישירה'
    }
    return source_map.get(source, source)

def get_call_status_hebrew(status):
    """Convert call status to Hebrew"""
    status_map = {
        'completed': 'הושלמה',
        'in-progress': 'בתהליך',
        'missed': 'לא נענתה',
        'busy': 'תפוס',
        'no-answer': 'לא ענה',
        'voicemail': 'תא קולי',
        'failed': 'נכשלה'
    }
    return status_map.get(status, status)

if __name__ == '__main__':
    print("✅ Advanced CRM API routes loaded successfully")