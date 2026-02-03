"""
Test for appointment confirmation job fixes

This test verifies:
1. send_message is called with correct parameters (text instead of message)
2. Status checking works properly (status field instead of success field)
3. Appointment validation prevents None appointment_id
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


def test_send_message_parameters():
    """
    Test that send_message is called with correct parameters
    
    This tests Issue 1: Correct parameter names
    - text instead of message
    - No invalid provider or lead_id parameters
    """
    from server.jobs.send_appointment_confirmation_job import send_appointment_confirmation
    from server.models_sql import (
        AppointmentAutomationRun,
        Appointment,
        AppointmentAutomation,
        Business,
        Lead
    )
    
    # Create mock objects
    mock_run = Mock(spec=AppointmentAutomationRun)
    mock_run.id = 1
    mock_run.appointment_id = 100
    mock_run.automation_id = 10
    mock_run.status = 'pending'
    mock_run.attempts = 0
    
    mock_appointment = Mock(spec=Appointment)
    mock_appointment.id = 100
    mock_appointment.status = 'scheduled'
    mock_appointment.lead_id = 200
    mock_appointment.customer_id = None
    mock_appointment.contact_phone = None
    mock_appointment.start_time = datetime.utcnow()
    mock_appointment.location = 'Test Location'
    mock_appointment.created_by = None
    
    mock_automation = Mock(spec=AppointmentAutomation)
    mock_automation.id = 10
    mock_automation.enabled = True
    mock_automation.trigger_status_ids = ['scheduled']
    mock_automation.message_template = 'Hello {first_name}'
    
    mock_lead = Mock(spec=Lead)
    mock_lead.phone_e164 = '+972501234567'
    mock_lead.phone_raw = '0501234567'
    mock_lead.first_name = 'Test'
    mock_lead.name = 'Test User'
    
    mock_business = Mock(spec=Business)
    mock_business.id = 1
    mock_business.name = 'Test Business'
    
    # Mock send_message to capture the call
    with patch('server.jobs.send_appointment_confirmation_job.AppointmentAutomationRun') as MockRun, \
         patch('server.jobs.send_appointment_confirmation_job.Appointment') as MockAppointment, \
         patch('server.jobs.send_appointment_confirmation_job.AppointmentAutomation') as MockAutomation, \
         patch('server.jobs.send_appointment_confirmation_job.Lead') as MockLead, \
         patch('server.jobs.send_appointment_confirmation_job.Business') as MockBusiness, \
         patch('server.jobs.send_appointment_confirmation_job.send_message') as mock_send, \
         patch('server.jobs.send_appointment_confirmation_job.db') as mock_db:
        
        # Setup query mocks
        MockRun.query.filter_by.return_value.first.return_value = mock_run
        MockAppointment.query.filter_by.return_value.first.return_value = mock_appointment
        MockAutomation.query.filter_by.return_value.first.return_value = mock_automation
        MockLead.query.get.return_value = mock_lead
        MockBusiness.query.get.return_value = mock_business
        
        # Mock send_message to return success
        mock_send.return_value = {'status': 'sent', 'message_id': 'test123'}
        
        # Call the function
        result = send_appointment_confirmation(run_id=1, business_id=1)
        
        # Verify send_message was called with correct parameters
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        
        # Check that text parameter is used (not message)
        assert 'text' in call_args.kwargs, "Should use 'text' parameter"
        assert 'message' not in call_args.kwargs, "Should NOT use 'message' parameter"
        
        # Check that invalid parameters are not used
        assert 'provider' not in call_args.kwargs, "Should NOT use 'provider' parameter"
        assert 'lead_id' not in call_args.kwargs, "Should NOT use 'lead_id' parameter"
        
        # Check required parameters are present
        assert 'business_id' in call_args.kwargs
        assert 'to_phone' in call_args.kwargs
        assert 'context' in call_args.kwargs
        
        # Verify result
        assert result['success'] is True


def test_status_field_checking():
    """
    Test that status field is checked correctly
    
    This tests the fix for status checking instead of success field:
    - Check for status in ['sent', 'queued', 'accepted']
    - Not checking for 'success' field
    """
    from server.jobs.send_appointment_confirmation_job import send_appointment_confirmation
    from server.models_sql import (
        AppointmentAutomationRun,
        Appointment,
        AppointmentAutomation,
        Business,
        Lead
    )
    
    # Create mock objects
    mock_run = Mock(spec=AppointmentAutomationRun)
    mock_run.id = 1
    mock_run.appointment_id = 100
    mock_run.automation_id = 10
    mock_run.status = 'pending'
    mock_run.attempts = 0
    
    mock_appointment = Mock(spec=Appointment)
    mock_appointment.id = 100
    mock_appointment.status = 'scheduled'
    mock_appointment.lead_id = 200
    mock_appointment.customer_id = None
    mock_appointment.contact_phone = None
    mock_appointment.start_time = datetime.utcnow()
    mock_appointment.location = 'Test Location'
    mock_appointment.created_by = None
    
    mock_automation = Mock(spec=AppointmentAutomation)
    mock_automation.id = 10
    mock_automation.enabled = True
    mock_automation.trigger_status_ids = ['scheduled']
    mock_automation.message_template = 'Test message'
    
    mock_lead = Mock(spec=Lead)
    mock_lead.phone_e164 = '+972501234567'
    mock_lead.phone_raw = '0501234567'
    mock_lead.first_name = 'Test'
    mock_lead.name = 'Test User'
    
    mock_business = Mock(spec=Business)
    mock_business.id = 1
    mock_business.name = 'Test Business'
    
    with patch('server.jobs.send_appointment_confirmation_job.AppointmentAutomationRun') as MockRun, \
         patch('server.jobs.send_appointment_confirmation_job.Appointment') as MockAppointment, \
         patch('server.jobs.send_appointment_confirmation_job.AppointmentAutomation') as MockAutomation, \
         patch('server.jobs.send_appointment_confirmation_job.Lead') as MockLead, \
         patch('server.jobs.send_appointment_confirmation_job.Business') as MockBusiness, \
         patch('server.jobs.send_appointment_confirmation_job.send_message') as mock_send, \
         patch('server.jobs.send_appointment_confirmation_job.db') as mock_db:
        
        # Setup query mocks
        MockRun.query.filter_by.return_value.first.return_value = mock_run
        MockAppointment.query.filter_by.return_value.first.return_value = mock_appointment
        MockAutomation.query.filter_by.return_value.first.return_value = mock_automation
        MockLead.query.get.return_value = mock_lead
        MockBusiness.query.get.return_value = mock_business
        
        # Test 1: status='sent' should succeed
        mock_send.return_value = {'status': 'sent'}
        result = send_appointment_confirmation(run_id=1, business_id=1)
        assert result['success'] is True
        
        # Reset mock
        mock_run.status = 'pending'
        
        # Test 2: status='queued' should succeed
        mock_send.return_value = {'status': 'queued'}
        result = send_appointment_confirmation(run_id=1, business_id=1)
        assert result['success'] is True
        
        # Reset mock
        mock_run.status = 'pending'
        
        # Test 3: status='error' should fail
        mock_send.return_value = {'status': 'error', 'error': 'Test error'}
        result = send_appointment_confirmation(run_id=1, business_id=1)
        assert result['success'] is False
        assert 'error' in result


def test_appointment_id_validation():
    """
    Test that appointment_id validation prevents None values
    
    This tests Issue 3: Validation before database operations
    """
    from server.services.appointment_automation_service import schedule_automation_jobs
    from server.models_sql import Appointment
    
    with patch('server.services.appointment_automation_service.Appointment') as MockAppointment, \
         patch('server.services.appointment_automation_service.get_active_automations') as mock_automations:
        
        # Test 1: Appointment not found
        MockAppointment.query.filter_by.return_value.first.return_value = None
        result = schedule_automation_jobs(appointment_id=999, business_id=1)
        assert 'error' in result
        assert result['scheduled'] == 0
        
        # Test 2: Appointment exists but has no ID (edge case)
        # This simulates a database inconsistency where an appointment object
        # was returned by the query but has a null ID field
        mock_appointment = Mock(spec=Appointment)
        mock_appointment.id = None  # Invalid state - should not create automation runs
        mock_appointment.status = 'scheduled'
        MockAppointment.query.filter_by.return_value.first.return_value = mock_appointment
        
        result = schedule_automation_jobs(appointment_id=100, business_id=1)
        assert 'error' in result
        assert result['scheduled'] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
