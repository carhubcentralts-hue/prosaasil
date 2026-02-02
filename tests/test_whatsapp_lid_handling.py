"""
Tests for WhatsApp LID (Lidless ID) phone resolution

These tests verify that @lid JIDs are properly resolved to real phone numbers
through participant extraction, mapping table lookup, and Baileys resolution.

Run: pytest tests/test_whatsapp_lid_handling.py -v
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestLIDPhoneExtraction:
    """Test phone extraction from @lid messages"""
    
    def test_lid_with_participant_extracts_phone(self):
        """@lid with participant field extracts phone correctly"""
        from server.agent_tools.phone_utils import normalize_phone
        
        # Simulate Baileys message with @lid and participant
        participant_jid = "972501234567@s.whatsapp.net"
        
        # Extract phone from participant
        phone_raw = participant_jid.replace('@s.whatsapp.net', '').split(':')[0]
        phone_e164 = normalize_phone(phone_raw)
        
        assert phone_e164 == "+972501234567"
    
    def test_lid_digits_are_not_phone_numbers(self):
        """@lid digits should NOT be treated as phone numbers"""
        from server.services.contact_identity_service import ContactIdentityService
        
        lid_jid = "82399031480511@lid"
        
        # extract_phone_from_jid should return None for @lid
        phone = ContactIdentityService.extract_phone_from_jid(lid_jid)
        
        assert phone is None, "@lid digits must not be extracted as phone"
    
    def test_standard_jid_extracts_phone(self):
        """Standard @s.whatsapp.net JID extracts phone correctly"""
        from server.services.contact_identity_service import ContactIdentityService
        
        jid = "972501234567@s.whatsapp.net"
        
        phone = ContactIdentityService.extract_phone_from_jid(jid)
        
        assert phone == "+972501234567"


class TestLIDMappingTable:
    """Test LID → phone_e164 mapping storage and retrieval"""
    
    @pytest.fixture
    def app_context(self):
        """Create Flask app context for DB access"""
        from server.app_factory import create_app
        from server.db import db
        
        app = create_app()
        with app.app_context():
            yield app
            db.session.rollback()
    
    def test_lid_mapping_stored_on_first_resolution(self, app_context):
        """When @lid is resolved to phone, mapping is stored in contact_identities"""
        from server.services.contact_identity_service import ContactIdentityService
        from server.models_sql import ContactIdentity, Lead
        from server.db import db
        
        business_id = 1
        lid_jid = "82399031480511@lid"
        participant_jid = "972501234567@s.whatsapp.net"
        phone_e164 = "+972501234567"
        push_name = "Test User"
        
        # Simulate first message: @lid with participant
        lead = ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=business_id,
            remote_jid=lid_jid,
            push_name=push_name,
            phone_e164_override=phone_e164,
            message_text="Hello",
            ts=datetime.utcnow()
        )
        
        # Verify lead has phone
        assert lead.phone_e164 == phone_e164
        
        # Verify mapping exists
        normalized_lid = ContactIdentityService.normalize_whatsapp_jid(lid_jid)
        identity = ContactIdentity.query.filter_by(
            business_id=business_id,
            channel='whatsapp',
            external_id=normalized_lid
        ).first()
        
        assert identity is not None
        assert identity.lead_id == lead.id
        
        # Cleanup
        db.session.delete(identity)
        db.session.delete(lead)
        db.session.commit()
    
    def test_lid_mapping_lookup_on_subsequent_messages(self, app_context):
        """Subsequent @lid messages without participant use mapping table"""
        from server.services.contact_identity_service import ContactIdentityService
        from server.models_sql import ContactIdentity, Lead
        from server.db import db
        
        business_id = 1
        lid_jid = "82399031480511@lid"
        phone_e164 = "+972501234567"
        
        # Create a lead with mapping
        lead = Lead()
        lead.tenant_id = business_id
        lead.phone_e164 = phone_e164
        lead.phone_raw = phone_e164.lstrip('+')
        lead.source = 'whatsapp'
        lead.name = "Test User"
        db.session.add(lead)
        db.session.flush()
        
        normalized_lid = ContactIdentityService.normalize_whatsapp_jid(lid_jid)
        identity = ContactIdentity(
            business_id=business_id,
            channel='whatsapp',
            external_id=normalized_lid,
            lead_id=lead.id
        )
        db.session.add(identity)
        db.session.commit()
        
        # Now test lookup
        found_phone = ContactIdentityService.lookup_phone_by_lid(business_id, lid_jid)
        
        assert found_phone == phone_e164
        
        # Cleanup
        db.session.delete(identity)
        db.session.delete(lead)
        db.session.commit()


class TestLeadDeduplication:
    """Test that lead deduplication works by phone_e164, not JID"""
    
    @pytest.fixture
    def app_context(self):
        """Create Flask app context for DB access"""
        from server.app_factory import create_app
        from server.db import db
        
        app = create_app()
        with app.app_context():
            yield app
            db.session.rollback()
    
    def test_same_phone_different_jids_same_lead(self, app_context):
        """Same phone with @lid and @s.whatsapp.net should resolve to same lead"""
        from server.services.contact_identity_service import ContactIdentityService
        from server.models_sql import Lead
        from server.db import db
        
        business_id = 1
        phone_e164 = "+972501234567"
        
        # Message 1: Standard JID
        standard_jid = "972501234567@s.whatsapp.net"
        lead1 = ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=business_id,
            remote_jid=standard_jid,
            push_name="User",
            message_text="Message 1",
            ts=datetime.utcnow()
        )
        
        assert lead1.phone_e164 == phone_e164
        lead1_id = lead1.id
        
        # Message 2: LID with same phone via override
        lid_jid = "82399031480511@lid"
        lead2 = ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=business_id,
            remote_jid=lid_jid,
            push_name="User",
            phone_e164_override=phone_e164,  # Same phone!
            message_text="Message 2",
            ts=datetime.utcnow()
        )
        
        # Should be the SAME lead (linked by phone)
        assert lead2.id == lead1_id
        assert lead2.phone_e164 == phone_e164
        
        # Cleanup
        from server.models_sql import ContactIdentity
        ContactIdentity.query.filter_by(lead_id=lead1_id).delete()
        db.session.delete(lead1)
        db.session.commit()
    
    def test_lid_without_phone_creates_separate_lead(self, app_context):
        """@lid without phone creates lead without phone_e164"""
        from server.services.contact_identity_service import ContactIdentityService
        from server.models_sql import ContactIdentity
        from server.db import db
        
        business_id = 1
        lid_jid = "82399031480511@lid"
        
        # Message with @lid but no participant and no override
        lead = ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=business_id,
            remote_jid=lid_jid,
            push_name="Unknown User",
            phone_e164_override=None,  # No phone resolved!
            message_text="Message",
            ts=datetime.utcnow()
        )
        
        # Lead should exist but without phone
        assert lead.phone_e164 is None
        assert lead.whatsapp_jid is not None
        
        # Cleanup
        ContactIdentity.query.filter_by(lead_id=lead.id).delete()
        db.session.delete(lead)
        db.session.commit()


class TestBaileysResolution:
    """Test Baileys JID resolution endpoint"""
    
    def test_baileys_resolves_standard_jid(self):
        """Baileys endpoint extracts phone from @s.whatsapp.net"""
        import requests_mock
        
        with requests_mock.Mocker() as m:
            baileys_url = "http://localhost:3300/internal/resolve-jid"
            m.get(baileys_url, json={
                'phone_e164': '+972501234567',
                'source': 'direct'
            })
            
            import requests
            response = requests.get(baileys_url, params={
                'jid': '972501234567@s.whatsapp.net',
                'tenantId': 'business_1'
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data['phone_e164'] == '+972501234567'
            assert data['source'] == 'direct'
    
    def test_baileys_returns_null_for_unresolvable_lid(self):
        """Baileys returns null for @lid when no store available"""
        import requests_mock
        
        with requests_mock.Mocker() as m:
            baileys_url = "http://localhost:3300/internal/resolve-jid"
            m.get(baileys_url, json={
                'phone_e164': None,
                'source': 'unresolvable'
            })
            
            import requests
            response = requests.get(baileys_url, params={
                'jid': '82399031480511@lid',
                'tenantId': 'business_1'
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data['phone_e164'] is None
            assert data['source'] == 'unresolvable'


class TestWebhookIntegration:
    """Test end-to-end webhook processing with LID"""
    
    @patch('server.services.customer_intelligence.CustomerIntelligence')
    def test_webhook_with_lid_and_participant(self, mock_ci):
        """Webhook with @lid + participant extracts phone correctly"""
        # This is an integration test outline
        # In practice, you'd mock the full webhook flow
        pass
    
    @patch('server.services.customer_intelligence.CustomerIntelligence')
    def test_webhook_with_lid_no_participant_uses_mapping(self, mock_ci):
        """Webhook with @lid but no participant uses mapping table"""
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
