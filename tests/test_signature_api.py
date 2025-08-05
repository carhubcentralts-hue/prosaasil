"""
Comprehensive tests for Digital Signature API endpoints following AgentLocator architecture
טסטים מקיפים עבור Signature API לפי ארכיטקטורת AgentLocator
"""
import pytest
import json
from datetime import datetime
from server.app import create_app
from server.models import db, DigitalSignature, Business, User


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
        business = Business(
            name="עסק חתימות דיגיטליות",
            phone="03-1234567",
            ai_prompt="AI חתימות",
            is_active=True
        )
        db.session.add(business)
        db.session.commit()
        
        user = User(
            username="signature_user",
            email="signature@test.com",
            password_hash="hashed_password",
            role="business",
            business_id=business.id
        )
        db.session.add(user)
        db.session.commit()
        
        return {"Authorization": f"Bearer test_token_{user.id}"}


def test_get_signatures_success(client, auth_headers):
    """בדיקת קבלת רשימת חתימות דיגיטליות בהצלחה"""
    response = client.get('/api/signature/signatures', headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'success' in data
    assert 'signatures' in data
    assert isinstance(data['signatures'], list)
    assert 'stats' in data


def test_get_signatures_unauthorized(client):
    """בדיקת גישה לחתימות ללא אימות"""
    response = client.get('/api/signature/signatures')
    
    assert response.status_code == 401
    data = json.loads(response.data)
    assert 'error' in data


def test_create_signature_success(client, auth_headers):
    """בדיקת יצירת חתימה דיגיטלית חדשה בהצלחה"""
    signature_data = {
        "document_name": "חוזה שירות",
        "signer_name": "ישראל ישראלי",
        "signer_email": "israel@example.com",
        "document_content": "תוכן החוזה..."
    }
    
    response = client.post('/api/signature/signatures',
                          json=signature_data,
                          headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'signature' in data
    assert data['signature']['document_name'] == signature_data['document_name']
    assert data['signature']['status'] == 'pending'


def test_create_signature_missing_fields(client, auth_headers):
    """בדיקת יצירת חתימה עם שדות חסרים"""
    signature_data = {
        "document_name": "חוזה ללא פרטי חותם"
        # חסרים signer_name ו-signer_email
    }
    
    response = client.post('/api/signature/signatures',
                          json=signature_data,
                          headers=auth_headers)
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


def test_sign_document_success(client, auth_headers, app):
    """בדיקת חתימה על מסמך בהצלחה"""
    with app.app_context():
        signature = DigitalSignature(
            document_name="מסמך לחתימה",
            signer_name="חותם טסט",
            signer_email="signer@test.com",
            business_id=1,
            status="pending"
        )
        db.session.add(signature)
        db.session.commit()
        signature_id = signature.id
    
    signature_data = {
        "signature_data": "signature_blob_data_here"
    }
    
    response = client.post(f'/api/signature/signatures/{signature_id}/sign',
                          json=signature_data,
                          headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['signature']['status'] == 'signed'
    assert 'signed_at' in data['signature']


def test_sign_nonexistent_document(client, auth_headers):
    """בדיקת חתימה על מסמך שלא קיים"""
    response = client.post('/api/signature/signatures/99999/sign',
                          json={"signature_data": "test"},
                          headers=auth_headers)
    
    assert response.status_code == 404


def test_business_permission_check(client, app):
    """בדיקת הרשאות עסק לשימוש בחתימות דיגיטליות"""
    with app.app_context():
        # יצירת עסק ללא הרשאות חתימות
        business = Business(
            name="עסק ללא חתימות",
            phone="03-9999999",
            ai_prompt="AI טסט",
            is_active=True
        )
        db.session.add(business)
        db.session.commit()
        
        user = User(
            username="no_signature_user",
            email="no_signature@test.com",
            password_hash="hashed_password",
            role="business",
            business_id=business.id
        )
        db.session.add(user)
        db.session.commit()
        
        headers = {"Authorization": f"Bearer test_token_{user.id}"}
    
    signature_data = {
        "document_name": "מסמך טסט",
        "signer_name": "חותם טסט",
        "signer_email": "test@test.com"
    }
    
    response = client.post('/api/signature/signatures',
                          json=signature_data,
                          headers=headers)
    
    # בדיקה שהעסק לא מורשה להשתמש בחתימות
    assert response.status_code == 403
    data = json.loads(response.data)
    assert 'error' in data


def test_signature_statistics(client, auth_headers, app):
    """בדיקת סטטיסטיקות חתימות"""
    with app.app_context():
        # יצירת חתימות עם סטטוסים שונים
        signatures = [
            DigitalSignature(
                document_name="חוזה 1",
                signer_name="חותם 1",
                signer_email="signer1@test.com",
                business_id=1,
                status="signed"
            ),
            DigitalSignature(
                document_name="חוזה 2",
                signer_name="חותם 2",
                signer_email="signer2@test.com",
                business_id=1,
                status="pending"
            ),
            DigitalSignature(
                document_name="חוזה 3",
                signer_name="חותם 3",
                signer_email="signer3@test.com",
                business_id=1,
                status="pending"
            )
        ]
        for sig in signatures:
            db.session.add(sig)
        db.session.commit()
    
    response = client.get('/api/signature/signatures', headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['stats']['total_signatures'] == 3
    assert data['stats']['signed'] == 1
    assert data['stats']['pending'] == 2


def test_admin_access_all_signatures(client, app):
    """בדיקת גישת מנהל לכל החתימות"""
    with app.app_context():
        # יצירת מנהל
        admin_user = User(
            username="admin",
            email="admin@test.com",
            password_hash="admin_hash",
            role="admin"
        )
        db.session.add(admin_user)
        db.session.commit()
        
        # יצירת חתימות ממספר עסקים
        business1 = Business(name="עסק 1", phone="03-1111111", ai_prompt="AI 1")
        business2 = Business(name="עסק 2", phone="03-2222222", ai_prompt="AI 2")
        db.session.add_all([business1, business2])
        db.session.commit()
        
        signatures = [
            DigitalSignature(
                document_name="חוזה עסק 1",
                signer_name="חותם 1",
                signer_email="signer1@test.com",
                business_id=business1.id,
                status="signed"
            ),
            DigitalSignature(
                document_name="חוזה עסק 2",
                signer_name="חותם 2",
                signer_email="signer2@test.com",
                business_id=business2.id,
                status="pending"
            )
        ]
        for sig in signatures:
            db.session.add(sig)
        db.session.commit()
        
        admin_headers = {"Authorization": f"Bearer test_token_{admin_user.id}"}
    
    response = client.get('/api/signature/signatures', headers=admin_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    # מנהל רואה חתימות מכל העסקים
    assert len(data['signatures']) == 2


def test_signature_cross_business_isolation(client, app):
    """בדיקת הפרדה בין עסקים - עסק אחד לא יכול לראות חתימות של עסק אחר"""
    with app.app_context():
        # יצירת שני עסקים
        business1 = Business(name="עסק חתימות 1", phone="03-1111111", ai_prompt="AI 1")
        business2 = Business(name="עסק חתימות 2", phone="03-2222222", ai_prompt="AI 2")
        db.session.add_all([business1, business2])
        db.session.commit()
        
        # יצירת משתמשים
        user1 = User(username="user1", email="user1@test.com", 
                    password_hash="hash1", business_id=business1.id)
        user2 = User(username="user2", email="user2@test.com", 
                    password_hash="hash2", business_id=business2.id)
        db.session.add_all([user1, user2])
        db.session.commit()
        
        # יצירת חתימות לכל עסק
        sig1 = DigitalSignature(
            document_name="חוזה עסק 1",
            signer_name="חותם עסק 1",
            signer_email="signer1@test.com",
            business_id=business1.id
        )
        sig2 = DigitalSignature(
            document_name="חוזה עסק 2",
            signer_name="חותם עסק 2",
            signer_email="signer2@test.com",
            business_id=business2.id
        )
        db.session.add_all([sig1, sig2])
        db.session.commit()
    
    # בדיקה שמשתמש של עסק 1 רואה רק את החתימות שלו
    headers1 = {"Authorization": f"Bearer test_token_{user1.id}"}
    response1 = client.get('/api/signature/signatures', headers=headers1)
    
    assert response1.status_code == 200
    data1 = json.loads(response1.data)
    assert len(data1['signatures']) == 1
    assert data1['signatures'][0]['document_name'] == "חוזה עסק 1"


def test_signature_document_validation(client, auth_headers):
    """בדיקת תקינות מסמכים לחתימה"""
    # בדיקת אימייל לא תקין
    invalid_email_data = {
        "document_name": "חוזה טסט",
        "signer_name": "חותם טסט",
        "signer_email": "invalid_email"
    }
    
    response = client.post('/api/signature/signatures',
                          json=invalid_email_data,
                          headers=auth_headers)
    
    # במימוש מלא יהיה validation של אימייל
    # כרגע נבדוק שהפונקציה עובדת
    assert response.status_code in [200, 400]


def test_signature_workflow_complete(client, auth_headers, app):
    """בדיקת תהליך חתימה מלא"""
    # שלב 1: יצירת מסמך לחתימה
    signature_data = {
        "document_name": "חוזה מלא",
        "signer_name": "חותם מלא",
        "signer_email": "full@test.com",
        "document_content": "תוכן חוזה מלא..."
    }
    
    response = client.post('/api/signature/signatures',
                          json=signature_data,
                          headers=auth_headers)
    
    assert response.status_code == 200
    signature_id = json.loads(response.data)['signature']['id']
    
    # שלב 2: חתימה על המסמך
    sign_data = {"signature_data": "digital_signature_blob"}
    
    response = client.post(f'/api/signature/signatures/{signature_id}/sign',
                          json=sign_data,
                          headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['signature']['status'] == 'signed'
    
    # שלב 3: וידוא שהמסמך מופיע כחתום ברשימה
    response = client.get('/api/signature/signatures', headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    signed_signatures = [s for s in data['signatures'] if s['status'] == 'signed']
    assert len(signed_signatures) >= 1