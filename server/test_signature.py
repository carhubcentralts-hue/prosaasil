"""
Digital Signature Module Tests - בדיקות מקיפות למודול חתימות דיגיטליות
"""
import unittest
import sys
import os
from datetime import datetime
import json
import tempfile

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Business, User, CRMCustomer
from digital_signature_service import DigitalSignatureService

class TestSignatureModule(unittest.TestCase):
    """בדיקות למודול חתימות דיגיטליות"""
    
    def setUp(self):
        """הכנות לפני כל בדיקה"""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_signature.db'
        
        with self.app.app_context():
            db.create_all()
            
            # יצירת עסק לבדיקה
            self.test_business = Business(
                name='עסק חתימות',
                business_type='legal',
                phone_number='+972501234567',
                greeting_message='שלום לעסק חתימות',
                system_prompt='מערכת חתימות',
                is_active=True
            )
            db.session.add(self.test_business)
            
            # יצירת משתמש לבדיקה
            self.test_user = User(
                username='signature_user',
                email='signature@test.com',
                password_hash='test_hash',
                role='business',
                business_id=1,  # Will be updated after business creation
                can_access_crm=True
            )
            db.session.add(self.test_user)
            
            # יצירת לקוח לבדיקה
            self.test_customer = CRMCustomer(
                name='לקוח חתימה',
                phone='+972501234567',
                email='customer@test.com',
                business_id=1,  # Will be updated after business creation
                status='active'
            )
            db.session.add(self.test_customer)
            db.session.commit()
            
            # עדכון business_id
            self.test_user.business_id = self.test_business.id
            self.test_customer.business_id = self.test_business.id
            db.session.commit()
        
        self.client = self.app.test_client()
        self.signature_service = DigitalSignatureService()
        
    def tearDown(self):
        """ניקוי אחרי כל בדיקה"""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
    
    def test_signature_dashboard_route(self):
        """בדיקת route של דשבורד חתימות"""
        with self.app.app_context():
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            response = self.client.get('/signatures/')
            
            # בדיקה שהדף נטען בהצלחה או מפנה לאימות
            self.assertIn(response.status_code, [200, 302])
    
    def test_signature_service_initialization(self):
        """בדיקת אתחול שירות חתימות דיגיטליות"""
        self.assertIsNotNone(self.signature_service)
    
    def test_create_signature_with_file(self):
        """בדיקת יצירת חתימה עם קובץ"""
        with self.app.app_context():
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            # יצירת קובץ זמני לבדיקה
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_file.write(b'PDF test content')
                tmp_file_path = tmp_file.name
            
            try:
                with open(tmp_file_path, 'rb') as test_file:
                    signature_data = {
                        'customer_id': self.test_customer.id,
                        'document_type': 'contract',
                        'notes': 'חתימה לבדיקה',
                        'document': (test_file, 'test_contract.pdf')
                    }
                    
                    response = self.client.post('/signatures/create',
                                              data=signature_data,
                                              content_type='multipart/form-data')
                    
                    # בדיקה שהיצירה התבצעה או הוחזרה הודעת שגיאה מתאימה
                    self.assertEqual(response.status_code, 302)  # Redirect after submission
                    
            finally:
                # ניקוי הקובץ הזמני
                os.unlink(tmp_file_path)
    
    def test_create_signature_missing_file(self):
        """בדיקת יצירת חתימה ללא קובץ"""
        with self.app.app_context():
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            signature_data = {
                'customer_id': self.test_customer.id,
                'document_type': 'contract',
                'notes': 'חתימה ללא קובץ'
                # ללא קובץ
            }
            
            response = self.client.post('/signatures/create', data=signature_data)
            
            # בדיקה שהשרת מחזיר שגיאה
            self.assertEqual(response.status_code, 302)  # Redirect with error
    
    def test_create_advanced_signature(self):
        """בדיקת יצירת חתימה מתקדמת"""
        with self.app.app_context():
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            # יצירת קובץ זמני לבדיקה
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_file.write(b'Advanced PDF test content')
                tmp_file_path = tmp_file.name
            
            try:
                with open(tmp_file_path, 'rb') as test_file:
                    signature_data = {
                        'customer_id': self.test_customer.id,
                        'document_type': 'agreement',
                        'title': 'הסכם בדיקה מתקדם',
                        'notes': 'חתימה מתקדמת לבדיקה',
                        'expiry_date': '2024-12-31',
                        'send_method': 'whatsapp',
                        'send_immediately': 'on',
                        'document': (test_file, 'advanced_agreement.pdf')
                    }
                    
                    response = self.client.post('/signatures/create_advanced',
                                              data=signature_data,
                                              content_type='multipart/form-data')
                    
                    # בדיקה שהיצירה המתקדמת התבצעה
                    self.assertEqual(response.status_code, 302)
                    
            finally:
                # ניקוי הקובץ הזמני
                os.unlink(tmp_file_path)
    
    def test_signature_service_methods(self):
        """בדיקת שיטות שירות החתימות"""
        with self.app.app_context():
            # בדיקת יצירת חתימה דרך השירות
            with tempfile.NamedTemporaryFile(suffix='.pdf') as tmp_file:
                tmp_file.write(b'Service test content')
                tmp_file.seek(0)
                
                result = self.signature_service.create_signature_document(
                    customer_id=self.test_customer.id,
                    document_type='contract',
                    document_file=tmp_file,
                    notes='בדיקת שירות',
                    business_id=self.test_business.id
                )
                
                # בדיקה שהשירות מחזיר תוצאה
                self.assertIsNotNone(result)
                self.assertIsInstance(result, dict)
    
    def test_send_signature_api(self):
        """בדיקת API לשליחת חתימה"""
        with self.app.app_context():
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            # ניסיון שליחת חתימה (Mock)
            response = self.client.post('/signatures/send/1',
                                      content_type='application/json')
            
            # בדיקה שהAPI מגיב (גם אם החתימה לא קיימת)
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn('success', data)
    
    def test_remind_signature_api(self):
        """בדיקת API לתזכורת חתימה"""
        with self.app.app_context():
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            # ניסיון שליחת תזכורת (Mock)
            response = self.client.post('/signatures/remind/1',
                                      content_type='application/json')
            
            # בדיקה שהAPI מגיב
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn('success', data)
    
    def test_view_signature_route(self):
        """בדיקת צפייה בחתימה"""
        with self.app.app_context():
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            response = self.client.get('/signatures/view/1')
            
            # בדיקה שהנתיב מגיב (גם אם החתימה לא קיימת)
            self.assertIn(response.status_code, [200, 302, 404])
    
    def test_download_signature_route(self):
        """בדיקת הורדת חתימה"""
        with self.app.app_context():
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            response = self.client.get('/signatures/download/1')
            
            # בדיקה שהנתיב מגיב
            self.assertIn(response.status_code, [200, 302, 404])
    
    def test_api_signatures_endpoint(self):
        """בדיקת API לקבלת חתימות"""
        with self.app.app_context():
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            response = self.client.get('/signatures/api/signatures')
            
            # בדיקה שהAPI מחזיר נתונים תקינים
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIsInstance(data, list)
    
    def test_public_signature_page(self):
        """בדיקת עמוד חתימה ציבורי"""
        with self.app.app_context():
            # ניסיון גישה לעמוד חתימה ציבורי עם token לא קיים
            response = self.client.get('/signatures/public/sign/invalid_token')
            
            # בדיקה שהעמוד מחזיר 404 לtoken לא קיים
            self.assertEqual(response.status_code, 404)
    
    def test_submit_signature_endpoint(self):
        """בדיקת הגשת חתימה"""
        with self.app.app_context():
            signature_data = {
                'signature': 'base64_signature_data',
                'customer_details': {
                    'name': 'לקוח חותם',
                    'email': 'signing@test.com'
                }
            }
            
            response = self.client.post('/signatures/public/submit/invalid_token',
                                      data=json.dumps(signature_data),
                                      content_type='application/json')
            
            # בדיקה שהAPI מגיב עם שגיאה לtoken לא קיים
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertFalse(data.get('success', True))
    
    def test_unauthorized_signature_access(self):
        """בדיקת גישה לא מורשית לחתימות"""
        # ניסיון גישה ללא התחברות
        response = self.client.get('/signatures/')
        
        # בדיקה שהמערכת מפנה לדף התחברות או מחזירה שגיאת הרשאה
        self.assertIn(response.status_code, [302, 401, 403])
    
    def test_cross_business_signature_protection(self):
        """בדיקת הגנה על חתימות בין עסקים"""
        with self.app.app_context():
            # יצירת עסק נוסף
            other_business = Business(
                name='עסק אחר',
                business_type='other',
                phone_number='+972509999999',
                greeting_message='עסק אחר',
                system_prompt='אחר',
                is_active=True
            )
            db.session.add(other_business)
            
            # יצירת לקוח בעסק אחר
            other_customer = CRMCustomer(
                name='לקוח של עסק אחר',
                phone='+972509999999',
                business_id=1,  # Will be updated
                status='active'
            )
            db.session.add(other_customer)
            db.session.commit()
            
            other_customer.business_id = other_business.id
            db.session.commit()
            
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            # ניסיון יצירת חתימה עבור לקוח של עסק אחר
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_file.write(b'Cross business test')
                tmp_file_path = tmp_file.name
            
            try:
                with open(tmp_file_path, 'rb') as test_file:
                    signature_data = {
                        'customer_id': other_customer.id,
                        'document_type': 'contract',
                        'notes': 'ניסיון גישה לא מורשית',
                        'document': (test_file, 'unauthorized.pdf')
                    }
                    
                    response = self.client.post('/signatures/create',
                                              data=signature_data,
                                              content_type='multipart/form-data')
                    
                    # בדיקה שהגישה נדחית
                    self.assertEqual(response.status_code, 302)
                    
            finally:
                os.unlink(tmp_file_path)

if __name__ == '__main__':
    # הרצת הבדיקות
    unittest.main(verbosity=2)