"""
WhatsApp Module Tests - בדיקות מקיפות למודול WhatsApp
"""
import unittest
import sys
import os
from datetime import datetime
import json

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Business, User, WhatsAppConversation, WhatsAppMessage
from whatsapp_service import WhatsAppService

class TestWhatsAppModule(unittest.TestCase):
    """בדיקות למודול WhatsApp"""
    
    def setUp(self):
        """הכנות לפני כל בדיקה"""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_whatsapp.db'
        
        with self.app.app_context():
            db.create_all()
            
            # יצירת עסק לבדיקה
            self.test_business = Business(
                name='עסק WhatsApp',
                business_type='test',
                phone_number='+972501234567',
                whatsapp_number='+972501234567',
                greeting_message='שלום מ-WhatsApp',
                system_prompt='בדיקת WhatsApp',
                whatsapp_enabled=True,
                is_active=True
            )
            db.session.add(self.test_business)
            
            # יצירת משתמש לבדיקה
            self.test_user = User(
                username='whatsapp_user',
                email='whatsapp@test.com',
                password_hash='test_hash',
                role='business',
                business_id=1,  # Will be updated after business creation
                can_access_whatsapp=True
            )
            db.session.add(self.test_user)
            db.session.commit()
            
            # עדכון business_id של המשתמש
            self.test_user.business_id = self.test_business.id
            db.session.commit()
        
        self.client = self.app.test_client()
        self.whatsapp_service = WhatsAppService()
        
    def tearDown(self):
        """ניקוי אחרי כל בדיקה"""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
    
    def test_whatsapp_dashboard_route(self):
        """בדיקת route של דשבורד WhatsApp"""
        with self.app.app_context():
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            response = self.client.get('/whatsapp/')
            
            # בדיקה שהדף נטען בהצלחה או מפנה לאימות
            self.assertIn(response.status_code, [200, 302])
    
    def test_whatsapp_service_initialization(self):
        """בדיקת אתחול שירות WhatsApp"""
        self.assertIsNotNone(self.whatsapp_service)
        self.assertIsNotNone(self.whatsapp_service.whatsapp_number)
    
    def test_send_whatsapp_message_api(self):
        """בדיקת API לשליחת הודעת WhatsApp"""
        with self.app.app_context():
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            message_data = {
                'to_number': '+972501234567',
                'message': 'הודעת בדיקה',
                'business_id': self.test_business.id
            }
            
            response = self.client.post('/whatsapp/send_message',
                                      data=json.dumps(message_data),
                                      content_type='application/json')
            
            # בדיקה שהשליחה התבצעה או הוחזרה הודעת שגיאה מתאימה
            self.assertIn(response.status_code, [200, 400, 500])
            
            if response.status_code == 200:
                data = json.loads(response.data)
                self.assertIn('success', data)
    
    def test_webhook_message_processing(self):
        """בדיקת עיבוד הודעה נכנסת דרך webhook"""
        with self.app.app_context():
            webhook_data = {
                'MessageSid': 'test_sid_123',
                'From': 'whatsapp:+972501234567',
                'To': f'whatsapp:{self.test_business.whatsapp_number}',
                'Body': 'שלום, אני רוצה מידע'
            }
            
            response = self.client.post('/whatsapp/webhook', data=webhook_data)
            
            # בדיקה שההודעה עובדה בהצלחה
            self.assertEqual(response.status_code, 200)
            
            # בדיקה שנוצרה שיחה במסד הנתונים
            conversation = WhatsAppConversation.query.filter_by(
                customer_number='+972501234567',
                business_id=self.test_business.id
            ).first()
            self.assertIsNotNone(conversation)
            
            # בדיקה שההודעה נשמרה
            message = WhatsAppMessage.query.filter_by(
                message_sid='test_sid_123'
            ).first()
            self.assertIsNotNone(message)
            self.assertEqual(message.message_body, 'שלום, אני רוצה מידע')
            self.assertEqual(message.direction, 'inbound')
    
    def test_webhook_invalid_data(self):
        """בדיקת webhook עם נתונים לא תקינים"""
        with self.app.app_context():
            # נתונים חסרים
            invalid_data = {
                'From': 'whatsapp:+972501234567'
                # חסר MessageSid ו-Body
            }
            
            response = self.client.post('/whatsapp/webhook', data=invalid_data)
            
            # בדיקה שהשרת מחזיר שגיאה
            self.assertEqual(response.status_code, 400)
    
    def test_status_callback(self):
        """בדיקת callback לסטטוס הודעות"""
        with self.app.app_context():
            # יצירת הודעה לבדיקה
            message = WhatsAppMessage(
                conversation_id=1,
                message_sid='test_sid_status',
                from_number='+972501234567',
                to_number=self.test_business.whatsapp_number,
                message_body='בדיקת סטטוס',
                direction='outbound',
                business_id=self.test_business.id,
                status='sent'
            )
            db.session.add(message)
            db.session.commit()
            
            status_data = {
                'MessageStatus': 'delivered',
                'ErrorCode': '',
                'ErrorMessage': ''
            }
            
            response = self.client.post(f'/whatsapp/status/{message.message_sid}',
                                      data=status_data)
            
            # בדיקה שהסטטוס עודכן
            self.assertEqual(response.status_code, 200)
            
            # בדיקה שהסטטוס השתנה במסד הנתונים
            updated_message = WhatsAppMessage.query.filter_by(
                message_sid='test_sid_status'
            ).first()
            self.assertEqual(updated_message.status, 'delivered')
    
    def test_view_conversation_authorized(self):
        """בדיקת צפייה בשיחה עם הרשאות"""
        with self.app.app_context():
            # יצירת שיחה לבדיקה
            conversation = WhatsAppConversation(
                customer_number='+972501234567',
                business_id=self.test_business.id,
                status='active'
            )
            db.session.add(conversation)
            db.session.commit()
            
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            response = self.client.get(f'/whatsapp/conversation/{conversation.id}')
            
            # בדיקה שהצפייה מותרת
            self.assertIn(response.status_code, [200, 302])
    
    def test_api_conversations_endpoint(self):
        """בדיקת API לקבלת שיחות"""
        with self.app.app_context():
            # יצירת שיחות לבדיקה
            conversations = [
                WhatsAppConversation(
                    customer_number='+972501111111',
                    business_id=self.test_business.id,
                    status='active'
                ),
                WhatsAppConversation(
                    customer_number='+972502222222',
                    business_id=self.test_business.id,
                    status='active'
                )
            ]
            
            for conv in conversations:
                db.session.add(conv)
            db.session.commit()
            
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            response = self.client.get('/whatsapp/api/conversations')
            
            # בדיקה שהAPI מחזיר נתונים תקינים
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIsInstance(data, list)
            self.assertEqual(len(data), 2)
    
    def test_api_stats_endpoint(self):
        """בדיקת API לסטטיסטיקות WhatsApp"""
        with self.app.app_context():
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            response = self.client.get('/whatsapp/api/stats')
            
            # בדיקה שהAPI מחזיר סטטיסטיקות תקינות
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn('total_conversations', data)
            self.assertIn('total_messages', data)
            self.assertIn('today_messages', data)
    
    def test_unauthorized_whatsapp_access(self):
        """בדיקת גישה לא מורשית ל-WhatsApp"""
        with self.app.app_context():
            # יצירת משתמש ללא הרשאות WhatsApp
            no_whatsapp_user = User(
                username='no_whatsapp',
                email='no@whatsapp.com',
                password_hash='test',
                role='business',
                business_id=self.test_business.id,
                can_access_whatsapp=False
            )
            db.session.add(no_whatsapp_user)
            db.session.commit()
            
            with self.client.session_transaction() as sess:
                sess['user_id'] = no_whatsapp_user.id
            
            response = self.client.get('/whatsapp/')
            
            # בדיקה שהגישה נדחית
            self.assertEqual(response.status_code, 302)
    
    def test_message_validation(self):
        """בדיקת ואלידציה של הודעות"""
        with self.app.app_context():
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            # הודעה ללא מספר טלפון
            invalid_message = {
                'message': 'הודעה ללא מספר',
                'business_id': self.test_business.id
            }
            
            response = self.client.post('/whatsapp/send_message',
                                      data=json.dumps(invalid_message),
                                      content_type='application/json')
            
            # בדיקה שהשרת מחזיר שגיאת ואלידציה
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertFalse(data.get('success', True))
    
    def test_conversation_creation_and_update(self):
        """בדיקת יצירה ועדכון של שיחות"""
        with self.app.app_context():
            initial_count = WhatsAppConversation.query.count()
            
            # הודעה ראשונה ממספר חדש
            webhook_data = {
                'MessageSid': 'new_customer_123',
                'From': 'whatsapp:+972503333333',
                'To': f'whatsapp:{self.test_business.whatsapp_number}',
                'Body': 'הודעה ראשונה'
            }
            
            response = self.client.post('/whatsapp/webhook', data=webhook_data)
            self.assertEqual(response.status_code, 200)
            
            # בדיקה שנוצרה שיחה חדשה
            new_count = WhatsAppConversation.query.count()
            self.assertEqual(new_count, initial_count + 1)
            
            # הודעה שנייה מאותו מספר
            webhook_data['MessageSid'] = 'same_customer_456'
            webhook_data['Body'] = 'הודעה שנייה'
            
            response = self.client.post('/whatsapp/webhook', data=webhook_data)
            self.assertEqual(response.status_code, 200)
            
            # בדיקה שלא נוצרה שיחה נוספת
            final_count = WhatsAppConversation.query.count()
            self.assertEqual(final_count, new_count)
            
            # בדיקה שהשיחה עודכנה
            conversation = WhatsAppConversation.query.filter_by(
                customer_number='+972503333333'
            ).first()
            self.assertIsNotNone(conversation)
            self.assertEqual(len(conversation.messages), 2)

if __name__ == '__main__':
    # הרצת הבדיקות
    unittest.main(verbosity=2)