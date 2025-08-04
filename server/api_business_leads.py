from flask import Blueprint, request, jsonify
from server.auth_middleware import require_auth
import json

business_leads_bp = Blueprint('business_leads', __name__)

@business_leads_bp.route('/api/business/leads', methods=['GET'])
@require_auth
def get_business_leads():
    """Get leads for a specific business"""
    try:
        business_id = request.args.get('business_id')
        if not business_id:
            return jsonify({'error': 'Business ID is required'}), 400
            
        # Mock data for business leads - replace with actual database query
        mock_leads = [
            {
                'id': 1,
                'name': 'יוסי כהן',
                'phone': '050-1234567',
                'email': 'yossi@example.com',
                'source': 'WhatsApp',
                'status': 'active',
                'created_at': '2024-08-01T12:00:00Z',
                'business_id': int(business_id)
            },
            {
                'id': 2,
                'name': 'רחל לוי',
                'phone': '052-7654321',
                'email': 'rachel@example.com',
                'source': 'טלפון',
                'status': 'pending',
                'created_at': '2024-08-02T14:30:00Z',
                'business_id': int(business_id)
            },
            {
                'id': 3,
                'name': 'דוד ישראלי',
                'phone': '054-9876543',
                'email': 'david@example.com',
                'source': 'אתר',
                'status': 'completed',
                'created_at': '2024-08-03T09:15:00Z',
                'business_id': int(business_id)
            }
        ]
        
        return jsonify(mock_leads)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@business_leads_bp.route('/api/business/stats', methods=['GET'])
@require_auth
def get_business_stats():
    """Get CRM stats for a specific business"""
    try:
        business_id = request.args.get('business_id')
        if not business_id:
            return jsonify({'error': 'Business ID is required'}), 400
            
        # Mock stats data - replace with actual database query
        mock_stats = {
            'total_leads': 15,
            'active_leads': 8,
            'converted_leads': 5,
            'pending_leads': 2,
            'today_leads': 3,
            'this_week_leads': 7,
            'this_month_leads': 15,
            'conversion_rate': 33.3
        }
        
        return jsonify(mock_stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500