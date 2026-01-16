"""
Test timezone fixes for appointments and reminders

Verifies that dates are stored and retrieved correctly without timezone shifts
"""
import pytest
from datetime import datetime
from server.app_factory import create_app
from server.db import db
from server.models_sql import Appointment, LeadReminder, Business, User
import json


@pytest.fixture
def app():
    """Create test Flask application"""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def test_user(app):
    """Create test user and business"""
    with app.app_context():
        # Create business
        business = Business(
            name="Test Business",
            phone="+972501234567",
            email="test@example.com"
        )
        db.session.add(business)
        db.session.flush()
        
        # Create user
        from werkzeug.security import generate_password_hash
        user = User(
            business_id=business.id,
            email="owner@example.com",
            password_hash=generate_password_hash("password123"),
            name="Test Owner",
            role="owner",
            is_active=True
        )
        db.session.add(user)
        db.session.commit()
        
        return {"user": user, "business": business}


def test_appointment_timezone_without_z_suffix(client, app, test_user):
    """Test creating appointment with local time (no Z suffix)"""
    with app.app_context():
        user = test_user["user"]
        business = test_user["business"]
        
        # Login
        response = client.post('/api/auth/login', json={
            'email': 'owner@example.com',
            'password': 'password123'
        })
        assert response.status_code == 200
        
        # Create appointment with local Israel time (19:00 = 7 PM)
        # The time should be stored as-is without UTC conversion
        appointment_data = {
            'title': 'Test Meeting',
            'start_time': '2024-01-20T19:00:00',  # 7 PM local time, no Z suffix
            'end_time': '2024-01-20T20:00:00',    # 8 PM local time, no Z suffix
            'appointment_type': 'meeting',
            'status': 'scheduled',
            'priority': 'medium'
        }
        
        response = client.post('/api/calendar/appointments', 
                              json=appointment_data,
                              headers={'Content-Type': 'application/json'})
        
        if response.status_code != 201:
            print(f"Error response: {response.get_json()}")
        assert response.status_code == 201
        
        # Fetch the appointment from DB directly
        apt = Appointment.query.first()
        assert apt is not None
        
        # Verify times are stored correctly (as naive datetime in local time)
        assert apt.start_time.hour == 19, f"Expected hour 19, got {apt.start_time.hour}"
        assert apt.start_time.minute == 0
        assert apt.end_time.hour == 20
        assert apt.end_time.minute == 0
        
        # Verify no timezone info
        assert apt.start_time.tzinfo is None
        assert apt.end_time.tzinfo is None


def test_appointment_timezone_with_z_suffix_legacy(client, app, test_user):
    """Test creating appointment with old format (Z suffix) - backward compatibility"""
    with app.app_context():
        user = test_user["user"]
        business = test_user["business"]
        
        # Login
        response = client.post('/api/auth/login', json={
            'email': 'owner@example.com',
            'password': 'password123'
        })
        assert response.status_code == 200
        
        # Create appointment with UTC format (legacy)
        # 19:00 local = 16:00 UTC (if we were doing UTC conversion)
        # But our fix should strip the Z and treat it as local time
        appointment_data = {
            'title': 'Test Meeting',
            'start_time': '2024-01-20T19:00:00Z',
            'end_time': '2024-01-20T20:00:00Z',
            'appointment_type': 'meeting',
            'status': 'scheduled',
            'priority': 'medium'
        }
        
        response = client.post('/api/calendar/appointments', 
                              json=appointment_data,
                              headers={'Content-Type': 'application/json'})
        
        assert response.status_code == 201
        
        # Fetch the appointment
        apt = Appointment.query.first()
        assert apt is not None
        
        # With our fix, even Z suffix is stripped and treated as local time
        assert apt.start_time.hour == 19, f"Expected hour 19, got {apt.start_time.hour}"


def test_reminder_timezone_without_z_suffix(client, app, test_user):
    """Test creating reminder with local time (no Z suffix)"""
    with app.app_context():
        user = test_user["user"]
        business = test_user["business"]
        
        # Login
        response = client.post('/api/auth/login', json={
            'email': 'owner@example.com',
            'password': 'password123'
        })
        assert response.status_code == 200
        
        # Create reminder with local Israel time
        reminder_data = {
            'note': 'Test Reminder',
            'due_at': '2024-01-20T15:30:00',  # 3:30 PM local time
            'priority': 'high',
            'reminder_type': 'general'
        }
        
        response = client.post('/api/reminders', 
                              json=reminder_data,
                              headers={'Content-Type': 'application/json'})
        
        if response.status_code != 201:
            print(f"Error response: {response.get_json()}")
        assert response.status_code == 201
        
        # Fetch the reminder
        reminder = LeadReminder.query.first()
        assert reminder is not None
        
        # Verify time is stored correctly
        assert reminder.due_at.hour == 15
        assert reminder.due_at.minute == 30
        assert reminder.due_at.tzinfo is None


def test_appointment_update_timezone(client, app, test_user):
    """Test updating appointment maintains correct timezone"""
    with app.app_context():
        user = test_user["user"]
        business = test_user["business"]
        
        # Create appointment directly
        apt = Appointment(
            business_id=business.id,
            title="Original Meeting",
            start_time=datetime(2024, 1, 20, 19, 0),  # 7 PM
            end_time=datetime(2024, 1, 20, 20, 0),    # 8 PM
            status='scheduled',
            appointment_type='meeting',
            priority='medium'
        )
        db.session.add(apt)
        db.session.commit()
        apt_id = apt.id
        
        # Login
        response = client.post('/api/auth/login', json={
            'email': 'owner@example.com',
            'password': 'password123'
        })
        assert response.status_code == 200
        
        # Update the appointment - change time to 8 PM
        update_data = {
            'start_time': '2024-01-20T20:00:00',  # Changed to 8 PM
            'end_time': '2024-01-20T21:00:00',
            'title': 'Updated Meeting'
        }
        
        response = client.put(f'/api/calendar/appointments/{apt_id}',
                             json=update_data,
                             headers={'Content-Type': 'application/json'})
        
        if response.status_code != 200:
            print(f"Error response: {response.get_json()}")
        assert response.status_code == 200
        
        # Verify update
        apt = Appointment.query.get(apt_id)
        assert apt.start_time.hour == 20, f"Expected hour 20, got {apt.start_time.hour}"
        assert apt.start_time.minute == 0
        assert apt.title == 'Updated Meeting'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
