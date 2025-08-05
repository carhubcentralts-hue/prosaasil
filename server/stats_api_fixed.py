"""
Stats API endpoints for React frontend - NO AUTH VERSION  
API נקודות עבור סטטיסטיקות עם React - ללא authentication
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Create Stats API Blueprint
stats_api_bp = Blueprint('stats_api', __name__, url_prefix='/api/stats')

@stats_api_bp.route('/overview', methods=['GET'])
def get_overview_stats():
    """סטטיסטיקות כלליות עבור React - ללא authentication"""
    try:
        # Return mock statistics for testing
        stats_data = {
            'customers': {
                'total': 150,
                'active': 125,
                'new_today': 5
            },
            'calls': {
                'today': 23,
                'this_week': 156,
                'answered': 19
            },
            'whatsapp': {
                'active': 12,
                'total_conversations': 45,
                'new_messages': 8
            },
            'tasks': {
                'pending': 7,
                'completed_today': 12,
                'overdue': 2
            },
            'financial': {
                'invoices': {
                    'paid_amount': 125000,
                    'pending_amount': 45000,
                    'total_this_month': 170000
                },
                'proposals': {
                    'total_value': 89000,
                    'pending_count': 5,
                    'accepted_count': 3
                }
            }
        }
        
        return jsonify({
            'success': True,
            'stats': stats_data
        })
        
    except Exception as e:
        logger.error(f"Stats overview error: {e}")
        return jsonify({'error': 'שגיאה בקבלת סטטיסטיקות'}), 500

@stats_api_bp.route('/trends', methods=['GET'])
def get_trends():
    """מגמות וטרנדים"""
    try:
        trends_data = {
            'customers_growth': 15.5,
            'calls_trend': 8.2,
            'whatsapp_growth': 22.1,
            'revenue_change': 12.3
        }
        
        return jsonify({
            'success': True,
            'trends': trends_data
        })
        
    except Exception as e:
        logger.error(f"Stats trends error: {e}")
        return jsonify({'error': 'שגיאה בקבלת מגמות'}), 500