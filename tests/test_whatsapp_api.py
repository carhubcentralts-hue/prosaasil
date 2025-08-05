"""
Comprehensive tests for WhatsApp API endpoints following AgentLocator architecture
טסטים מקיפים עבור WhatsApp API לפי ארכיטקטורת AgentLocator
"""
import pytest
import json
from datetime import datetime
from server.app import create_app
from server.models import db, WhatsAppConversation, WhatsAppMessage, Business, User


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
            name="עסק WhatsApp טסט",
            phone="03-1234567",
            whatsapp_phone="+972501234567",
            ai_prompt="AI WhatsApp טסט",
            is_active=True
        )
        db.session.add(business)
        db.session.commit()
        
        user = User(
            username="whatsapp_user",
            email="whatsapp@test.com",
            password_hash="hashed_password",
            role="business",
            business_id=business.id,
            can_access_whatsapp=True
        )
        db.session.add(user)
        db.session.commit()
        
        return {"Authorization": f"Bearer test_token_{user.id}"}


def test_get_conversations_success(client, auth_headers):
    """בדיקת קבלת רשימת שיחות WhatsApp בהצלחה"""
    response = client.get('/api/whatsapp/conversations', headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'success' in data
    assert 'conversations' in data
    assert isinstance(data['conversations'], list)


def test_get_conversations_unauthorized(client):
    """בדיקת גישה לשיחות ללא אימות"""
    response = client.get('/api/whatsapp/conversations')
    
    assert response.status_code == 401
    data = json.loads(response.data)
    assert 'error' in data


def test_create_conversation(client, auth_headers, app):
    """בדיקת יצירת שיחת WhatsApp חדשה"""
    conversation_data = {
        "customer_number": "+972501234567",
        "customer_name": "לקוח WhatsApp",
        "status": "active"
    }
    
    response = client.post('/api/whatsapp/conversations',
                          json=conversation_data,
                          headers=auth_headers)
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'conversation' in data
    assert data['conversation']['customer_number'] == conversation_data['customer_number']


def test_send_message_success(client, auth_headers, app):
    """בדיקת שליחת הודעת WhatsApp בהצלחה"""
    with app.app_context():
        # יצירת שיחה קיימת
        conversation = WhatsAppConversation(
            customer_number="+972501234567",
            customer_name="לקוח טסט",
            business_id=1,
            status="active"
        )
        db.session.add(conversation)
        db.session.commit()
        conversation_id = conversation.id
    
    message_data = {
        "message_body": "הודעת טסט",
        "message_type": "text"
    }
    
    response = client.post(f'/api/whatsapp/conversations/{conversation_id}/messages',
                          json=message_data,
                          headers=auth_headers)
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'message' in data


def test_get_conversation_messages(client, auth_headers, app):
    """בדיקת קבלת הודעות של שיחה ספציפית"""
    with app.app_context():
        conversation = WhatsAppConversation(
            customer_number="+972502222222",
            customer_name="לקוח עם הודעות",
            business_id=1,
            status="active"
        )
        db.session.add(conversation)
        db.session.commit()
        
        # יצירת הודעות טסט
        messages = [
            WhatsAppMessage(
                conversation_id=conversation.id,
                from_number="+972502222222",
                to_number="+972501234567",
                message_body="הודעה 1",
                direction="inbound",
                business_id=1
            ),
            WhatsAppMessage(
                conversation_id=conversation.id,
                from_number="+972501234567",
                to_number="+972502222222",
                message_body="תשובה 1",
                direction="outbound",
                business_id=1
            )
        ]
        for msg in messages:
            db.session.add(msg)
        db.session.commit()
        
        conversation_id = conversation.id
    
    response = client.get(f'/api/whatsapp/conversations/{conversation_id}/messages',
                         headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert len(data['messages']) == 2


def test_whatsapp_webhook_receive(client, app):
    """בדיקת webhook לקבלת הודעות WhatsApp"""
    webhook_data = {
        "From": "whatsapp:+972501111111",
        "To": "whatsapp:+972501234567",
        "Body": "הודעה נכנסת מ-WhatsApp",
        "MessageSid": "SM1234567890abcdef",
        "AccountSid": "AC1234567890abcdef"
    }
    
    response = client.post('/api/whatsapp/webhook',
                          data=webhook_data,
                          content_type='application/x-www-form-urlencoded')
    
    assert response.status_code == 200
    # בדיקת תוכן TwiML response
    assert b'<Response>' in response.data
    assert b'</Response>' in response.data


def test_conversation_status_update(client, auth_headers, app):
    """בדיקת עדכון סטטוס שיחה"""
    with app.app_context():
        conversation = WhatsAppConversation(
            customer_number="+972503333333",
            customer_name="לקוח לעדכון סטטוס",
            business_id=1,
            status="active"
        )
        db.session.add(conversation)
        db.session.commit()
        conversation_id = conversation.id
    
    status_data = {"status": "closed"}
    
    response = client.put(f'/api/whatsapp/conversations/{conversation_id}/status',
                         json=status_data,
                         headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['conversation']['status'] == "closed"


def test_whatsapp_business_permissions(client, app):
    """בדיקת הרשאות עסק לשימוש ב-WhatsApp"""
    with app.app_context():
        # יצירת עסק ללא הרשאות WhatsApp
        business = Business(
            name="עסק ללא WhatsApp",
            phone="03-9999999",
            ai_prompt="AI טסט",
            is_active=True
        )
        db.session.add(business)
        db.session.commit()
        
        user = User(
            username="no_whatsapp_user",
            email="no_whatsapp@test.com",
            password_hash="hashed_password",
            role="business",
            business_id=business.id,
            can_access_whatsapp=False
        )
        db.session.add(user)
        db.session.commit()
        
        headers = {"Authorization": f"Bearer test_token_{user.id}"}
    
    response = client.get('/api/whatsapp/conversations', headers=headers)
    
    assert response.status_code == 403
    data = json.loads(response.data)
    assert 'error' in data


def test_whatsapp_analytics(client, auth_headers, app):
    """בדיקת אנליטיקס WhatsApp"""
    with app.app_context():
        # יצירת נתונים לאנליטיקס
        conversations = [
            WhatsAppConversation(
                customer_number="+972504444444",
                customer_name="לקוח 1",
                business_id=1,
                status="active"
            ),
            WhatsAppConversation(
                customer_number="+972505555555",
                customer_name="לקוח 2",
                business_id=1,
                status="closed"
            )
        ]
        for conv in conversations:
            db.session.add(conv)
        db.session.commit()
    
    response = client.get('/api/whatsapp/analytics', headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'analytics' in data
    assert 'total_conversations' in data['analytics']
    assert 'active_conversations' in data['analytics']


def test_message_search(client, auth_headers, app):
    """בדיקת חיפוש הודעות"""
    with app.app_context():
        conversation = WhatsAppConversation(
            customer_number="+972506666666",
            customer_name="לקוח לחיפוש",
            business_id=1,
            status="active"
        )
        db.session.add(conversation)
        db.session.commit()
        
        messages = [
            WhatsAppMessage(
                conversation_id=conversation.id,
                from_number="+972506666666",
                to_number="+972501234567",
                message_body="היי, אני מחפש מידע על המוצר",
                direction="inbound",
                business_id=1
            ),
            WhatsAppMessage(
                conversation_id=conversation.id,
                from_number="+972501234567",
                to_number="+972506666666",
                message_body="בטח! אני אשמח לעזור",
                direction="outbound",
                business_id=1
            )
        ]
        for msg in messages:
            db.session.add(msg)
        db.session.commit()
    
    response = client.get('/api/whatsapp/messages/search?q=מוצר',
                         headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert len(data['messages']) == 1
    assert "מוצר" in data['messages'][0]['message_body']


def test_ai_response_generation(client, auth_headers, app):
    """בדיקת יצירת תגובות AI אוטומטיות"""
    with app.app_context():
        conversation = WhatsAppConversation(
            customer_number="+972507777777",
            customer_name="לקוח AI",
            business_id=1,
            status="active"
        )
        db.session.add(conversation)
        db.session.commit()
        conversation_id = conversation.id
    
    ai_request = {
        "message": "מתי אתם פתוחים?",
        "generate_ai_response": True
    }
    
    response = client.post(f'/api/whatsapp/conversations/{conversation_id}/ai-response',
                          json=ai_request,
                          headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert 'ai_response' in data


def test_bulk_message_operations(client, auth_headers, app):
    """בדיקת פעולות מסיביות על הודעות"""
    with app.app_context():
        # יצירת מספר שיחות
        conversations = []
        for i in range(3):
            conv = WhatsAppConversation(
                customer_number=f"+97250888888{i}",
                customer_name=f"לקוח {i+1}",
                business_id=1,
                status="active"
            )
            db.session.add(conv)
            conversations.append(conv)
        db.session.commit()
        
        conversation_ids = [conv.id for conv in conversations]
    
    bulk_message_data = {
        "conversation_ids": conversation_ids,
        "message_body": "הודעה מסיבית לכולם",
        "message_type": "text"
    }
    
    response = client.post('/api/whatsapp/bulk-message',
                          json=bulk_message_data,
                          headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['sent_count'] == 3