"""
Invoice API endpoints for React frontend - NO AUTH VERSION
API נקודות עבור חשבוניות עם React - ללא authentication
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Create Invoice API Blueprint
invoice_api_bp = Blueprint('invoice_api', __name__, url_prefix='/api/invoice')

@invoice_api_bp.route('/invoices', methods=['GET'])
def get_invoices():
    """קבלת רשימת חשבוניות"""
    try:
        invoices_data = [
            {
                'id': 1,
                'invoice_number': 'INV-2025-001',
                'customer_name': 'ישראל ישראלי',
                'amount': 25000,
                'status': 'paid',
                'created_at': '2025-08-01T10:00:00Z',
                'paid_at': '2025-08-03T14:30:00Z',
                'due_date': '2025-08-31T23:59:59Z'
            },
            {
                'id': 2,
                'invoice_number': 'INV-2025-002',
                'customer_name': 'שרה כהן',
                'amount': 15000,
                'status': 'pending',
                'created_at': '2025-08-02T11:00:00Z',
                'paid_at': None,
                'due_date': '2025-08-30T23:59:59Z'
            },
            {
                'id': 3,
                'invoice_number': 'INV-2025-003',
                'customer_name': 'דוד לוי',
                'amount': 8000,
                'status': 'overdue',
                'created_at': '2025-07-15T12:00:00Z',
                'paid_at': None,
                'due_date': '2025-08-15T23:59:59Z'
            }
        ]
        
        return jsonify({
            'success': True,
            'invoices': invoices_data
        })
        
    except Exception as e:
        logger.error(f"Invoices error: {e}")
        return jsonify({'error': 'שגיאה בקבלת חשבוניות'}), 500