from flask import Blueprint, jsonify, session
from .auth import login_required
from .models import db, Customer, CallLog

business_stats_bp = Blueprint('business_stats', __name__)

@business_stats_bp.route('/api/business/stats', methods=['GET'])
@login_required
def get_business_stats():
    try:
        business_id = session.get('business_id')
        if not business_id:
            return jsonify({'error': 'No business associated'}), 400
        
        # Get business-specific stats
        total_customers = Customer.query.filter_by(business_id=business_id).count()
        total_calls = CallLog.query.filter_by(business_id=business_id).count()
        
        # Today's calls (simplified - you can add date filtering)
        today_calls = CallLog.query.filter_by(business_id=business_id).count()
        
        # WhatsApp messages (placeholder)
        whatsapp_messages = 0
        
        return jsonify({
            'totalCustomers': total_customers,
            'totalCalls': total_calls,
            'todayCalls': today_calls,
            'whatsappMessages': whatsapp_messages
        })
    except Exception as e:
        return jsonify({'error': 'Failed to fetch business stats'}), 500