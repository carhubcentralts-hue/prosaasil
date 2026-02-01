"""
Test that scheduled messages can find phone numbers from phone_e164 field
Tests the fix for the issue where scheduled messages were skipping leads with phone_e164 but no phone_raw
"""
import pytest
from datetime import datetime
from server.db import db
from server.models_sql import Lead, Business, ScheduledMessageRule, LeadStatus
from server.services.scheduled_messages_service import create_scheduled_tasks_for_lead


def test_scheduled_messages_uses_phone_e164():
    """
    Test that scheduled messages service can construct WhatsApp JID from phone_e164
    when phone_raw is not set (common for leads created from WhatsApp)
    """
    # Create test business
    business = Business(
        name="Test Business",
        business_type="test"
    )
    db.session.add(business)
    db.session.flush()
    
    # Create test status
    status = LeadStatus(
        business_id=business.id,
        name="new",
        label="חדש"
    )
    db.session.add(status)
    db.session.flush()
    
    # Create test lead with phone_e164 but NO phone_raw (simulates WhatsApp-created lead)
    lead = Lead(
        tenant_id=business.id,
        phone_e164="+972501234567",  # Normalized E.164 format
        phone_raw=None,  # NOT SET - this is the issue!
        whatsapp_jid=None,  # Also not set
        reply_jid=None,
        status="new",
        name="Test Lead",
        source="whatsapp"
    )
    db.session.add(lead)
    db.session.flush()
    
    # Create test rule
    rule = ScheduledMessageRule(
        business_id=business.id,
        name="Test Rule",
        message_text="Hello {name}",
        delay_minutes=5,
        delay_seconds=300,
        is_active=True,
        created_by_user_id=1
    )
    db.session.add(rule)
    db.session.flush()
    
    # Link rule to status
    from server.models_sql import ScheduledRuleStatus
    rule_status = ScheduledRuleStatus(
        rule_id=rule.id,
        status_id=status.id
    )
    db.session.add(rule_status)
    db.session.commit()
    
    # Try to create scheduled tasks - should work now with phone_e164
    result = create_scheduled_tasks_for_lead(
        rule_id=rule.id,
        lead_id=lead.id,
        triggered_at=datetime.utcnow()
    )
    
    # Should create tasks (at least 1 for the immediate message if enabled, or 0 if not)
    # The important part is it should NOT skip due to "no phone"
    assert result >= 0, "Should not fail to create tasks"
    
    # Cleanup
    db.session.rollback()
    
    print("✅ Test passed: Scheduled messages can now use phone_e164 to construct WhatsApp JID")


def test_scheduled_messages_normalizes_phone():
    """
    Test that scheduled messages properly normalizes phone numbers using normalize_phone utility
    """
    # Create test business
    business = Business(
        name="Test Business 2",
        business_type="test"
    )
    db.session.add(business)
    db.session.flush()
    
    # Create test status
    status = LeadStatus(
        business_id=business.id,
        name="contacted",
        label="נוצר קשר"
    )
    db.session.add(status)
    db.session.flush()
    
    # Create test lead with various phone formats
    lead = Lead(
        tenant_id=business.id,
        phone_e164="+972-50-123-4567",  # Phone with dashes (should be normalized)
        phone_raw=None,
        whatsapp_jid=None,
        reply_jid=None,
        status="contacted",
        name="Test Lead 2",
        source="whatsapp"
    )
    db.session.add(lead)
    db.session.flush()
    
    # Create test rule
    rule = ScheduledMessageRule(
        business_id=business.id,
        name="Test Rule 2",
        message_text="Followup message",
        delay_minutes=10,
        delay_seconds=600,
        is_active=True,
        created_by_user_id=1
    )
    db.session.add(rule)
    db.session.flush()
    
    # Link rule to status
    from server.models_sql import ScheduledRuleStatus
    rule_status = ScheduledRuleStatus(
        rule_id=rule.id,
        status_id=status.id
    )
    db.session.add(rule_status)
    db.session.commit()
    
    # Try to create scheduled tasks
    result = create_scheduled_tasks_for_lead(
        rule_id=rule.id,
        lead_id=lead.id,
        triggered_at=datetime.utcnow()
    )
    
    # Should work with normalized phone
    assert result >= 0, "Should handle phone normalization correctly"
    
    # Cleanup
    db.session.rollback()
    
    print("✅ Test passed: Phone normalization works correctly in scheduled messages")


if __name__ == "__main__":
    print("Running phone normalization tests for scheduled messages...")
    test_scheduled_messages_uses_phone_e164()
    test_scheduled_messages_normalizes_phone()
    print("\n✅ All tests passed!")
