"""
WhatsApp API endpoints for React frontend - NO AUTH VERSION
API נקודות עבור WhatsApp עם React - ללא authentication
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Create WhatsApp API Blueprint
whatsapp_api_bp = Blueprint('whatsapp_api', __name__, url_prefix='/api/whatsapp')

@whatsapp_api_bp.route('/conversations', methods=['GET'])
def get_conversations():
    """קבלת רשימת שיחות WhatsApp"""
    try:
        conversations_data = [
            {
                'id': 1,
                'customer_number': '+972501234567',
                'customer_name': 'ישראל ישראלי',
                'status': 'active',
                'last_message': 'מתי תוכלו להתקשר?',
                'last_message_time': '2025-08-05T15:30:00Z',
                'message_count': 5
            },
            {
                'id': 2,
                'customer_number': '+972529876543',
                'customer_name': 'שרה כהן',
                'status': 'pending',
                'last_message': 'תודה על המידע',
                'last_message_time': '2025-08-05T14:20:00Z',
                'message_count': 3
            }
        ]
        
        return jsonify({
            'success': True,
            'conversations': conversations_data
        })
        
    except Exception as e:
        logger.error(f"WhatsApp conversations error: {e}")
        return jsonify({'error': 'שגיאה בקבלת שיחות WhatsApp'}), 500

@whatsapp_api_bp.route('/analytics', methods=['GET'])
def get_whatsapp_analytics():
    """אנליטיקס WhatsApp"""
    try:
        analytics_data = {
            'total_conversations': 45,
            'active_conversations': 12,
            'messages_today': 23,
            'response_rate': 85.5
        }
        
        return jsonify({
            'success': True,
            'analytics': analytics_data
        })
        
    except Exception as e:
        logger.error(f"WhatsApp analytics error: {e}")
        return jsonify({'error': 'שגיאה באנליטיקס WhatsApp'}), 500