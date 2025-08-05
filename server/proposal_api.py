"""
Proposal API endpoints for React frontend - NO AUTH VERSION
API נקודות עבור הצעות מחיר עם React - ללא authentication
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Create Proposal API Blueprint
proposal_api_bp = Blueprint('proposal_api', __name__, url_prefix='/api/proposal')

@proposal_api_bp.route('/proposals', methods=['GET'])
def get_proposals():
    """קבלת רשימת הצעות מחיר"""
    try:
        proposals_data = [
            {
                'id': 1,
                'title': 'הצעת מחיר - מערכת CRM',
                'customer_name': 'ישראל ישראלי',
                'amount': 25000,
                'status': 'pending',
                'created_at': '2025-08-05T10:00:00Z',
                'valid_until': '2025-08-20T23:59:59Z'
            },
            {
                'id': 2,
                'title': 'הצעת מחיר - אתר אינטרנט',
                'customer_name': 'שרה כהן',
                'amount': 15000,
                'status': 'accepted',
                'created_at': '2025-08-04T14:00:00Z',
                'accepted_at': '2025-08-05T09:30:00Z'
            },
            {
                'id': 3,
                'title': 'הצעת מחיר - יעוץ עסקי',
                'customer_name': 'דוד לוי',
                'amount': 8000,
                'status': 'rejected',
                'created_at': '2025-08-03T16:00:00Z',
                'rejected_at': '2025-08-04T12:00:00Z'
            }
        ]
        
        return jsonify({
            'success': True,
            'proposals': proposals_data
        })
        
    except Exception as e:
        logger.error(f"Proposals error: {e}")
        return jsonify({'error': 'שגיאה בקבלת הצעות מחיר'}), 500