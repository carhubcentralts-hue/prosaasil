"""
Comprehensive tests for CRM API endpoints following AgentLocator architecture
טסטים מקיפים עבור CRM API לפי ארכיטקטורת AgentLocator
"""
import pytest
import json
from datetime import datetime
from server.app import create_app
from server.models import db, CRMCustomer, Business, User


@pytest.fixture
def app():
    """יצירת אפליקציה לטסטים"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """יצירת קליינט לטסטים"""
    return app.test_client()


@pytest.fixture
def auth_headers(app, client):
    """יצירת headers עם אימות"""
    with app.app_context():
        # יצירת עסק טסט
        business = Business(
            name="עסק טסט",
            phone="03-1234567",
            ai_prompt="AI טסט",
            is_active=True
        )
        db.session.add(business)
        db.session.commit()
        
        # יצירת משתמש טסט
        user = User(
            username="test_user",
            email="test@example.com",
            password_hash="hashed_password",
            role="business",
            business_id=business.id
        )
        db.session.add(user)
        db.session.commit()
        
        # כאן בפרויקט האמיתי יהיה token authentication
        return {"Authorization": f"Bearer test_token_{user.id}"}


def test_get_customers_success(client, auth_headers):
    """בדיקת קבלת רשימת לקוחות בהצלחה"""
    response = client.get('/api/crm/customers', headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'success' in data
    assert 'customers' in data
    assert isinstance(data['customers'], list)


def test_get_customers_unauthorized(client):
    """בדיקת קבלת לקוחות ללא אימות"""
    response = client.get('/api/crm/customers')
    
    assert response.status_code == 401
    data = json.loads(response.data)
    assert 'error' in data


def test_create_customer_success(client, auth_headers):
    """בדיקת יצירת לקוח חדש בהצלחה"""
    customer_data = {
        "name": "לקוח טסט",
        "phone": "050-1234567",
        "email": "customer@test.com",
        "source": "phone"
    }
    
    response = client.post('/api/crm/customers', 
                          json=customer_data, 
                          headers=auth_headers)
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'customer' in data
    assert data['customer']['name'] == customer_data['name']


def test_create_customer_missing_fields(client, auth_headers):
    """בדיקת יצירת לקוח עם שדות חסרים"""
    customer_data = {
        "name": "לקוח ללא טלפון"
        # חסר phone
    }
    
    response = client.post('/api/crm/customers', 
                          json=customer_data, 
                          headers=auth_headers)
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_get_customer_by_id(client, auth_headers, app):
    """בדיקת קבלת לקוח לפי ID"""
    with app.app_context():
        # יצירת לקוח טסט
        customer = CRMCustomer(
            name="לקוח למציאה",
            phone="052-9876543",
            business_id=1
        )
        db.session.add(customer)
        db.session.commit()
        customer_id = customer.id
    
    response = client.get(f'/api/crm/customers/{customer_id}', 
                         headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['customer']['name'] == "לקוח למציאה"


def test_update_customer(client, auth_headers, app):
    """בדיקת עדכון פרטי לקוח"""
    with app.app_context():
        customer = CRMCustomer(
            name="לקוח לעדכון",
            phone="053-1111111",
            business_id=1
        )
        db.session.add(customer)
        db.session.commit()
        customer_id = customer.id
    
    update_data = {
        "name": "לקוח מעודכן",
        "email": "updated@test.com"
    }
    
    response = client.put(f'/api/crm/customers/{customer_id}',
                         json=update_data,
                         headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['customer']['name'] == "לקוח מעודכן"


def test_delete_customer(client, auth_headers, app):
    """בדיקת מחיקת לקוח"""
    with app.app_context():
        customer = CRMCustomer(
            name="לקוח למחיקה",
            phone="054-2222222",
            business_id=1
        )
        db.session.add(customer)
        db.session.commit()
        customer_id = customer.id
    
    response = client.delete(f'/api/crm/customers/{customer_id}',
                           headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True


def test_search_customers(client, auth_headers, app):
    """בדיקת חיפוש לקוחות"""
    with app.app_context():
        # יצירת מספר לקוחות לחיפוש
        customers = [
            CRMCustomer(name="יוסי כהן", phone="050-1111111", business_id=1),
            CRMCustomer(name="שרה לוי", phone="052-2222222", business_id=1),
            CRMCustomer(name="דוד כהן", phone="053-3333333", business_id=1)
        ]
        for customer in customers:
            db.session.add(customer)
        db.session.commit()
    
    # חיפוש לפי שם
    response = client.get('/api/crm/customers/search?q=כהן',
                         headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert len(data['customers']) == 2  # יוסי כהן ודוד כהן


def test_customer_statistics(client, auth_headers, app):
    """בדיקת סטטיסטיקות לקוחות"""
    with app.app_context():
        # יצירת לקוחות עם סטטוסים שונים
        customers = [
            CRMCustomer(name="לקוח פעיל 1", phone="050-1111111", 
                       business_id=1, status="active"),
            CRMCustomer(name="לקוח פעיל 2", phone="052-2222222", 
                       business_id=1, status="active"),
            CRMCustomer(name="פרוספקט", phone="053-3333333", 
                       business_id=1, status="prospect")
        ]
        for customer in customers:
            db.session.add(customer)
        db.session.commit()
    
    response = client.get('/api/crm/customers/stats',
                         headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'stats' in data
    assert data['stats']['total'] == 3
    assert data['stats']['active'] == 2
    assert data['stats']['prospect'] == 1


def test_business_isolation(client, app):
    """בדיקת הפרדה בין עסקים - לקוח של עסק אחד לא יכול לראות לקוחות של עסק אחר"""
    with app.app_context():
        # יצירת שני עסקים
        business1 = Business(name="עסק 1", phone="03-1111111", ai_prompt="AI 1")
        business2 = Business(name="עסק 2", phone="03-2222222", ai_prompt="AI 2")
        db.session.add_all([business1, business2])
        db.session.commit()
        
        # יצירת משתמשים לכל עסק
        user1 = User(username="user1", email="user1@test.com", 
                    password_hash="hash1", business_id=business1.id)
        user2 = User(username="user2", email="user2@test.com", 
                    password_hash="hash2", business_id=business2.id)
        db.session.add_all([user1, user2])
        db.session.commit()
        
        # יצירת לקוחות לכל עסק
        customer1 = CRMCustomer(name="לקוח עסק 1", phone="050-1111111", 
                               business_id=business1.id)
        customer2 = CRMCustomer(name="לקוח עסק 2", phone="050-2222222", 
                               business_id=business2.id)
        db.session.add_all([customer1, customer2])
        db.session.commit()
    
    # בדיקה שמשתמש של עסק 1 רואה רק את הלקוחות שלו
    headers1 = {"Authorization": f"Bearer test_token_{user1.id}"}
    response1 = client.get('/api/crm/customers', headers=headers1)
    
    assert response1.status_code == 200
    data1 = json.loads(response1.data)
    assert len(data1['customers']) == 1
    assert data1['customers'][0]['name'] == "לקוח עסק 1"


def test_api_error_handling(client, auth_headers):
    """בדיקת מנגנון טיפול בשגיאות API"""
    # בדיקת לקוח שלא קיים
    response = client.get('/api/crm/customers/99999', headers=auth_headers)
    assert response.status_code == 404
    
    # בדיקת נתונים לא תקינים
    invalid_data = {"invalid": "data"}
    response = client.post('/api/crm/customers', 
                          json=invalid_data, 
                          headers=auth_headers)
    assert response.status_code == 400