"""
WhatsApp Blueprint - מודול WhatsApp כ-Blueprint נפרד
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from app import db
from models import Business, WhatsAppConversation, WhatsAppMessage
from auth import login_required
from whatsapp_service import WhatsAppService
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Create WhatsApp Blueprint
whatsapp_bp = Blueprint('whatsapp', __name__, url_prefix='/whatsapp')

# DISABLED: Old Flask template route - React handles frontend now
# @whatsapp_bp.route('/')
# @login_required
def whatsapp_dashboard_old_disabled():
    """דשבורד WhatsApp ראשי"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        # בדיקת הרשאות WhatsApp
        if not current_user or not current_user.has_whatsapp_access():
            return jsonify({'error': 'אין הרשאה לגשת למערכת WhatsApp'}), 403
        
        # קבלת שיחות לפי העסק
        if current_user and current_user.role == 'admin':
            conversations = WhatsAppConversation.query.order_by(WhatsAppConversation.updated_at.desc()).all()
        elif current_user and current_user.business_id:
            conversations = WhatsAppConversation.query.filter_by(
                business_id=current_user.business_id
            ).order_by(WhatsAppConversation.updated_at.desc()).all()
        else:
            conversations = []
        
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
        
        return render_template('whatsapp.html', 
                             conversations=conversations,
                             stats=stats)
    except Exception as e:
        logger.error(f"Error in WhatsApp dashboard: {e}")
        return jsonify({'error': 'שגיאה בטעינת דשבורד WhatsApp'}), 500

@whatsapp_bp.route('/conversation/<int:conversation_id>')
@login_required
def view_conversation(conversation_id):
    """צפייה בשיחת WhatsApp"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        conversation = WhatsAppConversation.query.get_or_404(conversation_id)
        
        # בדיקת הרשאות
        if current_user.role != 'admin' and conversation.business_id != current_user.business_id:
            flash('אין לך הרשאה לצפות בשיחה זו', 'error')
            return redirect(url_for('whatsapp.whatsapp_dashboard'))
        
        # קבלת הודעות השיחה
        messages = WhatsAppMessage.query.filter_by(
            conversation_id=conversation_id
        ).order_by(WhatsAppMessage.created_at.asc()).all()
        
        return render_template('whatsapp_conversation.html', 
                             conversation=conversation, 
                             messages=messages)
        
    except Exception as e:
        logger.error(f"Error viewing conversation {conversation_id}: {e}")
        flash('שגיאה בטעינת השיחה', 'error')
        return redirect(url_for('whatsapp.whatsapp_dashboard'))

@whatsapp_bp.route('/send_message', methods=['POST'])
@login_required
def send_message():
    """שליחת הודעת WhatsApp"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        if not current_user.has_whatsapp_access():
            return jsonify({'success': False, 'message': 'אין הרשאה'})
        
        to_number = request.json.get('to_number')
        message_text = request.json.get('message')
        conversation_id = request.json.get('conversation_id')
        
        if not to_number or not message_text:
            return jsonify({'success': False, 'message': 'מספר טלפון והודעה הם שדות חובה'})
        
        # קביעת business_id
        business_id = current_user.business_id if current_user.role != 'admin' else request.json.get('business_id')
        
        # שליחת הודעה דרך שירות WhatsApp
        whatsapp_service = WhatsAppService()
        result = whatsapp_service.send_whatsapp_message(
            to_number=to_number,
            message_text=message_text,
            business_id=business_id
        )
        
        if result.get('success'):
            logger.info(f"✅ WhatsApp message sent to {to_number}")
            return jsonify({'success': True, 'message': 'ההודעה נשלחה בהצלחה'})
        else:
            logger.error(f"❌ Failed to send WhatsApp message to {to_number}")
            return jsonify({'success': False, 'message': 'שגיאה בשליחת ההודעה'})
            
    except Exception as e:
        logger.error(f"❌ Error sending WhatsApp message: {e}")
        return jsonify({'success': False, 'message': 'שגיאה בשליחת ההודעה'})

@whatsapp_bp.route('/webhook', methods=['POST'])
def webhook():
    """Webhook לקבלת הודעות WhatsApp נכנסות"""
    try:
        data = request.json or request.form.to_dict()
        logger.info(f"📥 WhatsApp webhook received: {data}")
        
        # עיבוד הודעה נכנסת
        message_sid = data.get('MessageSid')
        from_number = data.get('From', '').replace('whatsapp:', '')
        to_number = data.get('To', '').replace('whatsapp:', '')
        message_body = data.get('Body', '')
        
        if not message_sid or not from_number:
            logger.warning("❌ Invalid WhatsApp webhook data")
            return jsonify({'status': 'error', 'message': 'Invalid data'}), 400
        
        # חיפוש עסק לפי מספר WhatsApp
        business = Business.query.filter_by(whatsapp_number=to_number).first()
        if not business:
            # נסה למצוא עסק ברירת מחדל
            business = Business.query.filter_by(is_active=True).first()
        
        if not business:
            logger.warning(f"❌ No business found for WhatsApp number {to_number}")
            return jsonify({'status': 'error', 'message': 'Business not found'}), 404
        
        # קבלת או יצירת שיחה
        conversation = WhatsAppConversation.query.filter_by(
            customer_number=from_number,
            business_id=business.id
        ).first()
        
        if not conversation:
            conversation = WhatsAppConversation(
                customer_number=from_number,
                business_id=business.id,
                status='active'
            )
            db.session.add(conversation)
            db.session.flush()  # כדי לקבל את conversation.id
        
        # שמירת ההודעה
        message = WhatsAppMessage(
            conversation_id=conversation.id,
            message_sid=message_sid,
            from_number=from_number,
            to_number=to_number,
            message_body=message_body,
            direction='inbound',
            business_id=business.id
        )
        
        db.session.add(message)
        conversation.updated_at = datetime.utcnow()
        
        # עיבוד AI אוטומטי (אם מופעל)
        try:
            from ai_service import AIService
            ai_service = AIService()
            
            # יצירת תגובה אוטומטית
            ai_response = ai_service.process_whatsapp_message(
                message_text=message_body,
                customer_number=from_number,
                business=business
            )
            
            if ai_response:
                # שליחת תגובה אוטומטית
                whatsapp_service = WhatsAppService()
                whatsapp_service.send_whatsapp_message(
                    to_number=from_number,
                    message_text=ai_response,
                    business_id=business.id
                )
                
        except Exception as e:
            logger.warning(f"⚠️ AI processing failed: {e}")
        
        db.session.commit()
        logger.info(f"✅ WhatsApp message processed: {message_sid}")
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"❌ WhatsApp webhook error: {e}")
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@whatsapp_bp.route('/status/<message_sid>', methods=['POST'])
def status_callback(message_sid):
    """Callback לסטטוס הודעות WhatsApp"""
    try:
        data = request.form.to_dict()
        logger.info(f"📊 WhatsApp status update for {message_sid}: {data}")
        
        message_status = data.get('MessageStatus')
        error_code = data.get('ErrorCode')
        error_message = data.get('ErrorMessage')
        
        # עדכון סטטוס ההודעה במסד הנתונים
        message = WhatsAppMessage.query.filter_by(message_sid=message_sid).first()
        if message:
            message.status = message_status
            if error_code:
                message.error_code = error_code
                message.error_message = error_message
            
            db.session.commit()
            logger.info(f"✅ Message {message_sid} status updated to {message_status}")
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"❌ WhatsApp status callback error: {e}")
        return jsonify({'status': 'error'}), 500

@whatsapp_bp.route('/api/conversations')
@login_required
def api_conversations():
    """API לקבלת רשימת שיחות WhatsApp"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        if not current_user.has_whatsapp_access():
            return jsonify({'error': 'אין הרשאה'}), 403
        
        # קבלת שיחות לפי העסק
        if current_user.role == 'admin':
            conversations = WhatsAppConversation.query.order_by(
                WhatsAppConversation.updated_at.desc()
            ).limit(50).all()
        else:
            conversations = WhatsAppConversation.query.filter_by(
                business_id=current_user.business_id
            ).order_by(WhatsAppConversation.updated_at.desc()).limit(50).all()
        
        return jsonify([{
            'id': c.id,
            'customer_number': c.customer_number,
            'customer_name': c.customer_name,
            'status': c.status,
            'created_at': c.created_at.isoformat() if c.created_at else None,
            'updated_at': c.updated_at.isoformat() if c.updated_at else None,
            'message_count': len(c.messages) if hasattr(c, 'messages') else 0
        } for c in conversations])
        
    except Exception as e:
        logger.error(f"Error in API conversations: {e}")
        return jsonify({'error': 'שגיאה בקבלת נתוני שיחות'}), 500

@whatsapp_bp.route('/api/stats')
@login_required
def api_stats():
    """API לסטטיסטיקות WhatsApp"""
    try:
        from auth import AuthService
        current_user = AuthService.get_current_user()
        
        if not current_user.has_whatsapp_access():
            return jsonify({'error': 'אין הרשאה'}), 403
        
        # קבלת נתונים לפי העסק
        if current_user.role == 'admin':
            conversations = WhatsAppConversation.query.all()
            messages = WhatsAppMessage.query.all()
        else:
            conversations = WhatsAppConversation.query.filter_by(
                business_id=current_user.business_id
            ).all()
            messages = WhatsAppMessage.query.filter_by(
                business_id=current_user.business_id
            ).all()
        
        today = datetime.utcnow().date()
        
        stats = {
            'total_conversations': len(conversations),
            'active_conversations': len([c for c in conversations if c.status == 'active']),
            'total_messages': len(messages),
            'today_messages': len([m for m in messages if m.created_at.date() == today]),
            'inbound_messages': len([m for m in messages if m.direction == 'inbound']),
            'outbound_messages': len([m for m in messages if m.direction == 'outbound'])
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error in API stats: {e}")
        return jsonify({'error': 'שגיאה בקבלת סטטיסטיקות'}), 500