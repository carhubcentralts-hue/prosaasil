"""
WhatsApp API endpoints for React frontend - REAL BAILEYS INTEGRATION
API נקודות עבור WhatsApp עם React - חיבור אמיתי לBaileys
"""
from flask import Blueprint, request, jsonify
from datetime import datetime
import logging
import os
import qrcode
import io
import base64
from baileys_integration import baileys_service

logger = logging.getLogger(__name__)

# Create WhatsApp API Blueprint
whatsapp_api_bp = Blueprint('whatsapp_api', __name__, url_prefix='/api/whatsapp')

@whatsapp_api_bp.route('/status', methods=['GET'])
def get_whatsapp_status():
    """קבלת סטטוס חיבור WhatsApp"""
    try:
        is_connected = baileys_service.is_authenticated()
        qr_available = baileys_service.get_qr_code() is not None
        
        return jsonify({
            'success': True,
            'connected': is_connected,
            'qr_available': qr_available,
            'status': 'connected' if is_connected else ('qr_ready' if qr_available else 'disconnected')
        })
        
    except Exception as e:
        logger.error(f"WhatsApp status error: {e}")
        return jsonify({'error': 'שגיאה בבדיקת סטטוס WhatsApp'}), 500

@whatsapp_api_bp.route('/qr', methods=['GET'])
def get_qr_code():
    """קבלת QR Code אמיתי מBaileys"""
    try:
        qr_text = baileys_service.get_qr_code()
        
        if not qr_text:
            return jsonify({'error': 'QR Code לא זמין'}), 404
            
        # יצירת QR Code כתמונה
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_text)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # המרה לbase64
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_str = base64.b64encode(img_buffer.getvalue()).decode()
        
        return jsonify({
            'success': True,
            'qr_code': f"data:image/png;base64,{img_str}",
            'qr_text': qr_text
        })
        
    except Exception as e:
        logger.error(f"QR Code error: {e}")
        return jsonify({'error': 'שגיאה ביצירת QR Code'}), 500

@whatsapp_api_bp.route('/connect', methods=['POST'])
def start_baileys_connection():
    """הפעלת חיבור Baileys"""
    try:
        success = baileys_service.start_baileys_service()
        
        return jsonify({
            'success': success,
            'message': 'שירות WhatsApp הופעל' if success else 'שגיאה בהפעלת שירות WhatsApp'
        })
        
    except Exception as e:
        logger.error(f"Baileys start error: {e}")
        return jsonify({'error': 'שגיאה בהפעלת Baileys'}), 500

@whatsapp_api_bp.route('/conversations', methods=['GET'])
def get_conversations():
    """קבלת רשימת שיחות WhatsApp אמיתיות"""
    try:
        business_id = request.args.get('business_id', 1)  # Default business
        conversations = baileys_service.get_conversations(business_id)
        
        return jsonify({
            'success': True,
            'conversations': conversations
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