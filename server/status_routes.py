from flask import Blueprint, jsonify
import logging
import os
import requests
from datetime import datetime

# הגדרת logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# יצירת Blueprint עבור status
status_bp = Blueprint('status', __name__, url_prefix='/api')

@status_bp.route('/status', methods=['GET'])
def get_system_status():
    """קבלת סטטוס מערכות: GPT, Twilio, Baileys"""
    try:
        status = {
            'timestamp': datetime.now().isoformat(),
            'systems': {
                'gpt': check_openai_status(),
                'twilio': check_twilio_status(), 
                'baileys': check_baileys_status()
            }
        }
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({'error': 'Failed to get status'}), 500

def check_openai_status():
    """בדיקת סטטוס OpenAI GPT"""
    try:
        openai_key = os.environ.get('OPENAI_API_KEY')
        if not openai_key:
            return {
                'status': 'error',
                'message': 'OpenAI API key not configured',
                'last_check': datetime.now().isoformat()
            }
        
        # בדיקה פשוטה - אם יש מפתח נחשיב שהשירות פעיל
        return {
            'status': 'operational',
            'message': 'OpenAI GPT service available',
            'last_check': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"OpenAI status check failed: {e}")
        return {
            'status': 'error', 
            'message': f'Status check failed: {str(e)}',
            'last_check': datetime.now().isoformat()
        }

def check_twilio_status():
    """בדיקת סטטוס Twilio"""
    try:
        twilio_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        twilio_token = os.environ.get('TWILIO_AUTH_TOKEN')
        
        if not twilio_sid or not twilio_token:
            return {
                'status': 'error',
                'message': 'Twilio credentials not configured',
                'last_check': datetime.now().isoformat()
            }
        
        # בדיקה פשוטה - אם יש אישורים נחשיב שהשירות פעיל
        return {
            'status': 'operational',
            'message': 'Twilio service available',
            'last_check': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Twilio status check failed: {e}")
        return {
            'status': 'error',
            'message': f'Status check failed: {str(e)}',
            'last_check': datetime.now().isoformat()
        }

def check_baileys_status():
    """בדיקת סטטוס Baileys WhatsApp"""
    try:
        # בדיקה אם קיים תיקיית auth
        auth_dir = os.path.join(os.path.dirname(__file__), 'baileys_auth_info')
        
        if os.path.exists(auth_dir):
            return {
                'status': 'operational',
                'message': 'Baileys WhatsApp service available',
                'last_check': datetime.now().isoformat()
            }
        else:
            return {
                'status': 'warning',
                'message': 'Baileys not connected - QR scan needed',
                'last_check': datetime.now().isoformat()
            }
        
    except Exception as e:
        logger.error(f"Baileys status check failed: {e}")
        return {
            'status': 'error',
            'message': f'Status check failed: {str(e)}',
            'last_check': datetime.now().isoformat()
        }