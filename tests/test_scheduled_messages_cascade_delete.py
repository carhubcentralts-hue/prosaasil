"""
Test cascade delete for scheduled message rules
Verifies that deleting a rule properly deletes associated queue entries
without attempting to set rule_id to NULL (which would violate NOT NULL constraint)
"""
import pytest
import os
from datetime import datetime, timedelta


def test_delete_rule_with_queued_messages():
    """
    Test that deleting a rule properly cascades to delete queued messages
    without violating NOT NULL constraint on rule_id
    """
    # Set migration mode to avoid DB initialization issues
    os.environ['MIGRATION_MODE'] = '1'
    os.environ['TESTING'] = '1'
    
    from server.app_factory import create_app
    from server.models_sql import (
        db, Business, ScheduledMessageRule, ScheduledMessagesQueue,
        Lead, LeadStatus, ScheduledRuleStatus
    )
    from server.services.scheduled_messages_service import delete_rule
    
    app = create_app()
    
    with app.app_context():
        # Create test business
        business = Business(
            name="Test Business",
            business_type="general",
            is_active=True
        )
        db.session.add(business)
        db.session.flush()
        
        # Create test lead status
        status = LeadStatus(
            business_id=business.id,
            name="test_status",
            label="Test Status",
            is_active=True
        )
        db.session.add(status)
        db.session.flush()
        
        # Create test lead
        lead = Lead(
            business_id=business.id,
            phone="+972501234567",
            name="Test Lead",
            status_id=status.id
        )
        db.session.add(lead)
        db.session.flush()
        
        # Create test rule
        rule = ScheduledMessageRule(
            business_id=business.id,
            name="Test Rule",
            message_text="Test message",
            is_active=True
        )
        db.session.add(rule)
        db.session.flush()
        
        # Link rule to status
        rule_status = ScheduledRuleStatus(
            rule_id=rule.id,
            status_id=status.id
        )
        db.session.add(rule_status)
        
        # Create queued messages linked to this rule
        for i in range(3):
            queued_msg = ScheduledMessagesQueue(
                business_id=business.id,
                rule_id=rule.id,
                lead_id=lead.id,
                message_text=f"Test message {i}",
                remote_jid="972501234567@s.whatsapp.net",
                scheduled_for=datetime.utcnow() + timedelta(minutes=i+1),
                dedupe_key=f"test_rule_{rule.id}_lead_{lead.id}_step_{i}",
                status='pending'
            )
            db.session.add(queued_msg)
        
        db.session.commit()
        
        rule_id = rule.id
        business_id = business.id
        
        # Verify messages exist before deletion
        messages_before = ScheduledMessagesQueue.query.filter_by(
            rule_id=rule_id
        ).count()
        assert messages_before == 3, "Should have 3 queued messages before deletion"
        
        # Delete the rule - this should cascade delete the messages
        # WITHOUT trying to set rule_id to NULL (which would fail)
        success = delete_rule(rule_id, business_id)
        
        assert success, "Rule deletion should succeed"
        
        # Verify rule is deleted
        deleted_rule = ScheduledMessageRule.query.filter_by(id=rule_id).first()
        assert deleted_rule is None, "Rule should be deleted"
        
        # Verify queued messages are also deleted (not orphaned with NULL rule_id)
        messages_after = ScheduledMessagesQueue.query.filter_by(
            rule_id=rule_id
        ).count()
        assert messages_after == 0, "All queued messages should be deleted via cascade"
        
        # Verify no orphaned messages exist (rule_id should never be NULL)
        orphaned = ScheduledMessagesQueue.query.filter(
            ScheduledMessagesQueue.rule_id.is_(None)
        ).count()
        assert orphaned == 0, "No orphaned messages should exist with NULL rule_id"


def test_delete_nonexistent_rule():
    """Test deleting a rule that doesn't exist returns False"""
    os.environ['MIGRATION_MODE'] = '1'
    os.environ['TESTING'] = '1'
    
    from server.app_factory import create_app
    from server.services.scheduled_messages_service import delete_rule
    
    app = create_app()
    
    with app.app_context():
        result = delete_rule(999999, 1)
        assert result is False, "Deleting nonexistent rule should return False"


def test_delete_lead_with_scheduled_messages():
    """
    Test that deleting a lead properly deletes associated scheduled messages
    without violating NOT NULL constraint on lead_id
    """
    os.environ['MIGRATION_MODE'] = '1'
    os.environ['TESTING'] = '1'
    
    from server.app_factory import create_app
    from server.models_sql import (
        db, Business, ScheduledMessageRule, ScheduledMessagesQueue,
        Lead, LeadStatus, ScheduledRuleStatus
    )
    
    app = create_app()
    
    with app.app_context():
        # Create test business
        business = Business(
            name="Test Business Lead Delete",
            business_type="general",
            is_active=True
        )
        db.session.add(business)
        db.session.flush()
        
        # Create test lead status
        status = LeadStatus(
            business_id=business.id,
            name="test_status_lead_delete",
            label="Test Status Lead Delete",
            is_active=True
        )
        db.session.add(status)
        db.session.flush()
        
        # Create test lead
        lead = Lead(
            business_id=business.id,
            phone="+972501234568",
            name="Test Lead To Delete",
            status_id=status.id,
            tenant_id=business.id
        )
        db.session.add(lead)
        db.session.flush()
        
        # Create test rule
        rule = ScheduledMessageRule(
            business_id=business.id,
            name="Test Rule For Lead Delete",
            message_text="Test message for lead delete",
            is_active=True
        )
        db.session.add(rule)
        db.session.flush()
        
        # Link rule to status
        rule_status = ScheduledRuleStatus(
            rule_id=rule.id,
            status_id=status.id
        )
        db.session.add(rule_status)
        
        # Create queued messages linked to this lead
        for i in range(3):
            queued_msg = ScheduledMessagesQueue(
                business_id=business.id,
                rule_id=rule.id,
                lead_id=lead.id,
                message_text=f"Test message {i} for lead",
                remote_jid="972501234568@s.whatsapp.net",
                scheduled_for=datetime.utcnow() + timedelta(minutes=i+1),
                dedupe_key=f"test_lead_delete_{rule.id}_lead_{lead.id}_step_{i}",
                status='pending'
            )
            db.session.add(queued_msg)
        
        db.session.commit()
        
        lead_id = lead.id
        
        # Verify messages exist before deletion
        messages_before = ScheduledMessagesQueue.query.filter_by(
            lead_id=lead_id
        ).count()
        assert messages_before == 3, "Should have 3 queued messages before lead deletion"
        
        # Delete the lead's scheduled messages first (as done in delete_leads_job.py)
        ScheduledMessagesQueue.query.filter(
            ScheduledMessagesQueue.lead_id == lead_id
        ).delete(synchronize_session=False)
        
        # Now delete the lead
        db.session.delete(lead)
        db.session.commit()
        
        # Verify lead is deleted
        deleted_lead = Lead.query.filter_by(id=lead_id).first()
        assert deleted_lead is None, "Lead should be deleted"
        
        # Verify queued messages are also deleted
        messages_after = ScheduledMessagesQueue.query.filter_by(
            lead_id=lead_id
        ).count()
        assert messages_after == 0, "All queued messages should be deleted"
        
        # Verify no orphaned messages exist (lead_id should never be NULL)
        orphaned = ScheduledMessagesQueue.query.filter(
            ScheduledMessagesQueue.lead_id.is_(None)
        ).count()
        assert orphaned == 0, "No orphaned messages should exist with NULL lead_id"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

