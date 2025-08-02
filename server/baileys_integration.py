"""
Baileys WhatsApp Web Integration for Enhanced CRM
מערכת WhatsApp Web דרך Baileys במקום Twilio
"""

import os
import json
import subprocess
import threading
import time
import logging
from datetime import datetime
from flask import request, jsonify, render_template, redirect, url_for, flash
from app import app, db
from models import Business, WhatsAppConversation, WhatsAppMessage

logger = logging.getLogger(__name__)

class BaileysWhatsAppService:
    """שירות WhatsApp דרך Baileys"""
    
    def __init__(self):
        self.is_connected = False
        self.qr_code = None
        self.baileys_process = None
        self.auth_folder = "baileys_auth_info"
        
    def start_baileys_service(self):
        """הפעלת שירות Baileys"""
        try:
            # וודא שתיקיית האימות קיימת
            os.makedirs(self.auth_folder, exist_ok=True)
            
            # הפעלת Baileys ברקע
            cmd = ["node", "baileys_client.js"]
            self.baileys_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            logger.info("🚀 Baileys WhatsApp service started")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start Baileys: {e}")
            return False
    
    def get_qr_code(self):
        """קבלת QR Code לחיבור"""
        try:
            # קרא QR מקובץ אם קיים
            qr_file = os.path.join(self.auth_folder, "qr_code.txt")
            if os.path.exists(qr_file):
                with open(qr_file, 'r') as f:
                    return f.read().strip()
            return None
        except Exception as e:
            logger.error(f"Error reading QR code: {e}")
            return None
    
    def is_authenticated(self):
        """בדיקה אם WhatsApp מחובר"""
        auth_file = os.path.join(self.auth_folder, "creds.json")
        return os.path.exists(auth_file)
    
    def send_message(self, to_number, message):
        """שליחת הודעה דרך Baileys"""
        try:
            # נקה מספר טלפון
            clean_number = to_number.replace('+', '').replace('-', '').replace(' ', '')
            if not clean_number.endswith('@s.whatsapp.net'):
                clean_number += '@s.whatsapp.net'
            
            # צור בקשת שליחה
            message_data = {
                'to': clean_number,
                'message': message,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # שמור לתור הודעות
            queue_file = os.path.join(self.auth_folder, "message_queue.json")
            queue = []
            if os.path.exists(queue_file):
                with open(queue_file, 'r', encoding='utf-8') as f:
                    queue = json.load(f)
            
            queue.append(message_data)
            
            with open(queue_file, 'w', encoding='utf-8') as f:
                json.dump(queue, f, ensure_ascii=False, indent=2)
            
            logger.info(f"📱 Baileys message queued: {to_number}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Baileys send error: {e}")
            return False
    
    def get_conversations(self, business_id=None):
        """קבלת שיחות WhatsApp"""
        try:
            query = WhatsAppConversation.query
            if business_id:
                query = query.filter_by(business_id=business_id)
            
            conversations = query.order_by(WhatsAppConversation.last_message_at.desc()).all()
            return [conv.to_dict() for conv in conversations]
            
        except Exception as e:
            logger.error(f"Error getting conversations: {e}")
            return []
    
    def process_incoming_message(self, message_data):
        """עיבוד הודעה נכנסת"""
        try:
            phone_number = message_data.get('from', '').replace('@s.whatsapp.net', '')
            message_text = message_data.get('message', '')
            business_id = message_data.get('business_id', 1)
            
            # מצא או צור שיחה
            conversation = WhatsAppConversation.query.filter_by(
                phone_number=phone_number,
                business_id=business_id
            ).first()
            
            if not conversation:
                conversation = WhatsAppConversation(
                    phone_number=phone_number,
                    business_id=business_id,
                    last_message_at=datetime.utcnow()
                )
                db.session.add(conversation)
                db.session.flush()
            
            # שמור הודעה
            message = WhatsAppMessage(
                conversation_id=conversation.id,
                sender_type='customer',
                message_text=message_text,
                timestamp=datetime.utcnow()
            )
            db.session.add(message)
            
            # עדכן זמן אחרון
            conversation.last_message_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"📨 Baileys message processed: {phone_number}")
            
            # עיבוד עם AI אם נדרש
            self._process_with_ai(conversation.id, message_text, business_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing incoming message: {e}")
            db.session.rollback()
            return False
    
    def _process_with_ai(self, conversation_id, message_text, business_id):
        """עיבוד הודעה עם AI"""
        try:
            from ai_service import AIService
            ai_service = AIService()
            
            # עיבוד עם AI
            ai_response = ai_service.process_conversation(
                user_message=message_text,
                business_id=business_id,
                conversation_context={'type': 'whatsapp'}
            )
            
            if ai_response:
                # שמור תגובת AI
                ai_message = WhatsAppMessage(
                    conversation_id=conversation_id,
                    sender_type='ai',
                    message_text=ai_response,
                    timestamp=datetime.utcnow()
                )
                db.session.add(ai_message)
                db.session.commit()
                
                # שלח תגובה חזרה
                conversation = WhatsAppConversation.query.get(conversation_id)
                if conversation:
                    self.send_message(conversation.phone_number, ai_response)
            
        except Exception as e:
            logger.error(f"AI processing error: {e}")

# יצירת מופע שירות גלובלי
baileys_service = BaileysWhatsAppService()

# Routes לממשק Baileys
@app.route('/baileys/setup')
def baileys_setup():
    """עמוד הגדרת Baileys"""
    qr_code = baileys_service.get_qr_code()
    is_connected = baileys_service.is_authenticated()
    
    return render_template('baileys_setup.html', 
                         qr_code=qr_code, 
                         is_connected=is_connected)

@app.route('/baileys/start', methods=['POST'])
def baileys_start():
    """הפעלת שירות Baileys"""
    success = baileys_service.start_baileys_service()
    if success:
        flash('שירות WhatsApp הופעל בהצלחה', 'success')
    else:
        flash('שגיאה בהפעלת השירות', 'error')
    
    return redirect(url_for('baileys_setup'))

@app.route('/baileys/conversations')
def baileys_conversations():
    """רשימת שיחות WhatsApp"""
    conversations = baileys_service.get_conversations()
    return render_template('baileys_conversations.html', 
                         conversations=conversations)

@app.route('/baileys/conversation/<int:conversation_id>')
def baileys_conversation_detail(conversation_id):
    """פרטי שיחה ספציפית"""
    try:
        conversation = WhatsAppConversation.query.get(conversation_id)
        if not conversation:
            flash('שיחה לא נמצאה', 'error')
            return redirect(url_for('baileys_conversations'))
        
        messages = WhatsAppMessage.query.filter_by(
            conversation_id=conversation_id
        ).order_by(WhatsAppMessage.timestamp).all()
        
        return render_template('baileys_conversation_detail.html',
                             conversation=conversation,
                             messages=messages)
    except Exception as e:
        logger.error(f"Error loading conversation: {e}")
        flash('שגיאה בטעינת השיחה', 'error')
        return redirect(url_for('baileys_conversations'))

@app.route('/baileys/send_message', methods=['POST'])
def baileys_send_message():
    """שליחת הודעה חדשה"""
    try:
        conversation_id = request.form.get('conversation_id')
        message_text = request.form.get('message')
        
        if not conversation_id or not message_text:
            return jsonify({'success': False, 'error': 'נתונים חסרים'})
        
        conversation = WhatsAppConversation.query.get(conversation_id)
        if not conversation:
            return jsonify({'success': False, 'error': 'שיחה לא נמצאה'})
        
        # שלח הודעה
        success = baileys_service.send_message(conversation.phone_number, message_text)
        
        if success:
            # שמור הודעה במסד נתונים
            message = WhatsAppMessage(
                conversation_id=conversation_id,
                sender_type='user',
                message_text=message_text,
                timestamp=datetime.utcnow()
            )
            db.session.add(message)
            
            # עדכן זמן אחרון
            conversation.last_message_at = datetime.utcnow()
            db.session.commit()
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'שליחה נכשלה'})
            
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return jsonify({'success': False, 'error': str(e)})

# הפעלת שירות אוטומטית בעת הפעלת האפליקציה
def initialize_baileys():
    """אתחול Baileys בעת הפעלת השרת"""
    try:
        if not baileys_service.is_authenticated():
            logger.info("🔄 Starting Baileys service for first time setup...")
            baileys_service.start_baileys_service()
        else:
            logger.info("✅ Baileys already authenticated, starting service...")
            baileys_service.start_baileys_service()
    except Exception as e:
        logger.error(f"Failed to initialize Baileys: {e}")

# הפעלה אוטומטית
if __name__ != '__main__':
    # הפעל ברקע כשהשרת עולה
    threading.Thread(target=initialize_baileys, daemon=True).start()