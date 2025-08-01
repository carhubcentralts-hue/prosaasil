"""
🚀 WhatsApp Enhanced Service - Advanced Multi-Platform WhatsApp Bot
מערכת WhatsApp מתקדמת עם תמיכה בTwilio WhatsApp Business ו-Baileys WhatsApp Web
"""

import os
import json
import requests
import asyncio
import time
from datetime import datetime, timedelta
from flask import current_app
from app import db
from models import Business, WhatsAppMessage, WhatsAppConversation
from ai_service import AIService
import logging

logger = logging.getLogger(__name__)

class WhatsAppEnhancedService:
    def __init__(self):
        """Initialize enhanced WhatsApp service with dual platform support"""
        self.account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
        self.auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
        self.whatsapp_number = 'whatsapp:+17752616183'
        self.base_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        self.ai_service = AIService()
        
        # Baileys Web WhatsApp Configuration
        self.baileys_enabled = False  # Will be enabled after setup
        self.baileys_session_path = "./baileys_session"
        
        # Message queue for restricted account
        self.message_queue = []
        self.account_restricted = True  # Currently restricted
        
    # ========== Twilio WhatsApp Business Methods ==========
    
    def send_twilio_whatsapp(self, to_number, message_text, business_id=None):
        """שלח הודעת WhatsApp דרך Twilio WhatsApp Business API"""
        try:
            if not to_number.startswith('whatsapp:'):
                to_number = f'whatsapp:{to_number}'
                
            logger.info(f"📱 [Twilio] Sending WhatsApp to {to_number}: {message_text[:50]}...")
            
            if self.account_restricted:
                # Queue message during restriction
                queued_message = {
                    'to_number': to_number,
                    'message_text': message_text,
                    'business_id': business_id,
                    'timestamp': datetime.utcnow(),
                    'platform': 'twilio',
                    'status': 'queued_account_restricted'
                }
                self.message_queue.append(queued_message)
                logger.warning(f"🚨 [Twilio] Account restricted - Message queued: {len(self.message_queue)} total")
                
                # Save to database as queued
                if business_id:
                    conversation = self._get_or_create_conversation(
                        customer_number=to_number.replace('whatsapp:', ''),
                        business_id=int(business_id)
                    )
                    self._save_message_to_db(
                        conversation_id=conversation.id,
                        message_sid=f'QUEUED_TWILIO_{int(time.time())}',
                        from_number=self.whatsapp_number,
                        to_number=to_number,
                        message_body=message_text,
                        direction='outbound',
                        status='queued_account_restricted',
                        business_id=business_id
                    )
                
                return {
                    'success': True,
                    'sid': f'QUEUED_TWILIO_{int(time.time())}',
                    'status': 'queued_account_restricted',
                    'platform': 'twilio'
                }
            
            # Send via Twilio when account is active
            message_data = {
                'From': self.whatsapp_number,
                'To': to_number,
                'Body': message_text
            }
            
            response = requests.post(
                self.base_url,
                data=message_data,
                auth=(self.account_sid or "", self.auth_token or ""),
                timeout=30
            )
            
            if response.status_code == 201:
                result = response.json()
                logger.info(f"✅ [Twilio] WhatsApp sent successfully: {result['sid']}")
                return {
                    'success': True,
                    'sid': result['sid'],
                    'status': result['status'],
                    'platform': 'twilio'
                }
            else:
                logger.error(f"❌ [Twilio] Failed to send: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': response.text,
                    'platform': 'twilio'
                }
                
        except Exception as e:
            logger.error(f"❌ [Twilio] WhatsApp send error: {e}")
            return {
                'success': False,
                'error': str(e),
                'platform': 'twilio'
            }
    
    # ========== Baileys WhatsApp Web Methods ==========
    
    def send_baileys_whatsapp(self, to_number, message_text, business_id=None):
        """שלח הודעת WhatsApp דרך Baileys WhatsApp Web"""
        try:
            # Clean phone number for Baileys format
            clean_number = to_number.replace('whatsapp:', '').replace('+', '')
            if not clean_number.endswith('@s.whatsapp.net'):
                clean_number = f'{clean_number}@s.whatsapp.net'
                
            logger.info(f"📱 [Baileys] Sending WhatsApp to {clean_number}: {message_text[:50]}...")
            
            if not self.baileys_enabled:
                logger.warning("⚠️ [Baileys] Not enabled - Use setup_baileys() first")
                return {
                    'success': False,
                    'error': 'Baileys not enabled - setup required',
                    'platform': 'baileys'
                }
            
            # Queue for Baileys processing
            baileys_message = {
                'to': clean_number,
                'message': message_text,
                'business_id': business_id,
                'timestamp': datetime.utcnow(),
                'platform': 'baileys'
            }
            
            # Save to database
            if business_id:
                conversation = self._get_or_create_conversation(
                    customer_number=to_number.replace('whatsapp:', '').replace('+', ''),
                    business_id=int(business_id)
                )
                self._save_message_to_db(
                    conversation_id=conversation.id,
                    message_sid=f'BAILEYS_{int(time.time())}',
                    from_number='baileys_session',
                    to_number=clean_number,
                    message_body=message_text,
                    direction='outbound',
                    status='sent_baileys',
                    business_id=business_id
                )
            
            # TODO: Implement actual Baileys sending when session is ready
            logger.info(f"✅ [Baileys] Message prepared for sending: {clean_number}")
            
            return {
                'success': True,
                'sid': f'BAILEYS_{int(time.time())}',
                'status': 'sent_baileys',
                'platform': 'baileys'
            }
            
        except Exception as e:
            logger.error(f"❌ [Baileys] WhatsApp send error: {e}")
            return {
                'success': False,
                'error': str(e),
                'platform': 'baileys'
            }
    
    # ========== Unified Sending Method ==========
    
    def send_whatsapp_message(self, to_number, message_text, business_id=None, platform='auto'):
        """שלח הודעת WhatsApp עם בחירה אוטומטית של פלטפורמה"""
        try:
            logger.info(f"📱 [Enhanced] Sending WhatsApp message via {platform}")
            
            if platform == 'twilio' or (platform == 'auto' and not self.baileys_enabled):
                return self.send_twilio_whatsapp(to_number, message_text, business_id)
            elif platform == 'baileys' or (platform == 'auto' and self.account_restricted):
                return self.send_baileys_whatsapp(to_number, message_text, business_id)
            else:
                # Auto-select best platform
                if self.account_restricted:
                    logger.info("📱 [Enhanced] Auto-selecting Baileys (Twilio restricted)")
                    return self.send_baileys_whatsapp(to_number, message_text, business_id)
                else:
                    logger.info("📱 [Enhanced] Auto-selecting Twilio (account active)")
                    return self.send_twilio_whatsapp(to_number, message_text, business_id)
                    
        except Exception as e:
            logger.error(f"❌ [Enhanced] Send error: {e}")
            return {
                'success': False,
                'error': str(e),
                'platform': 'enhanced'
            }
    
    # ========== Message Processing ==========
    
    def process_incoming_whatsapp(self, webhook_data, platform='twilio'):
        """עיבוד הודעות WhatsApp נכנסות מכל פלטפורמה"""
        try:
            from_number = webhook_data.get('From', '').replace('whatsapp:', '')
            to_number = webhook_data.get('To', '').replace('whatsapp:', '')
            message_body = webhook_data.get('Body', '').strip()
            message_sid = webhook_data.get('MessageSid', f'{platform}_{int(time.time())}')
            
            logger.info(f"📱 [Enhanced] Processing {platform} message from {from_number}: {message_body[:50]}...")
            
            # Get business by WhatsApp number
            business = Business.query.filter_by(whatsapp_number=to_number).first()
            if not business:
                business = Business.query.filter_by(whatsapp_number=f'+{to_number}').first()
            
            if not business:
                logger.warning(f"⚠️ [Enhanced] No business found for WhatsApp {to_number}")
                return {'status': 'error', 'message': 'Business not found'}
            
            # Create/get conversation
            conversation = self._get_or_create_conversation(from_number, business.id)
            
            # Save incoming message
            self._save_message_to_db(
                conversation_id=conversation.id,
                message_sid=message_sid,
                from_number=from_number,
                to_number=to_number,
                message_body=message_body,
                direction='inbound',
                status='received',
                business_id=business.id
            )
            
            # Generate AI response
            ai_response = self.ai_service.generate_whatsapp_response(
                business_id=business.id,
                customer_message=message_body,
                conversation_history=self._get_conversation_history(conversation.id)
            )
            
            if ai_response and ai_response.get('response'):
                # Send response using unified method
                send_result = self.send_whatsapp_message(
                    to_number=f'+{from_number}',
                    message_text=ai_response['response'],
                    business_id=business.id,
                    platform='auto'  # Auto-select best platform
                )
                
                if send_result.get('success'):
                    logger.info(f"✅ [Enhanced] AI response sent via {send_result.get('platform')}")
                else:
                    logger.error(f"❌ [Enhanced] Failed to send AI response: {send_result.get('error')}")
            
            return {'status': 'processed', 'platform': platform}
            
        except Exception as e:
            logger.error(f"❌ [Enhanced] Processing error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    # ========== Baileys Setup ==========
    
    def setup_baileys(self):
        """הגדרת Baileys WhatsApp Web Session"""
        try:
            logger.info("🔧 [Baileys] Setting up WhatsApp Web session...")
            
            # Create Baileys session directory
            os.makedirs(self.baileys_session_path, exist_ok=True)
            
            # TODO: Implement Baileys initialization
            # This would typically involve:
            # 1. Installing @whiskeysockets/baileys npm package
            # 2. Creating Node.js script for WhatsApp Web connection
            # 3. QR code generation for authentication
            # 4. Session persistence
            
            logger.info("📱 [Baileys] Session setup prepared - QR scan required")
            
            return {
                'success': True,
                'message': 'Baileys setup prepared - QR scan required',
                'session_path': self.baileys_session_path
            }
            
        except Exception as e:
            logger.error(f"❌ [Baileys] Setup error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def enable_baileys(self):
        """הפעלת מצב Baileys לאחר הגדרה מוצלחת"""
        self.baileys_enabled = True
        logger.info("✅ [Baileys] WhatsApp Web mode enabled")
    
    # ========== Queue Management ==========
    
    def get_message_queue_status(self):
        """קבלת סטטוס תור ההודעות"""
        return {
            'total_queued': len(self.message_queue),
            'account_restricted': self.account_restricted,
            'baileys_enabled': self.baileys_enabled,
            'queue': self.message_queue[-10:]  # Last 10 messages
        }
    
    def flush_message_queue(self):
        """ריקון תור ההודעות כשהחשבון חוזר לפעילות"""
        if not self.account_restricted:
            logger.info(f"🚀 [Enhanced] Flushing {len(self.message_queue)} queued messages...")
            
            for queued_msg in self.message_queue:
                if queued_msg['platform'] == 'twilio':
                    self.send_twilio_whatsapp(
                        queued_msg['to_number'],
                        queued_msg['message_text'],
                        queued_msg['business_id']
                    )
                elif queued_msg['platform'] == 'baileys':
                    self.send_baileys_whatsapp(
                        queued_msg['to_number'],
                        queued_msg['message_text'],
                        queued_msg['business_id']
                    )
            
            self.message_queue.clear()
            logger.info("✅ [Enhanced] Message queue flushed successfully")
    
    def set_account_status(self, restricted=False):
        """עדכון סטטוס החשבון"""
        self.account_restricted = restricted
        if not restricted:
            self.flush_message_queue()
    
    # ========== Helper Methods ==========
    
    def _get_or_create_conversation(self, customer_number, business_id):
        """יצירה או קבלת שיחה קיימת"""
        conversation = WhatsAppConversation.query.filter_by(
            customer_number=customer_number,
            business_id=business_id
        ).first()
        
        if not conversation:
            conversation = WhatsAppConversation()
            conversation.customer_number = customer_number
            conversation.business_id = business_id
            conversation.status = 'active'
            db.session.add(conversation)
            db.session.commit()
            
        return conversation
    
    def _save_message_to_db(self, conversation_id, message_sid, from_number, to_number, 
                           message_body, direction, status, business_id):
        """שמירת הודעה במסד הנתונים"""
        message = WhatsAppMessage()
        message.conversation_id = conversation_id
        message.message_sid = message_sid
        message.from_number = from_number
        message.to_number = to_number
        message.message_body = message_body
        message.direction = direction
        message.status = status
        message.business_id = business_id
        db.session.add(message)
        db.session.commit()
        
        return message
    
    def _get_conversation_history(self, conversation_id, limit=20):
        """קבלת היסטוריית שיחה"""
        messages = WhatsAppMessage.query.filter_by(
            conversation_id=conversation_id
        ).order_by(
            WhatsAppMessage.created_at.desc()
        ).limit(limit).all()
        
        return [
            {
                'direction': msg.direction,
                'message': msg.message_body,
                'timestamp': msg.created_at
            }
            for msg in reversed(messages)
        ]

# Global instance
whatsapp_enhanced = WhatsAppEnhancedService()