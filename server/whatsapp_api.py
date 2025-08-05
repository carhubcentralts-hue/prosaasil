"""
WhatsApp API endpoints for React frontend
API נקודות עבור מערכת WhatsApp עם React
"""
from flask import Blueprint, request, jsonify
from app import db
from models import Business, WhatsAppConversation, WhatsAppMessage
from auth import login_required, AuthService
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Create WhatsApp API Blueprint
whatsapp_api_bp = Blueprint('whatsapp_api', __name__, url_prefix='/api/whatsapp')

@whatsapp_api_bp.route('/conversations', methods=['GET'])
@login_required
def get_conversations():
    """קבלת רשימת שיחות WhatsApp עבור React"""
    try:
        current_user = AuthService.get_current_user()
        
        # בדיקת הרשאות WhatsApp
        if not current_user or not current_user.has_whatsapp_access():
            return jsonify({'error': 'אין הרשאה לגשת למערכת WhatsApp'}), 403
        
        # קבלת שיחות לפי העסק
        if current_user.role == 'admin':
            conversations = WhatsAppConversation.query.order_by(WhatsAppConversation.updated_at.desc()).all()
        else:
            conversations = WhatsAppConversation.query.filter_by(
                business_id=current_user.business_id
            ).order_by(WhatsAppConversation.updated_at.desc()).all()
        
        # סטטיסטיקות
        today = datetime.utcnow().date()
        today_messages = 0
        active_conversations = 0
        
        for conv in conversations:
            messages_today = WhatsAppMessage.query.filter(
                WhatsAppMessage.conversation_id == conv.id,
                WhatsAppMessage.created_at >= today
            ).count()
            today_messages += messages_today
            
            if conv.status == 'active':
                active_conversations += 1
        
        stats = {
            'total_conversations': len(conversations),
            'active_conversations': active_conversations,
            'today_messages': today_messages,
            'total_messages': WhatsAppMessage.query.count()
        }
        
        # המרת שיחות לפורמט JSON
        conversations_data = []
        for conv in conversations:
            conversations_data.append({
                'id': conv.id,
                'customer_name': conv.customer_name,
                'customer_number': conv.customer_number,
                'status': conv.status,
                'created_at': conv.created_at.isoformat() if conv.created_at else None,
                'updated_at': conv.updated_at.isoformat() if conv.updated_at else None
            })
        
        return jsonify({
            'success': True,
            'conversations': conversations_data,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting WhatsApp conversations: {e}")
        return jsonify({'error': 'שגיאה בטעינת שיחות WhatsApp'}), 500

@whatsapp_api_bp.route('/conversation/<int:conversation_id>/messages', methods=['GET'])
@login_required
def get_conversation_messages(conversation_id):
    """קבלת הודעות של שיחה ספציפית"""
    try:
        current_user = AuthService.get_current_user()
        
        if not current_user or not current_user.has_whatsapp_access():
            return jsonify({'error': 'אין הרשאה לגשת למערכת WhatsApp'}), 403
        
        # בדיקת הרשאה לשיחה
        conversation = WhatsAppConversation.query.get_or_404(conversation_id)
        
        if (current_user.role != 'admin' and 
            conversation.business_id != current_user.business_id):
            return jsonify({'error': 'אין הרשאה לגשת לשיחה זו'}), 403
        
        # קבלת הודעות
        messages = WhatsAppMessage.query.filter_by(
            conversation_id=conversation_id
        ).order_by(WhatsAppMessage.created_at.asc()).all()
        
        messages_data = []
        for msg in messages:
            messages_data.append({
                'id': msg.id,
                'from_number': msg.from_number,
                'to_number': msg.to_number,
                'message_body': msg.message_body,
                'direction': msg.direction,
                'status': msg.status,
                'created_at': msg.created_at.isoformat() if msg.created_at else None,
                'media_url': msg.media_url,
                'media_type': msg.media_type
            })
        
        return jsonify({
            'success': True,
            'conversation': {
                'id': conversation.id,
                'customer_name': conversation.customer_name,
                'customer_number': conversation.customer_number,
                'status': conversation.status
            },
            'messages': messages_data
        })
        
    except Exception as e:
        logger.error(f"Error getting conversation messages: {e}")
        return jsonify({'error': 'שגיאה בטעינת הודעות'}), 500

@whatsapp_api_bp.route('/send_message', methods=['POST'])
@login_required
def send_message():
    """שליחת הודעת WhatsApp חדשה"""
    try:
        current_user = AuthService.get_current_user()
        
        if not current_user or not current_user.has_whatsapp_access():
            return jsonify({'error': 'אין הרשאה לגשת למערכת WhatsApp'}), 403
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'נתונים לא תקינים'}), 400
        
        to_number = data.get('to_number')
        message_body = data.get('message_body')
        
        if not to_number or not message_body:
            return jsonify({'error': 'מספר טלפון והודעה נדרשים'}), 400
        
        # כרגע נחזיר הצלחה - יש לחבר לשירות WhatsApp אמיתי
        return jsonify({
            'success': True,
            'message': 'הודעה נשלחה בהצלחה',
            'message_id': f'msg_{datetime.now().timestamp()}'
        })
        
    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {e}")
        return jsonify({'error': 'שגיאה בשליחת הודעה'}), 500