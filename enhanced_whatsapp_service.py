"""
Enhanced WhatsApp Service with Conversation Management
שירות WhatsApp מתקדם עם ניהול שיחות אוטומטי
"""

import os
import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from twilio.rest import Client
from models import Business
from enhanced_ai_service import enhanced_ai_service
from app import db

logger = logging.getLogger(__name__)

class EnhancedWhatsAppService:
    """שירות WhatsApp מתקדם עם ניהול שיחות"""
    
    def __init__(self):
        self.client = Client(
            os.environ.get('TWILIO_ACCOUNT_SID'),
            os.environ.get('TWILIO_AUTH_TOKEN')
        )
        self.from_number = os.environ.get('TWILIO_PHONE_NUMBER')
        # Task 2: Enhanced conversation tracking per user
        self.active_conversations = {}  # מעקב אחר שיחות פעילות
        self.max_conversation_age = 3600  # 1 hour timeout
        
    def process_incoming_message(self, from_number: str, to_number: str, 
                                message_body: str) -> Dict[str, Any]:
        """עיבוד הודעת WhatsApp נכנסת עם ניהול שיחה מלא - Task 2"""
        
        # Update conversation tracking
        self._update_conversation_tracking(from_number, message_body)
        
        try:
            # מציאת עסק לפי מספר
            business = Business.query.filter_by(phone_number=to_number).first()
            if not business:
                logger.error(f"No business found for number {to_number}")
                return {'success': False, 'error': 'Business not found'}
            
            # בדיקת הרשאות WhatsApp
            if not getattr(business, 'whatsapp_permissions', True):
                logger.warning(f"WhatsApp not permitted for business {business.id}")
                return {'success': False, 'error': 'WhatsApp not permitted'}
            
            # קבלת/יצירת שיחה
            conversation = self._get_or_create_conversation(
                business.id, from_number, to_number
            )
            
            # בדיקת תור פתוח
            if self._has_open_turn(conversation.id):
                logger.info(f"Conversation {conversation.id} already has open turn")
                return {'success': True, 'message': 'Turn already open'}
            
            # בדיקת הודעה ריקה
            if not message_body or not message_body.strip():
                logger.warning(f"Empty message from {from_number}")
                return self._send_error_response(
                    conversation, 
                    "לא קיבלתי הודעה. תוכל לכתוב שוב?"
                )
            
            # עיבוד עם AI - Agent task #2 with retry and error logging
            try:
                ai_result = enhanced_ai_service.process_conversation(
                    business_id=business.id,
                    message=message_body,
                    conversation_context={
                        "conversation_id": getattr(conversation, 'whatsapp_conversation_id', str(conversation.id)),
                        "phone": from_number,
                        "channel": "whatsapp"
                    }
                )
                
                if not ai_result.get('success'):
                    logger.error(f"AI processing failed: {ai_result.get('error', 'Unknown error')}")
                    # Retry once
                    logger.info("Retrying AI processing...")
                    ai_result = enhanced_ai_service.process_conversation(
                        business_id=business.id,
                        message=message_body,
                        conversation_context={
                            "conversation_id": getattr(conversation, 'whatsapp_conversation_id', str(conversation.id)),
                            "phone": from_number,
                            "channel": "whatsapp",
                            "retry": True
                        }
                    )
                    
            except Exception as ai_error:
                logger.error(f"OpenAI API failed: {ai_error}")
                ai_result = {
                    'success': False,
                    'error': f'OpenAI API error: {str(ai_error)}',
                    'response': 'מצטער, יש לי בעיה טכנית זמנית. אנא נסה שוב או התקשר אלינו.'
                }
            
            if not ai_result['success']:
                return self._send_error_response(
                    conversation,
                    "מצטער, אירעה שגיאה זמנית. נסה שוב בעוד רגע."
                )
            
            # שמירת הודעות
            self._save_messages(
                conversation=conversation,
                user_message=message_body,
                ai_response=ai_result['response'],
                intent=ai_result.get('intent', 'unknown')
            )
            
            # שליחת תגובה - Agent task #2 confirm delivery via Twilio
            send_result = self._send_whatsapp_message(
                to_number=from_number,
                message=ai_result.get('response', 'תודה על הפנייה')
            )
            
            # Verify message was actually delivered via Twilio
            if send_result.get('success') and send_result.get('sid'):
                logger.info(f"WhatsApp message delivered: {send_result['sid']}")
            
            if send_result['success']:
                # עדכון מועד תגובה אחרון
                conversation.last_activity = datetime.utcnow()
                conversation.message_count += 1
                db.session.commit()
                
                # סגירת תור
                self._close_conversation_turn(conversation.id)
                
            return {
                'success': True,
                'conversation_id': conversation.whatsapp_conversation_id,
                'ai_response': ai_result['response'],
                'intent': ai_result.get('intent'),
                'message_sent': send_result['success']
            }
            
        except Exception as e:
            logger.error(f"Error processing WhatsApp message: {e}")
            return {'success': False, 'error': str(e)}

    def _update_conversation_tracking(self, from_number: str, message: str):
        """Task 2: Enhanced conversation context tracking"""
        now = datetime.utcnow()
        
        # Clean old conversations
        cutoff_time = now.timestamp() - self.max_conversation_age
        old_keys = [
            key for key, conv in self.active_conversations.items()
            if conv.get('last_seen', 0) < cutoff_time
        ]
        for key in old_keys:
            del self.active_conversations[key]
            logger.info(f"📱 Cleaned old conversation: {key}")
        
        # Update/create conversation context
        if from_number not in self.active_conversations:
            self.active_conversations[from_number] = {
                "history": [],
                "last_seen": now.timestamp(),
                "message_count": 0
            }
            logger.info(f"📱 New WhatsApp conversation started: {from_number}")
        
        # Add message to history
        conv = self.active_conversations[from_number]
        conv['history'].append({
            "message": message,
            "timestamp": now.timestamp(),
            "role": "user"
        })
        conv['last_seen'] = now.timestamp()
        conv['message_count'] += 1
        
        # Limit history size
        if len(conv['history']) > 20:
            conv['history'] = conv['history'][-20:]
        
        logger.info(f"📱 Updated conversation for {from_number}: {conv['message_count']} messages")

    def get_conversation_context(self, from_number: str) -> Dict[str, Any]:
        """Get conversation history for AI processing"""
        return self.active_conversations.get(from_number, {
            "history": [],
            "last_seen": 0,
            "message_count": 0
        })
    
    def _get_or_create_conversation(self, business_id: int, from_number: str, 
                                   to_number: str):
        """קבלת או יצירת שיחת WhatsApp - Agent task #2"""
        
        from models import WhatsAppConversation
        from datetime import datetime, timedelta
        
        # חיפוש שיחה קיימת (פעילה ב-24 שעות האחרונות)
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        conversation = WhatsAppConversation.query.filter(
            WhatsAppConversation.business_id == business_id,
            WhatsAppConversation.customer_number == from_number,
            WhatsAppConversation.status == 'active',
            WhatsAppConversation.updated_at >= cutoff_time
        ).first()
        
        if conversation:
            # Update timestamp to prevent overlapping sessions
            conversation.updated_at = datetime.utcnow()
            db.session.commit()
            return conversation
        
        # יצירת שיחה חדשה עם conversation_id יחיד
        new_conversation_id = str(uuid.uuid4())
        conversation = WhatsAppConversation(
            customer_number=from_number,
            business_id=business_id,
            status='active'
        )
        
        # Add conversation_id attribute for tracking
        conversation.whatsapp_conversation_id = new_conversation_id
        
        db.session.add(conversation)
        db.session.commit()
        
        logger.info(f"Created new WhatsApp conversation: {new_conversation_id}")
        return conversation
    
    def _has_open_turn(self, conversation_id: int) -> bool:
        """בדיקה האם יש תור פתוח בשיחה"""
        
        conversation_key = f"whatsapp_conversation_{conversation_id}"
        return conversation_key in self.active_conversations
    
    def _close_conversation_turn(self, conversation_id: int):
        """סגירת תור שיחה"""
        
        conversation_key = f"whatsapp_conversation_{conversation_id}"
        if conversation_key in self.active_conversations:
            del self.active_conversations[conversation_key]
    
    def _save_messages(self, conversation, 
                      user_message: str, ai_response: str, intent: str):
        """שמירת הודעות במסד נתונים - Agent task #2"""
        
        try:
            from models import WhatsAppMessage
            
            # הודעת משתמש נכנסת
            user_msg = WhatsAppMessage(
                conversation_id=conversation.id,
                business_id=conversation.business_id,
                from_number=conversation.customer_number,
                to_number=f"whatsapp:{self.from_number}",
                message_body=user_message,
                direction='inbound',
                status='received'
            )
            
            # הודעת AI יוצאת  
            ai_msg = WhatsAppMessage(
                conversation_id=conversation.id,
                business_id=conversation.business_id,
                from_number=f"whatsapp:{self.from_number}",
                to_number=conversation.customer_number,
                message_body=ai_response,
                direction='outbound',
                status='sent'
            )
            
            db.session.add(user_msg)
            db.session.add(ai_msg)
            db.session.commit()
            
            logger.info(f"Saved WhatsApp session in {conversation.id} (user+ai messages)")
            
        except Exception as e:
            logger.error(f"Failed to save WhatsApp messages: {e}")
            db.session.rollback()
    
    def _send_whatsapp_message(self, to_number: str, message: str) -> Dict[str, Any]:
        """שליחת הודעת WhatsApp"""
        
        try:
            # וידוא פורמט מספר
            if not to_number.startswith('whatsapp:'):
                to_number = f"whatsapp:{to_number}"
            
            from_whatsapp = f"whatsapp:{self.from_number}"
            
            message_instance = self.client.messages.create(
                body=message,
                from_=from_whatsapp,
                to=to_number
            )
            
            logger.info(f"WhatsApp message sent: {message_instance.sid}")
            
            return {
                'success': True,
                'sid': message_instance.sid,
                'message_sid': message_instance.sid,
                'status': message_instance.status
            }
            
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            return {'success': False, 'error': str(e)}
    
    def _send_error_response(self, conversation, error_message: str) -> Dict[str, Any]:
        """שליחת הודעת שגיאה ללקוח"""
        
        send_result = self._send_whatsapp_message(
            to_number=conversation.customer_number,
            message=error_message
        )
        
        return {
            'success': False,
            'error': 'Processing error',
            'error_message_sent': send_result.get('success', False)
        }


# יצירת instance גלובלי
enhanced_whatsapp_service = EnhancedWhatsAppService()
            return {'success': False, 'error': str(e)}
    
    def _send_error_response(self, conversation: WhatsAppConversation, 
                            error_message: str) -> Dict[str, Any]:
        """שליחת הודעת שגיאה"""
        
        send_result = self._send_whatsapp_message(
            to_number=conversation.from_number,
            message=error_message
        )
        
        if send_result['success']:
            # שמירת הודעת השגיאה
            error_msg = WhatsAppMessage(
                conversation_id=conversation.id,
                business_id=conversation.business_id,
                from_number=conversation.to_number,
                to_number=conversation.from_number,
                message_body=error_message,
                message_type='outgoing',
                status='sent',
                intent_detected='system_error',
                created_at=datetime.utcnow()
            )
            
            db.session.add(error_msg)
            db.session.commit()
        
        return {
            'success': True,
            'error_sent': send_result['success'],
            'message': error_message
        }
    
    def get_conversation_status(self, conversation_id: str) -> Dict[str, Any]:
        """קבלת סטטוס שיחה"""
        
        try:
            conversation = WhatsAppConversation.query.filter_by(
                whatsapp_conversation_id=conversation_id
            ).first()
            
            if not conversation:
                return {'success': False, 'error': 'Conversation not found'}
            
            messages_count = WhatsAppMessage.query.filter_by(
                conversation_id=conversation.id
            ).count()
            
            last_message = WhatsAppMessage.query.filter_by(
                conversation_id=conversation.id
            ).order_by(WhatsAppMessage.created_at.desc()).first()
            
            return {
                'success': True,
                'conversation_id': conversation_id,
                'status': conversation.status,
                'message_count': messages_count,
                'last_activity': conversation.last_activity.isoformat() if conversation.last_activity else None,
                'last_message': {
                    'body': last_message.message_body if last_message else None,
                    'type': last_message.message_type if last_message else None,
                    'timestamp': last_message.created_at.isoformat() if last_message else None
                },
                'has_open_turn': self._has_open_turn(conversation.id)
            }
            
        except Exception as e:
            logger.error(f"Error getting conversation status: {e}")
            return {'success': False, 'error': str(e)}
    
    def cleanup_old_conversations(self, hours: int = 24):
        """ניקוי שיחות ישנות"""
        
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            old_conversations = WhatsAppConversation.query.filter(
                WhatsAppConversation.last_activity < cutoff_time,
                WhatsAppConversation.status == 'active'
            ).all()
            
            for conversation in old_conversations:
                conversation.status = 'inactive'
                self._close_conversation_turn(conversation.id)
            
            db.session.commit()
            
            logger.info(f"Cleaned up {len(old_conversations)} old conversations")
            return len(old_conversations)
            
        except Exception as e:
            logger.error(f"Error cleaning up conversations: {e}")
            db.session.rollback()
            return 0

# Helper functions for appointment duplicate prevention
def _has_appointment_keywords(message: str) -> bool:
    """בדיקה אם ההודעה מכילה מילות מפתח לתור"""
    appointment_keywords = ['תור', 'פגישה', 'רופא', 'זמן', 'מחר', 'היום', 'מתי', 'לקבוע']
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in appointment_keywords)


def _prevent_duplicate_whatsapp_appointment(phone_number: str, business_id: int, message: str) -> bool:
    """מניעת יצירת תורים כפולים ב-WhatsApp"""
    try:
        from models import AppointmentRequest
        from datetime import datetime, timedelta
        
        # בדיקת תורים קיימים בשעתיים האחרונות
        two_hours_ago = datetime.utcnow() - timedelta(hours=2)
        
        existing_appointment = AppointmentRequest.query.filter(
            AppointmentRequest.customer_phone == phone_number,
            AppointmentRequest.created_at >= two_hours_ago,
            AppointmentRequest.status.in_(['pending', 'confirmed'])
        ).first()
        
        if existing_appointment:
            logger.warning(f"⚠️ Duplicate WhatsApp appointment prevented for {phone_number}")
            return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error checking duplicate WhatsApp appointments: {e}")
        return False


# יצירת instance גלובלי
enhanced_whatsapp_service = EnhancedWhatsAppService()