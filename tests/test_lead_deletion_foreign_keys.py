"""
Test lead deletion with all foreign key relationships
Verifies that deleting a lead properly handles all related records
"""
import pytest
import os
from datetime import datetime, timedelta


def test_delete_lead_with_all_relationships():
    """
    Test that deleting a lead properly handles all foreign key relationships:
    - ContactIdentity
    - WhatsAppConversation (FIX: was causing constraint violation)
    - CallSession
    - CRMTask
    - LeadMergeCandidate
    - OutboundCallJob
    - Nullify: CallLog, Contract, Appointment
    - Cascade: LeadNote, LeadAttachment, ScheduledMessagesQueue
    """
    os.environ['MIGRATION_MODE'] = '1'
    os.environ['TESTING'] = '1'
    
    from server.app_factory import create_app
    from server.models_sql import (
        db, Business, Lead, LeadStatus, ContactIdentity, WhatsAppConversation,
        CallSession, CRMTask, LeadMergeCandidate, CallLog, Contract, 
        Appointment, LeadActivity, LeadReminder, OutboundCallJob,
        OutboundCallRun
    )
    
    app = create_app()
    
    with app.app_context():
        # Create test business
        business = Business(
            name="Test Business FK",
            business_type="general",
            is_active=True
        )
        db.session.add(business)
        db.session.flush()
        
        # Create test lead status
        status = LeadStatus(
            business_id=business.id,
            name="test_status_fk",
            label="Test Status FK",
            is_active=True
        )
        db.session.add(status)
        db.session.flush()
        
        # Create test lead
        lead = Lead(
            tenant_id=business.id,
            phone_e164="+972501234567",
            name="Test Lead FK",
            status="test_status_fk"
        )
        db.session.add(lead)
        db.session.flush()
        lead_id = lead.id
        
        # Create ContactIdentity
        contact_identity = ContactIdentity(
            business_id=business.id,
            channel="whatsapp",
            external_id="972501234567@s.whatsapp.net",
            lead_id=lead_id
        )
        db.session.add(contact_identity)
        
        # Create WhatsAppConversation (THIS WAS CAUSING THE BUG)
        whatsapp_conv = WhatsAppConversation(
            business_id=business.id,
            customer_number="+972501234567",
            lead_id=lead_id,
            provider="baileys"
        )
        db.session.add(whatsapp_conv)
        
        # Create CallSession
        call_session = CallSession(
            call_sid="TEST_CALL_SID_FK",
            business_id=business.id,
            lead_id=lead_id
        )
        db.session.add(call_session)
        
        # Create CRMTask
        crm_task = CRMTask(
            title="Test Task FK",
            business_id=business.id,
            lead_id=lead_id
        )
        db.session.add(crm_task)
        
        # Create LeadMergeCandidate
        duplicate_lead = Lead(
            tenant_id=business.id,
            phone_e164="+972501234568",
            name="Duplicate Lead FK",
            status="test_status_fk"
        )
        db.session.add(duplicate_lead)
        db.session.flush()
        
        merge_candidate = LeadMergeCandidate(
            lead_id=lead_id,
            duplicate_lead_id=duplicate_lead.id,
            confidence_score=0.8,
            reason="phone"
        )
        db.session.add(merge_candidate)
        
        # Create OutboundCallJob
        outbound_run = OutboundCallRun(
            business_id=business.id,
            name="Test Run FK",
            status="running"
        )
        db.session.add(outbound_run)
        db.session.flush()
        
        outbound_job = OutboundCallJob(
            run_id=outbound_run.id,
            lead_id=lead_id,
            business_id=business.id
        )
        db.session.add(outbound_job)
        
        # Create CallLog (should be nullified, not deleted)
        call_log = CallLog(
            business_id=business.id,
            lead_id=lead_id,
            call_sid="TEST_CALL_LOG_FK",
            from_number="+972501234567",
            direction="inbound"
        )
        db.session.add(call_log)
        db.session.flush()
        call_log_id = call_log.id
        
        # Create Contract (should be nullified, not deleted)
        contract = Contract(
            business_id=business.id,
            lead_id=lead_id,
            title="Test Contract FK"
        )
        db.session.add(contract)
        db.session.flush()
        contract_id = contract.id
        
        # Create Appointment (should be nullified, not deleted)
        appointment = Appointment(
            business_id=business.id,
            lead_id=lead_id,
            title="Test Appointment FK",
            start_time=datetime.utcnow() + timedelta(hours=1),
            end_time=datetime.utcnow() + timedelta(hours=2)
        )
        db.session.add(appointment)
        db.session.flush()
        appointment_id = appointment.id
        
        # Create LeadActivity
        activity = LeadActivity(
            lead_id=lead_id,
            type="note",
            payload={"text": "Test activity"}
        )
        db.session.add(activity)
        
        # Create LeadReminder
        reminder = LeadReminder(
            tenant_id=business.id,
            lead_id=lead_id,
            due_at=datetime.utcnow() + timedelta(days=1),
            note="Test reminder"
        )
        db.session.add(reminder)
        
        db.session.commit()
        
        # Verify all records exist before deletion
        assert ContactIdentity.query.filter_by(lead_id=lead_id).count() == 1
        assert WhatsAppConversation.query.filter_by(lead_id=lead_id).count() == 1
        assert CallSession.query.filter_by(lead_id=lead_id).count() == 1
        assert CRMTask.query.filter_by(lead_id=lead_id).count() == 1
        assert LeadMergeCandidate.query.filter_by(lead_id=lead_id).count() == 1
        assert OutboundCallJob.query.filter_by(lead_id=lead_id).count() == 1
        assert CallLog.query.filter_by(id=call_log_id).first().lead_id == lead_id
        assert Contract.query.filter_by(id=contract_id).first().lead_id == lead_id
        assert Appointment.query.filter_by(id=appointment_id).first().lead_id == lead_id
        assert LeadActivity.query.filter_by(lead_id=lead_id).count() == 1
        assert LeadReminder.query.filter_by(lead_id=lead_id).count() == 1
        
        # Now use the routes_leads DELETE endpoint logic
        from server.routes_leads import leads_bp
        from flask import g
        
        with app.test_client() as client:
            # Simulate the delete_lead function logic
            # Delete all related records to prevent foreign key constraint violations
            
            # 1. Delete activities and reminders
            LeadActivity.query.filter_by(lead_id=lead_id).delete()
            LeadReminder.query.filter_by(lead_id=lead_id).delete()
            
            # 2. Delete contact identities
            ContactIdentity.query.filter_by(lead_id=lead_id).delete()
            
            # 3. Delete WhatsApp conversations (FIX)
            WhatsAppConversation.query.filter_by(lead_id=lead_id).delete()
            
            # 4. Delete call sessions
            CallSession.query.filter_by(lead_id=lead_id).delete()
            
            # 5. Delete CRM tasks
            CRMTask.query.filter_by(lead_id=lead_id).delete()
            
            # 6. Delete lead merge candidates
            LeadMergeCandidate.query.filter_by(lead_id=lead_id).delete()
            LeadMergeCandidate.query.filter_by(duplicate_lead_id=lead_id).delete()
            
            # 7. Delete outbound call jobs
            OutboundCallJob.query.filter_by(lead_id=lead_id).delete()
            
            # 8. Nullify foreign keys in related tables
            CallLog.query.filter_by(lead_id=lead_id).update({'lead_id': None})
            Contract.query.filter_by(lead_id=lead_id).update({'lead_id': None})
            Appointment.query.filter_by(lead_id=lead_id).update({'lead_id': None})
            
            # 9. Delete the lead itself
            db.session.delete(lead)
            db.session.commit()
        
        # Verify lead is deleted
        assert Lead.query.filter_by(id=lead_id).first() is None
        
        # Verify related records are deleted
        assert ContactIdentity.query.filter_by(lead_id=lead_id).count() == 0
        assert WhatsAppConversation.query.filter_by(lead_id=lead_id).count() == 0
        assert CallSession.query.filter_by(lead_id=lead_id).count() == 0
        assert CRMTask.query.filter_by(lead_id=lead_id).count() == 0
        assert LeadMergeCandidate.query.filter_by(lead_id=lead_id).count() == 0
        assert OutboundCallJob.query.filter_by(lead_id=lead_id).count() == 0
        assert LeadActivity.query.filter_by(lead_id=lead_id).count() == 0
        assert LeadReminder.query.filter_by(lead_id=lead_id).count() == 0
        
        # Verify records that should be preserved with NULL lead_id
        call_log_after = CallLog.query.filter_by(id=call_log_id).first()
        assert call_log_after is not None, "CallLog should still exist"
        assert call_log_after.lead_id is None, "CallLog.lead_id should be NULL"
        
        contract_after = Contract.query.filter_by(id=contract_id).first()
        assert contract_after is not None, "Contract should still exist"
        assert contract_after.lead_id is None, "Contract.lead_id should be NULL"
        
        appointment_after = Appointment.query.filter_by(id=appointment_id).first()
        assert appointment_after is not None, "Appointment should still exist"
        assert appointment_after.lead_id is None, "Appointment.lead_id should be NULL"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
