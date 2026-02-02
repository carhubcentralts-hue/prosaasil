"""
Test to verify appointments created via auto_meeting.py get proper calendar_id assignment
This addresses the issue where calendar filtering returns 0 results for specific calendars
"""
import os
from datetime import datetime, timedelta


def test_auto_meeting_assigns_calendar_id():
    """
    Verify that auto-generated appointments from phone calls get calendar_id assigned
    
    This test ensures:
    1. Auto appointments created via auto_meeting.py have calendar_id set
    2. The calendar_id matches the default calendar for the business
    3. Appointments can be filtered by calendar_id successfully
    """
    # Set migration mode to avoid DB initialization during tests
    os.environ['MIGRATION_MODE'] = '1'
    
    from server.app_factory import create_app
    from server.db import db
    from server.models_sql import Business, BusinessCalendar, Appointment, CallLog
    from server.auto_meeting import create_auto_appointment_from_call
    
    app = create_app()
    
    with app.app_context():
        # Clean up any test data
        test_business_name = "Test Business for Calendar Assignment"
        existing_business = Business.query.filter_by(name=test_business_name).first()
        if existing_business:
            # Clean up appointments, calendars, and call logs first
            Appointment.query.filter_by(business_id=existing_business.id).delete()
            BusinessCalendar.query.filter_by(business_id=existing_business.id).delete()
            CallLog.query.filter_by(business_id=existing_business.id).delete()
            db.session.delete(existing_business)
            db.session.commit()
        
        # Create a test business
        business = Business(
            name=test_business_name,
            phone="+972501234567",
            business_type="test",
            timezone="Asia/Jerusalem"
        )
        db.session.add(business)
        db.session.commit()
        business_id = business.id
        
        # Create a default calendar for the business
        calendar = BusinessCalendar(
            business_id=business_id,
            name="Test Calendar",
            type_key="test_calendar",
            provider="internal",
            is_active=True,
            priority=10,
            default_duration_minutes=60,
            allowed_tags=["פגישה", "ייעוץ"]
        )
        db.session.add(calendar)
        db.session.commit()
        calendar_id = calendar.id
        
        # Create a call log for the appointment
        call_log = CallLog(
            business_id=business_id,
            call_sid="test_call_sid_123",
            from_phone="+972501234567",
            to_phone="+972509876543",
            status="completed",
            duration=120,
            direction="inbound"
        )
        db.session.add(call_log)
        db.session.commit()
        
        # Prepare lead info for creating an appointment
        meeting_time = datetime.now() + timedelta(days=1)
        lead_info = {
            'customer_name': 'Test Customer',
            'appointment_time': meeting_time.isoformat(),
            'appointment_title': 'Test Appointment',
            'appointment_description': 'Test description',
            'completed_count': 5
        }
        
        conversation_history = [
            {'user': 'שלום, אני רוצה לקבוע פגישה', 'bot': 'בטח, אשמח לעזור'},
            {'user': 'מחר בשעה 14:00', 'bot': 'מצוין, רשמתי'}
        ]
        
        # Create appointment using auto_meeting function
        result = create_auto_appointment_from_call(
            call_sid="test_call_sid_123",
            lead_info=lead_info,
            conversation_history=conversation_history,
            phone_number="+972509876543"
        )
        
        # Verify the appointment was created
        assert result is not None, "Appointment creation should return a result"
        assert result.get('success') is True, f"Appointment creation should succeed, got: {result}"
        
        appointment_id = result.get('appointment_id')
        assert appointment_id is not None, "Appointment ID should be returned"
        
        # Fetch the created appointment
        appointment = Appointment.query.get(appointment_id)
        assert appointment is not None, "Appointment should exist in database"
        
        # ✅ CRITICAL CHECK: Verify calendar_id is assigned
        assert appointment.calendar_id is not None, \
            "❌ BUG: Appointment calendar_id is NULL - this causes filtering to fail!"
        
        assert appointment.calendar_id == calendar_id, \
            f"Appointment should be assigned to default calendar (expected {calendar_id}, got {appointment.calendar_id})"
        
        # Verify we can filter appointments by calendar_id
        filtered_appointments = Appointment.query.filter(
            Appointment.business_id == business_id,
            Appointment.calendar_id == calendar_id
        ).all()
        
        assert len(filtered_appointments) > 0, \
            "Should find appointments when filtering by calendar_id"
        
        assert appointment_id in [apt.id for apt in filtered_appointments], \
            "Created appointment should appear in calendar-filtered results"
        
        # Clean up
        Appointment.query.filter_by(business_id=business_id).delete()
        BusinessCalendar.query.filter_by(business_id=business_id).delete()
        CallLog.query.filter_by(business_id=business_id).delete()
        Business.query.filter_by(id=business_id).delete()
        db.session.commit()
        
        print("✅ Test passed: Auto-generated appointments have calendar_id assigned correctly")


if __name__ == '__main__':
    test_auto_meeting_assigns_calendar_id()
