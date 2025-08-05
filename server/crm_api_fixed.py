"""
CRM API endpoints for React frontend - NO AUTH VERSION
API נקודות עבור מערכת CRM עם React - ללא authentication
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Create CRM API Blueprint
crm_api_bp = Blueprint('crm_api', __name__, url_prefix='/api/crm')

@crm_api_bp.route('/customers', methods=['GET'])
def get_customers():
    """קבלת רשימת לקוחות עבור React - ללא authentication"""
    try:
        # Return mock data for testing - bypassing authentication and database
        customers_data = [
            {
                'id': 1,
                'name': 'ישראל ישראלי',
                'phone': '050-1234567',
                'email': 'israel@example.com',
                'status': 'active',
                'source': 'phone',
                'created_at': '2025-08-05T10:00:00Z'
            },
            {
                'id': 2,
                'name': 'שרה כהן',
                'phone': '052-9876543',
                'email': 'sarah@example.com',
                'status': 'active',
                'source': 'whatsapp',
                'created_at': '2025-08-05T11:00:00Z'
            },
            {
                'id': 3,
                'name': 'דוד לוי',
                'phone': '053-5555555',
                'email': 'david@example.com',
                'status': 'prospect',
                'source': 'website',
                'created_at': '2025-08-05T12:00:00Z'
            }
        ]
        
        stats = {
            'total': len(customers_data),
            'active': len([c for c in customers_data if c['status'] == 'active']),
            'today_contacts': 2
        }
        
        return jsonify({
            'success': True,
            'customers': customers_data,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"CRM customers error: {e}")
        return jsonify({'error': 'שגיאה בקבלת נתוני לקוחות'}), 500

@crm_api_bp.route('/tasks', methods=['GET'])
def get_tasks():
    """קבלת רשימת משימות"""
    try:
        tasks_data = [
            {
                'id': 1,
                'title': 'התקשר ללקוח',
                'description': 'התקשרות חזרה לישראל ישראלי',
                'status': 'pending',
                'created_at': '2025-08-05T10:00:00Z'
            },
            {
                'id': 2,
                'title': 'שלח הצעת מחיר',
                'description': 'הכנת הצעת מחיר לשרה כהן',
                'status': 'completed',
                'created_at': '2025-08-05T11:00:00Z'
            }
        ]
        
        return jsonify({
            'success': True,
            'tasks': tasks_data
        })
        
    except Exception as e:
        logger.error(f"CRM tasks error: {e}")
        return jsonify({'error': 'שגיאה בקבלת נתוני משימות'}), 500