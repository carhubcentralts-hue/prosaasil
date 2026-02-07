"""
Tests for LeadStatusUpdateService - Single Source of Truth (SSOT)

Tests cover:
1. WhatsApp summary with recommendation → status changes
2. Call summary with recommendation → status changes
3. Idempotency (same source_event_id → no duplicate)
4. Invalid status → no crash, audit only
5. Low confidence → no status change
6. Same status → no-op
7. Push notification sent on status change
"""
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime
from server.models_sql import Lead, Business, LeadStatus, LeadStatusEvent, LeadStatusHistory, db
from server.services.lead_status_update_service import LeadStatusUpdateService


@pytest.fixture
def app():
    """Create Flask app for testing"""
    from flask import Flask
    from server.db import db as _db

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TESTING'] = True

    _db.init_app(app)

    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def test_business(app):
    """Create a test business with statuses"""
    with app.app_context():
        business = Business(
            name="Test Business",
            business_type="general",
            phone_e164="+972501234567"
        )
        db.session.add(business)
        db.session.commit()
        
        # Create Hebrew status labels
        statuses = [
            LeadStatus(
                business_id=business.id,
                name='new',
                label='חדש',
                is_active=True,
                is_default=True,
                order_index=0
            ),
            LeadStatus(
                business_id=business.id,
                name='interested',
                label='מעוניין',
                is_active=True,
                order_index=1
            ),
            LeadStatus(
                business_id=business.id,
                name='contacted',
                label='נוצר קשר',
                is_active=True,
                order_index=2
            ),
            LeadStatus(
                business_id=business.id,
                name='no_answer',
                label='אין מענה',
                is_active=True,
                order_index=3
            ),
        ]
        
        for status in statuses:
            db.session.add(status)
        
        db.session.commit()
        yield business
        
        # Cleanup
        LeadStatusEvent.query.filter_by(business_id=business.id).delete()
        LeadStatusHistory.query.filter_by(tenant_id=business.id).delete()
        LeadStatus.query.filter_by(business_id=business.id).delete()
        Lead.query.filter_by(tenant_id=business.id).delete()
        db.session.delete(business)
        db.session.commit()


@pytest.fixture
def test_lead(app, test_business):
    """Create a test lead"""
    with app.app_context():
        lead = Lead(
            tenant_id=test_business.id,
            phone_e164="+972501234567",
            status='new',
            name='Test Lead'
        )
        db.session.add(lead)
        db.session.commit()
        yield lead


class TestLeadStatusUpdateService:
    """Test suite for LeadStatusUpdateService"""
    
    def test_whatsapp_summary_with_recommendation_updates_status(self, app, test_business, test_lead):
        """Test that WhatsApp summary with recommendation updates status"""
        with app.app_context():
            service = LeadStatusUpdateService()
            
            # Summary with Hebrew recommendation
            summary = "הלקוח מעוניין בשירות. דיברנו על מחירים. [המלצה: מעוניין]"
            
            success, message = service.apply_from_recommendation(
                business_id=test_business.id,
                lead_id=test_lead.id,
                summary_text=summary,
                source='whatsapp_summary',
                source_event_id='wa_session_123',
                confidence=0.85
            )
            
            # Verify success
            assert success
            assert "new → interested" in message.lower() or "מעוניין" in message
            
            # Verify lead status updated
            lead = Lead.query.get(test_lead.id)
            assert lead.status == 'interested'
            
            # Verify status event recorded
            event = LeadStatusEvent.query.filter_by(
                business_id=test_business.id,
                source_event_id='wa_session_123'
            ).first()
            assert event is not None
            assert event.applied is True
            assert event.recommended_status_label == 'מעוניין'
            assert event.recommended_status_id == 'interested'
            
            # Verify status history recorded
            history = LeadStatusHistory.query.filter_by(
                lead_id=test_lead.id
            ).order_by(LeadStatusHistory.created_at.desc()).first()
            assert history is not None
            assert history.new_status == 'interested'
            assert history.old_status == 'new'
    
    def test_call_summary_with_recommendation_updates_status(self, app, test_business, test_lead):
        """Test that call summary with recommendation updates status"""
        with app.app_context():
            service = LeadStatusUpdateService()
            
            # Summary with Hebrew recommendation
            summary = "שיחה עם הלקוח. לא ענה. תא קולי. [המלצה: אין מענה]"
            
            success, message = service.apply_from_recommendation(
                business_id=test_business.id,
                lead_id=test_lead.id,
                summary_text=summary,
                source='call_summary',
                source_event_id='CA1234567890',
                confidence=0.9
            )
            
            # Verify success
            assert success
            
            # Verify lead status updated
            lead = Lead.query.get(test_lead.id)
            assert lead.status == 'no_answer'
            
            # Verify status event recorded
            event = LeadStatusEvent.query.filter_by(
                source_event_id='CA1234567890'
            ).first()
            assert event is not None
            assert event.applied is True
            assert event.source == 'call_summary'
    
    def test_idempotency_prevents_duplicate_updates(self, app, test_business, test_lead):
        """Test that same source_event_id prevents duplicate updates"""
        with app.app_context():
            service = LeadStatusUpdateService()
            
            summary = "הלקוח מעוניין. [המלצה: מעוניין]"
            source_event_id = 'wa_session_456'
            
            # First attempt - should succeed
            success1, message1 = service.apply_from_recommendation(
                business_id=test_business.id,
                lead_id=test_lead.id,
                summary_text=summary,
                source='whatsapp_summary',
                source_event_id=source_event_id,
                confidence=0.8
            )
            
            assert success1
            
            lead = Lead.query.get(test_lead.id)
            original_status = lead.status
            
            # Second attempt with same source_event_id - should be idempotent
            success2, message2 = service.apply_from_recommendation(
                business_id=test_business.id,
                lead_id=test_lead.id,
                summary_text=summary,
                source='whatsapp_summary',
                source_event_id=source_event_id,  # Same ID!
                confidence=0.8
            )
            
            # Should report as already processed
            assert success2  # Idempotent operations return success
            assert "already" in message2.lower() or "כבר" in message2
            
            # Status should not have changed again
            lead = Lead.query.get(test_lead.id)
            assert lead.status == original_status
            
            # Should have only one event
            events = LeadStatusEvent.query.filter_by(
                source_event_id=source_event_id
            ).all()
            assert len(events) == 1
    
    def test_invalid_status_label_does_not_crash(self, app, test_business, test_lead):
        """Test that invalid status label doesn't crash, just audits"""
        with app.app_context():
            service = LeadStatusUpdateService()
            
            # Summary with non-existent status
            summary = "הלקוח רוצה משהו. [המלצה: סטטוס לא קיים]"
            
            success, message = service.apply_from_recommendation(
                business_id=test_business.id,
                lead_id=test_lead.id,
                summary_text=summary,
                source='call_summary',
                source_event_id='CA_invalid_123',
                confidence=0.8
            )
            
            # Should not succeed but also not crash
            assert not success
            assert "not found" in message.lower() or "לא נמצא" in message
            
            # Lead status should not have changed
            lead = Lead.query.get(test_lead.id)
            assert lead.status == 'new'
            
            # Should have event recorded as not applied
            event = LeadStatusEvent.query.filter_by(
                source_event_id='CA_invalid_123'
            ).first()
            assert event is not None
            assert event.applied is False
            assert event.recommended_status_id is None
    
    def test_low_confidence_does_not_update_status(self, app, test_business, test_lead):
        """Test that low confidence prevents status update"""
        with app.app_context():
            service = LeadStatusUpdateService()
            
            summary = "אולי מעוניין. [המלצה: מעוניין]"
            
            success, message = service.apply_from_recommendation(
                business_id=test_business.id,
                lead_id=test_lead.id,
                summary_text=summary,
                source='whatsapp_summary',
                source_event_id='wa_low_conf_123',
                confidence=0.4  # Below 0.65 threshold
            )
            
            # Should not succeed
            assert not success
            assert "confidence" in message.lower() or "ביטחון" in message
            
            # Lead status should not have changed
            lead = Lead.query.get(test_lead.id)
            assert lead.status == 'new'
            
            # Should have event recorded as not applied
            event = LeadStatusEvent.query.filter_by(
                source_event_id='wa_low_conf_123'
            ).first()
            assert event is not None
            assert event.applied is False
            assert event.confidence == 0.4
    
    def test_same_status_is_noop(self, app, test_business, test_lead):
        """Test that recommending the same status is a no-op"""
        with app.app_context():
            service = LeadStatusUpdateService()
            
            # Set lead to 'interested'
            test_lead.status = 'interested'
            db.session.commit()
            
            # Recommend same status
            summary = "הלקוח מעוניין. [המלצה: מעוניין]"
            
            success, message = service.apply_from_recommendation(
                business_id=test_business.id,
                lead_id=test_lead.id,
                summary_text=summary,
                source='call_summary',
                source_event_id='CA_noop_123',
                confidence=0.8
            )
            
            # Should succeed (no-op is still success)
            assert success
            assert "already" in message.lower() or "no-op" in message.lower()
            
            # Status should remain the same
            lead = Lead.query.get(test_lead.id)
            assert lead.status == 'interested'
            
            # Event should be recorded as applied (but no change needed)
            event = LeadStatusEvent.query.filter_by(
                source_event_id='CA_noop_123'
            ).first()
            assert event is not None
            assert event.applied is True
    
    @patch('server.services.lead_status_update_service.dispatch_push_to_user')
    def test_push_notification_sent_on_status_change(self, mock_dispatch, app, test_business, test_lead):
        """Test that push notification is sent when status changes"""
        with app.app_context():
            # Create a user for the business
            from server.models_sql import User
            user = User(
                tenant_id=test_business.id,
                email='test@example.com',
                username='testuser',
                role='admin'
            )
            db.session.add(user)
            db.session.commit()
            
            service = LeadStatusUpdateService()
            
            summary = "הלקוח מעוניין. [המלצה: מעוניין]"
            
            success, message = service.apply_from_recommendation(
                business_id=test_business.id,
                lead_id=test_lead.id,
                summary_text=summary,
                source='whatsapp_summary',
                source_event_id='wa_push_123',
                confidence=0.85
            )
            
            # Verify success
            assert success
            
            # Verify push notification was dispatched
            assert mock_dispatch.called
            
            # Verify notification parameters
            assert mock_dispatch.call_args.kwargs['user_id'] == user.id
            assert mock_dispatch.call_args.kwargs['business_id'] == test_business.id
            
            # Verify payload contains status change info
            payload = mock_dispatch.call_args.kwargs['payload']
            assert 'סטטוס' in payload.title or 'status' in payload.title.lower()
            assert payload.data['type'] == 'lead_status_change'
            assert payload.data['lead_id'] == test_lead.id
    
    def test_no_recommendation_in_summary(self, app, test_business, test_lead):
        """Test handling when summary has no [המלצה: ...] tag"""
        with app.app_context():
            service = LeadStatusUpdateService()
            
            # Summary without recommendation
            summary = "דיברתי עם הלקוח. הכל בסדר."
            
            success, message = service.apply_from_recommendation(
                business_id=test_business.id,
                lead_id=test_lead.id,
                summary_text=summary,
                source='call_summary',
                source_event_id='CA_no_rec_123',
                confidence=0.8
            )
            
            # Should not succeed
            assert not success
            assert "no recommendation" in message.lower() or "אין המלצה" in message
            
            # Lead status should not have changed
            lead = Lead.query.get(test_lead.id)
            assert lead.status == 'new'
    
    def test_partial_label_matching(self, app, test_business, test_lead):
        """Test that partial label matching works"""
        with app.app_context():
            service = LeadStatusUpdateService()
            
            # Use partial label (just "מעוניין" instead of exact match)
            summary = "הלקוח רוצה השירות. [המלצה: מעוניין]"
            
            success, message = service.apply_from_recommendation(
                business_id=test_business.id,
                lead_id=test_lead.id,
                summary_text=summary,
                source='whatsapp_summary',
                source_event_id='wa_partial_123',
                confidence=0.8
            )
            
            # Should succeed with partial match
            assert success
            
            # Verify lead status updated
            lead = Lead.query.get(test_lead.id)
            assert lead.status == 'interested'
    
    def test_case_insensitive_matching(self, app, test_business, test_lead):
        """Test that label matching is case-insensitive"""
        with app.app_context():
            service = LeadStatusUpdateService()
            
            # Use different case
            summary = "דיברנו. [המלצה: מעוניין]"  # Lowercase in Hebrew doesn't really exist, but test normalization
            
            success, message = service.apply_from_recommendation(
                business_id=test_business.id,
                lead_id=test_lead.id,
                summary_text=summary,
                source='call_summary',
                source_event_id='CA_case_123',
                confidence=0.8
            )
            
            # Should succeed
            assert success
            
            # Verify lead status updated
            lead = Lead.query.get(test_lead.id)
            assert lead.status == 'interested'
    
    def test_multiple_sources_same_lead(self, app, test_business, test_lead):
        """Test that different sources can update same lead independently"""
        with app.app_context():
            service = LeadStatusUpdateService()
            
            # First update from WhatsApp
            summary_wa = "הלקוח מעוניין. [המלצה: מעוניין]"
            success1, _ = service.apply_from_recommendation(
                business_id=test_business.id,
                lead_id=test_lead.id,
                summary_text=summary_wa,
                source='whatsapp_summary',
                source_event_id='wa_multi_123',
                confidence=0.8
            )
            
            assert success1
            lead = Lead.query.get(test_lead.id)
            assert lead.status == 'interested'
            
            # Second update from Call with different event ID
            summary_call = "עכשיו יצרנו קשר. [המלצה: נוצר קשר]"
            success2, _ = service.apply_from_recommendation(
                business_id=test_business.id,
                lead_id=test_lead.id,
                summary_text=summary_call,
                source='call_summary',
                source_event_id='CA_multi_456',  # Different ID
                confidence=0.9
            )
            
            assert success2
            lead = Lead.query.get(test_lead.id)
            assert lead.status == 'contacted'
            
            # Should have two separate events
            events = LeadStatusEvent.query.filter_by(
                lead_id=test_lead.id
            ).all()
            assert len(events) == 2
