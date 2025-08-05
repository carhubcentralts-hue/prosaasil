"""
Signature API endpoints for React frontend - NO AUTH VERSION
API נקודות עבור חתימות דיגיטליות עם React - ללא authentication  
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Create Signature API Blueprint
signature_api_bp = Blueprint('signature_api', __name__, url_prefix='/api/signature')

@signature_api_bp.route('/signatures', methods=['GET'])
def get_signatures():
    """קבלת רשימת חתימות דיגיטליות"""
    try:
        signatures_data = [
            {
                'id': 1,
                'document_name': 'חוזה שירות - ישראל ישראלי',
                'signer_name': 'ישראל ישראלי',
                'signer_email': 'israel@example.com',
                'status': 'signed',
                'created_at': '2025-08-05T10:00:00Z',
                'signed_at': '2025-08-05T11:30:00Z'
            },
            {
                'id': 2,
                'document_name': 'הסכם תחזוקה - שרה כהן',
                'signer_name': 'שרה כהן',
                'signer_email': 'sarah@example.com',
                'status': 'pending',
                'created_at': '2025-08-05T12:00:00Z',
                'signed_at': None
            }
        ]
        
        stats = {
            'total_signatures': len(signatures_data),
            'signed': len([s for s in signatures_data if s['status'] == 'signed']),
            'pending': len([s for s in signatures_data if s['status'] == 'pending'])
        }
        
        return jsonify({
            'success': True,
            'signatures': signatures_data,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Signatures error: {e}")
        return jsonify({'error': 'שגיאה בקבלת חתימות'}), 500