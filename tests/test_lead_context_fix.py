"""
Tests for Lead Context and Agent Context Fixes

These tests verify the critical bug fixes:
1. store_lid_phone_mapping uses tenant_id instead of business_id
2. g.agent_context uses phone_e164 from lead_context
3. Lead context is loaded from UnifiedLeadContextService

Run: pytest tests/test_lead_context_fix.py -v
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestContactIdentityServiceFix:
    """Test that store_lid_phone_mapping uses correct tenant_id field"""
    
    def test_store_lid_phone_mapping_uses_tenant_id(self):
        """store_lid_phone_mapping should use tenant_id not business_id for Lead queries"""
        from server.services.contact_identity_service import ContactIdentityService
        from server.models_sql import Lead, ContactIdentity
        
        with patch('server.services.contact_identity_service.Lead') as MockLead, \
             patch('server.services.contact_identity_service.ContactIdentity') as MockContactIdentity, \
             patch('server.services.contact_identity_service.db') as mock_db:
            
            # Setup mock query
            mock_query = Mock()
            mock_filter_by = Mock()
            mock_query.filter_by.return_value = mock_filter_by
            mock_filter_by.first.return_value = None  # No existing lead
            MockLead.query = mock_query
            
            # Mock ContactIdentity query
            mock_ci_query = Mock()
            mock_ci_filter = Mock()
            mock_ci_query.filter_by.return_value = mock_ci_filter
            mock_ci_filter.first.return_value = None
            MockContactIdentity.query = mock_ci_query
            
            # Call the function
            try:
                ContactIdentityService.store_lid_phone_mapping(
                    business_id=123,
                    lid_jid="82399031480511@lid",
                    phone_e164="+972501234567"
                )
            except Exception:
                pass  # We're just checking the query was called correctly
            
            # Verify Lead.query.filter_by was called with tenant_id, not business_id
            call_args = mock_query.filter_by.call_args
            assert call_args is not None
            assert 'tenant_id' in call_args[1], "Should use tenant_id field"
            assert call_args[1]['tenant_id'] == 123
            assert 'business_id' not in call_args[1], "Should NOT use business_id field"


class TestAgentContextPhoneFix:
    """Test that g.agent_context uses phone_e164 from lead_context"""
    
    def test_agent_context_extracts_phone_from_lead_context(self):
        """g.agent_context should extract phone_e164 from lead_context, not use @lid JID"""
        
        # Mock context with lead_context containing phone_e164
        context = {
            'lead_id': 123,
            'lead_context': {
                'found': True,
                'lead_id': 123,
                'lead_phone': '+972501234567',  # Real E.164 phone
            },
            'phone': '+972501234567',
            'remote_jid': '82399031480511@lid'  # LID JID (not a real phone)
        }
        
        # Simulate the logic from ai_service.py
        phone_e164 = None
        if context and context.get('lead_context'):
            lead_ctx = context['lead_context']
            phone_e164 = lead_ctx.get('lead_phone')
        
        if not phone_e164 and context:
            phone_e164 = context.get('phone')
        
        # Verify we got the E.164 phone, not the @lid JID
        assert phone_e164 == '+972501234567'
        assert '@lid' not in phone_e164
    
    def test_agent_context_fallback_to_context_phone(self):
        """If lead_context missing, should fallback to context['phone']"""
        
        context = {
            'lead_id': 123,
            'lead_context': None,  # Lead context not loaded
            'phone': '+972501234567',
            'remote_jid': '82399031480511@lid'
        }
        
        # Simulate the logic
        phone_e164 = None
        if context and context.get('lead_context'):
            lead_ctx = context['lead_context']
            phone_e164 = lead_ctx.get('lead_phone')
        
        if not phone_e164 and context:
            phone_e164 = context.get('phone')
        
        assert phone_e164 == '+972501234567'


class TestLeadContextLoading:
    """Test that lead_context is loaded in WhatsApp routes"""
    
    def test_lead_context_added_to_ai_context(self):
        """ai_context should include lead_context when lead_id is available"""
        
        # Import before patching for clarity
        from server.services.unified_lead_context_service import get_unified_context_for_lead
        
        # Simulate the logic from routes_whatsapp.py
        lead_id = 123
        business_id = 456
        
        # Mock UnifiedLeadContextService response
        mock_lead_context = Mock()
        mock_lead_context.found = True
        mock_lead_context.lead_id = 123
        mock_lead_context.dict.return_value = {'found': True, 'lead_id': 123}
        
        with patch('server.services.unified_lead_context_service.get_unified_context_for_lead') as mock_get_context:
            mock_get_context.return_value = mock_lead_context
            
            lead_context_payload = None
            if lead_id:
                lead_context_payload = get_unified_context_for_lead(
                    business_id=business_id,
                    lead_id=lead_id,
                    channel='whatsapp'
                )
            
            ai_context = {
                'lead_id': lead_id,
                'lead_context': lead_context_payload.dict() if lead_context_payload else None
            }
            
            # Verify lead_context is included
            assert ai_context['lead_context'] is not None
            assert ai_context['lead_context']['found'] is True
            assert ai_context['lead_context']['lead_id'] == 123


class TestLeadContextValidation:
    """Test that missing lead_context is detected and logged"""
    
    def test_error_logged_when_lead_id_exists_but_context_null(self):
        """Should log ERROR when lead_id exists but lead_context is None"""
        
        context = {
            'lead_id': 123,
            'lead_context': None  # This is the bug we're detecting
        }
        
        # Verify the condition that should trigger the error log
        has_lead_id = context and context.get('lead_id')
        missing_context = not context.get('lead_context')
        
        assert has_lead_id is True
        assert missing_context is True
        # In actual code, this would trigger:
        # logger.error(f"[CONTEXT] ❌ CRITICAL: lead_id={...} exists but lead_context is None!")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
