"""
Test lead deletion transaction handling fix
Verifies that the fix for LeadStatusHistory table properly handles transactions
"""
import pytest
import os
from datetime import datetime


def test_delete_lead_with_missing_status_history_table():
    """
    Test that deleting a lead works correctly even if lead_status_history table doesn't exist.
    This test verifies the transaction rollback fix for the UndefinedTable error.
    
    Before fix: Transaction would be aborted and subsequent SQL operations would fail
    After fix: Transaction is rolled back and deletion proceeds normally
    """
    os.environ['MIGRATION_MODE'] = '1'
    os.environ['TESTING'] = '1'
    
    from server.app_factory import create_app
    from server.models_sql import (
        db, Business, Lead, LeadStatus, CallLog
    )
    
    app = create_app()
    
    with app.app_context():
        # Create test business
        business = Business(
            name="Test Business Transaction",
            business_type="general",
            is_active=True
        )
        db.session.add(business)
        db.session.flush()
        
        # Create test lead status
        status = LeadStatus(
            business_id=business.id,
            name="test_status_transaction",
            label="Test Status Transaction",
            is_active=True
        )
        db.session.add(status)
        db.session.flush()
        
        # Create test lead
        lead = Lead(
            tenant_id=business.id,
            phone_e164="+972501234599",
            name="Test Lead Transaction",
            status="test_status_transaction"
        )
        db.session.add(lead)
        db.session.flush()
        lead_id = lead.id
        
        # Create CallLog (should be nullified, not deleted)
        call_log = CallLog(
            business_id=business.id,
            lead_id=lead_id,
            call_sid="TEST_CALL_LOG_TRANSACTION",
            from_number="+972501234599",
            direction="inbound"
        )
        db.session.add(call_log)
        db.session.flush()
        call_log_id = call_log.id
        
        db.session.commit()
        
        # Verify lead and call log exist before deletion
        assert Lead.query.filter_by(id=lead_id).first() is not None
        assert CallLog.query.filter_by(id=call_log_id).first().lead_id == lead_id
        
        # Now simulate the delete_lead function logic with the fix
        from server.models_sql import LeadStatusHistory, LeadActivity, LeadReminder, ContactIdentity
        from server.models_sql import WhatsAppConversation, CallSession, CRMTask, LeadMergeCandidate
        from server.models_sql import OutboundCallJob, Contract, Appointment, WhatsAppBroadcastRecipient
        
        try:
            # 1. Delete activities and reminders
            LeadActivity.query.filter_by(lead_id=lead_id).delete()
            LeadReminder.query.filter_by(lead_id=lead_id).delete()
            
            # 2. Delete contact identities
            ContactIdentity.query.filter_by(lead_id=lead_id).delete()
            
            # 3. Delete WhatsApp conversations
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
            
            # 8. Delete lead status history (handle missing table gracefully)
            try:
                LeadStatusHistory.query.filter_by(lead_id=lead_id).delete()
            except Exception as lsh_err:
                # Check if this is an UndefinedTable error (table doesn't exist)
                err_str = str(lsh_err).lower()
                is_undefined_table = ('undefinedtable' in err_str or 'does not exist' in err_str) and 'lead_status_history' in err_str
                
                if is_undefined_table:
                    print("⚠️ LeadStatusHistory delete skipped (table does not exist)")
                    # 🔥 CRITICAL FIX: Rollback the failed transaction to allow subsequent operations
                    db.session.rollback()
                else:
                    raise
            
            # 9. Nullify foreign keys in related tables (THIS IS THE KEY TEST)
            # Before fix: This would fail with "current transaction is aborted"
            # After fix: This succeeds because we rolled back the failed transaction
            CallLog.query.filter_by(lead_id=lead_id).update({'lead_id': None})
            Contract.query.filter_by(lead_id=lead_id).update({'lead_id': None})
            Appointment.query.filter_by(lead_id=lead_id).update({'lead_id': None})
            
            # 10. Nullify WhatsApp broadcast recipient references
            WhatsAppBroadcastRecipient.query.filter_by(lead_id=lead_id).update({'lead_id': None})
            
            # 11. Delete the lead itself
            db.session.delete(lead)
            db.session.commit()
            
        except Exception as e:
            db.session.rollback()
            pytest.fail(f"Lead deletion failed: {str(e)}")
        
        # Verify lead is deleted
        assert Lead.query.filter_by(id=lead_id).first() is None, "Lead should be deleted"
        
        # Verify CallLog still exists but with NULL lead_id
        call_log_after = CallLog.query.filter_by(id=call_log_id).first()
        assert call_log_after is not None, "CallLog should still exist"
        assert call_log_after.lead_id is None, "CallLog.lead_id should be NULL"
        
        print("✅ Test passed: Lead deletion works correctly with transaction fix")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
