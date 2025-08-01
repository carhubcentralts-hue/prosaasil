"""
CRM Module Tests - בדיקות מקיפות למודול CRM
"""
import unittest
import sys
import os
from datetime import datetime

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import CRMCustomer, CRMTask, Business, User
from auth import AuthService
import json

class TestCRMModule(unittest.TestCase):
    """בדיקות למודול CRM"""
    
    def setUp(self):
        """הכנות לפני כל בדיקה"""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_crm.db'
        
        with self.app.app_context():
            db.create_all()
            
            # יצירת עסק לבדיקה
            self.test_business = Business(
                name='עסק בדיקה',
                business_type='test',
                phone_number='+972501234567',
                greeting_message='שלום מעסק הבדיקה',
                system_prompt='מערכת בדיקה',
                is_active=True
            )
            db.session.add(self.test_business)
            
            # יצירת משתמש לבדיקה
            self.test_user = User(
                username='test_user',
                email='test@test.com',
                password_hash='test_hash',
                role='business',
                business_id=1,  # Will be updated after business creation
                can_access_crm=True
            )
            db.session.add(self.test_user)
            db.session.commit()
            
            # עדכון business_id של המשתמש
            self.test_user.business_id = self.test_business.id
            db.session.commit()
        
        self.client = self.app.test_client()
        
    def tearDown(self):
        """ניקוי אחרי כל בדיקה"""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
    
    def test_crm_dashboard_route(self):
        """בדיקת route של דשבורד CRM"""
        with self.app.app_context():
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            response = self.client.get('/crm/')
            
            # בדיקה שהדף נטען בהצלחה או מפנה לאימות
            self.assertIn(response.status_code, [200, 302])
    
    def test_add_customer_success(self):
        """בדיקת הוספת לקוח בהצלחה"""
        with self.app.app_context():
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            customer_data = {
                'name': 'יוסי כהן',
                'phone': '+972501234567',
                'email': 'yossi@example.com',
                'status': 'active',
                'source': 'manual',
                'notes': 'לקוח בדיקה'
            }
            
            response = self.client.post('/crm/add_customer', data=customer_data)
            
            # בדיקה שהתוספת הצליחה
            self.assertEqual(response.status_code, 302)  # Redirect after success
            
            # בדיקה שהלקוח נשמר במסד הנתונים
            customer = CRMCustomer.query.filter_by(phone=customer_data['phone']).first()
            self.assertIsNotNone(customer)
            self.assertEqual(customer.name, customer_data['name'])
            self.assertEqual(customer.email, customer_data['email'])
    
    def test_add_customer_missing_required_fields(self):
        """בדיקת הוספת לקוח עם שדות חסרים"""
        with self.app.app_context():
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            # נתונים חסרים (ללא שם)
            customer_data = {
                'phone': '+972501234567',
                'email': 'test@example.com'
            }
            
            response = self.client.post('/crm/add_customer', data=customer_data)
            
            # בדיקה שהשרת מחזיר שגיאה או מפנה חזרה
            self.assertEqual(response.status_code, 302)
            
            # בדיקה שהלקוח לא נשמר במסד הנתונים
            customer = CRMCustomer.query.filter_by(phone=customer_data['phone']).first()
            self.assertIsNone(customer)
    
    def test_view_customer_authorized(self):
        """בדיקת צפייה בלקוח עם הרשאות"""
        with self.app.app_context():
            # יצירת לקוח לבדיקה
            customer = CRMCustomer(
                name='לקוח בדיקה',
                phone='+972501234567',
                business_id=self.test_business.id,
                status='active'
            )
            db.session.add(customer)
            db.session.commit()
            
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            response = self.client.get(f'/crm/customer/{customer.id}')
            
            # בדיקה שהצפייה מותרת
            self.assertIn(response.status_code, [200, 302])
    
    def test_add_task_success(self):
        """בדיקת הוספת משימה בהצלחה"""
        with self.app.app_context():
            # יצירת לקוח לבדיקה
            customer = CRMCustomer(
                name='לקוח בדיקה',
                phone='+972501234567',
                business_id=self.test_business.id,
                status='active'
            )
            db.session.add(customer)
            db.session.commit()
            
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            task_data = {
                'title': 'משימת בדיקה',
                'description': 'תיאור משימת הבדיקה',
                'customer_id': customer.id,
                'priority': 'high',
                'due_date': '2024-12-31'
            }
            
            response = self.client.post('/crm/add_task', data=task_data)
            
            # בדיקה שהמשימה נוספה בהצלחה
            self.assertEqual(response.status_code, 200)
            
            # בדיקה שהמשימה נשמרה במסד הנתונים
            task = CRMTask.query.filter_by(title=task_data['title']).first()
            self.assertIsNotNone(task)
            self.assertEqual(task.description, task_data['description'])
            self.assertEqual(task.customer_id, customer.id)
    
    def test_api_customers_endpoint(self):
        """בדיקת API לקבלת לקוחות"""
        with self.app.app_context():
            # יצירת לקוחות לבדיקה
            customers = [
                CRMCustomer(name='לקוח 1', phone='+972501111111', business_id=self.test_business.id),
                CRMCustomer(name='לקוח 2', phone='+972502222222', business_id=self.test_business.id)
            ]
            
            for customer in customers:
                db.session.add(customer)
            db.session.commit()
            
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            response = self.client.get('/crm/api/customers')
            
            # בדיקה שהAPI מחזיר נתונים תקינים
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIsInstance(data, list)
            self.assertEqual(len(data), 2)
    
    def test_api_stats_endpoint(self):
        """בדיקת API לסטטיסטיקות"""
        with self.app.app_context():
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            response = self.client.get('/crm/api/stats')
            
            # בדיקה שהAPI מחזיר סטטיסטיקות תקינות
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn('total_customers', data)
            self.assertIn('active_customers', data)
            self.assertIn('total_tasks', data)
    
    def test_unauthorized_access(self):
        """בדיקת גישה לא מורשית"""
        # ניסיון גישה ללא התחברות
        response = self.client.get('/crm/')
        
        # בדיקה שהמערכת מפנה לדף התחברות או מחזירה שגיאת הרשאה
        self.assertIn(response.status_code, [302, 401, 403])
    
    def test_cross_business_data_protection(self):
        """בדיקת הגנה על נתונים בין עסקים"""
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
            db.session.commit()
            
            # יצירת לקוח בעסק אחר
            other_customer = CRMCustomer(
                name='לקוח של עסק אחר',
                phone='+972509999999',
                business_id=other_business.id,
                status='active'
            )
            db.session.add(other_customer)
            db.session.commit()
            
            with self.client.session_transaction() as sess:
                sess['user_id'] = self.test_user.id
            
            # ניסיון גישה ללקוח של עסק אחר
            response = self.client.get(f'/crm/customer/{other_customer.id}')
            
            # בדיקה שהגישה נדחית
            self.assertIn(response.status_code, [302, 403])

if __name__ == '__main__':
    # הרצת הבדיקות
    unittest.main(verbosity=2)