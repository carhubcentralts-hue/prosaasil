"""
Tests for CRM Context-Aware Support Feature
Tests multi-tenant security, phone normalization, call summary notes, and redaction rules.

Run: pytest tests/test_crm_context_support.py -v
"""
import pytest
import re
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestPhoneNormalization:
    """Test phone number normalization to E.164 format"""
    
    def test_normalize_israeli_landline_with_zero(self):
        """Israeli landline starting with 0"""
        from server.agent_tools.phone_utils import normalize_il_phone
        
        result = normalize_il_phone("035551234")
        assert result == "+97235551234"
    
    def test_normalize_israeli_mobile_with_zero(self):
        """Israeli mobile starting with 05"""
        from server.agent_tools.phone_utils import normalize_il_phone
        
        result = normalize_il_phone("0501234567")
        assert result == "+972501234567"
    
    def test_normalize_already_e164(self):
        """Already in E.164 format"""
        from server.agent_tools.phone_utils import normalize_il_phone
        
        result = normalize_il_phone("+972501234567")
        assert result == "+972501234567"
    
    def test_normalize_with_dashes(self):
        """Phone with dashes"""
        from server.agent_tools.phone_utils import normalize_il_phone
        
        result = normalize_il_phone("050-123-4567")
        assert result == "+972501234567"
    
    def test_normalize_without_plus(self):
        """972 without + prefix"""
        from server.agent_tools.phone_utils import normalize_il_phone
        
        result = normalize_il_phone("972501234567")
        assert result == "+972501234567"
    
    def test_normalize_empty_returns_none(self):
        """Empty string returns None"""
        from server.agent_tools.phone_utils import normalize_il_phone
        
        result = normalize_il_phone("")
        assert result is None
    
    def test_normalize_none_returns_none(self):
        """None returns None"""
        from server.agent_tools.phone_utils import normalize_il_phone
        
        result = normalize_il_phone(None)
        assert result is None
    
    def test_normalize_invalid_returns_none(self):
        """Invalid phone returns None"""
        from server.agent_tools.phone_utils import normalize_il_phone
        
        result = normalize_il_phone("UNKNOWN")
        assert result is None


class TestRedactionRules:
    """Test sensitive data redaction"""
    
    def test_redact_credit_card_16_digits(self):
        """Redact 16-digit credit card number"""
        from server.agent_tools.tools_crm_context import redact_sensitive_data
        
        text = "My card is 4532015112830366"
        result = redact_sensitive_data(text)
        assert "4532015112830366" not in result
        assert "[REDACTED_CARD]" in result
    
    def test_redact_credit_card_13_digits(self):
        """Redact 13-digit credit card number"""
        from server.agent_tools.tools_crm_context import redact_sensitive_data
        
        text = "Card: 4532015112830"
        result = redact_sensitive_data(text)
        assert "4532015112830" not in result
        assert "[REDACTED_CARD]" in result
    
    def test_redact_password_pattern(self):
        """Redact password patterns"""
        from server.agent_tools.tools_crm_context import redact_sensitive_data
        
        text = "The password: mySecretPass123"
        result = redact_sensitive_data(text)
        assert "mySecretPass123" not in result
        assert "[REDACTED_PASSWORD]" in result
    
    def test_redact_hebrew_password_pattern(self):
        """Redact Hebrew password patterns"""
        from server.agent_tools.tools_crm_context import redact_sensitive_data
        
        text = "הסיסמה שלי: secret123"
        result = redact_sensitive_data(text)
        assert "secret123" not in result
        assert "[REDACTED_PASSWORD]" in result
    
    def test_redact_api_token(self):
        """Redact API tokens"""
        from server.agent_tools.tools_crm_context import redact_sensitive_data
        
        # Use a clearly fake token pattern for testing
        fake_token = "sk_test_" + "x" * 30
        text = f"Use token {fake_token}"
        result = redact_sensitive_data(text)
        assert fake_token not in result
        assert "[REDACTED_TOKEN]" in result
    
    def test_redact_israeli_id_with_label(self):
        """Redact Israeli ID when preceded by label"""
        from server.agent_tools.tools_crm_context import redact_sensitive_data
        
        text = "ת.ז: 123456789"
        result = redact_sensitive_data(text)
        assert "123456789" not in result
        assert "[REDACTED_ID]" in result
    
    def test_keep_phone_numbers(self):
        """Phone numbers should NOT be redacted"""
        from server.agent_tools.tools_crm_context import redact_sensitive_data
        
        text = "Call me at 0501234567"
        result = redact_sensitive_data(text)
        # 10 digits should remain (phone numbers)
        assert "0501234567" in result
    
    def test_none_input(self):
        """None input returns empty"""
        from server.agent_tools.tools_crm_context import redact_sensitive_data
        
        result = redact_sensitive_data(None)
        assert result is None
    
    def test_empty_string(self):
        """Empty string returns empty"""
        from server.agent_tools.tools_crm_context import redact_sensitive_data
        
        result = redact_sensitive_data("")
        assert result == ""


class TestMultiTenantSecurity:
    """Test multi-tenant isolation - critical security tests"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database for testing"""
        with patch('server.agent_tools.tools_crm_context.Lead') as mock_lead, \
             patch('server.agent_tools.tools_crm_context.LeadNote') as mock_note, \
             patch('server.agent_tools.tools_crm_context.Appointment') as mock_apt, \
             patch('server.agent_tools.tools_crm_context.db') as mock_db:
            yield {
                'Lead': mock_lead,
                'LeadNote': mock_note,
                'Appointment': mock_apt,
                'db': mock_db
            }
    
    def test_find_lead_requires_business_id(self, mock_db):
        """find_lead_by_phone must scope to business_id"""
        from server.agent_tools.tools_crm_context import FindLeadByPhoneInput, find_lead_by_phone
        
        # Setup mock
        mock_db['Lead'].query.filter_by.return_value.order_by.return_value.first.return_value = None
        
        # Call with business_id=1
        result = find_lead_by_phone(FindLeadByPhoneInput(business_id=1, phone="0501234567"))
        
        # Verify filter_by was called with tenant_id
        mock_db['Lead'].query.filter_by.assert_called_once()
        call_kwargs = mock_db['Lead'].query.filter_by.call_args[1]
        assert 'tenant_id' in call_kwargs
        assert call_kwargs['tenant_id'] == 1
    
    def test_get_lead_context_requires_business_id(self, mock_db):
        """get_lead_context must scope to business_id"""
        from server.agent_tools.tools_crm_context import GetLeadContextInput, get_lead_context
        
        # Setup mock - return None (lead not found)
        mock_db['Lead'].query.filter_by.return_value.first.return_value = None
        
        # Call with business_id=1, lead_id=99
        result = get_lead_context(GetLeadContextInput(business_id=1, lead_id=99))
        
        # Verify filter_by was called with both tenant_id and id
        mock_db['Lead'].query.filter_by.assert_called_once()
        call_kwargs = mock_db['Lead'].query.filter_by.call_args[1]
        assert 'tenant_id' in call_kwargs
        assert call_kwargs['tenant_id'] == 1
        assert 'id' in call_kwargs
        assert call_kwargs['id'] == 99
        
        # Result should indicate not found
        assert result.found is False
    
    def test_create_lead_note_validates_tenant(self, mock_db):
        """create_lead_note must verify lead belongs to tenant"""
        from server.agent_tools.tools_crm_context import CreateLeadNoteInput, create_lead_note
        
        # Setup mock - return None (lead not found in this tenant)
        mock_db['Lead'].query.filter_by.return_value.first.return_value = None
        
        # Try to create note for lead_id=99 in business_id=1
        result = create_lead_note(CreateLeadNoteInput(
            business_id=1,
            lead_id=99,
            note_type="call_summary",
            content="Test note"
        ))
        
        # Should fail because lead not found in this tenant
        assert result.success is False
        assert "not found" in result.message.lower() or "לא נמצא" in result.message
    
    def test_update_lead_fields_validates_tenant(self, mock_db):
        """update_lead_fields must verify lead belongs to tenant"""
        from server.agent_tools.tools_crm_context import UpdateLeadFieldsInput, update_lead_fields
        
        # Setup mock - return None (lead not found in this tenant)
        mock_db['Lead'].query.filter_by.return_value.first.return_value = None
        
        # Try to update lead_id=99 in business_id=1
        result = update_lead_fields(UpdateLeadFieldsInput(
            business_id=1,
            lead_id=99,
            patch={"status": "qualified"}
        ))
        
        # Should fail because lead not found in this tenant
        assert result.success is False
        assert "not found" in result.message.lower() or "לא נמצא" in result.message


class TestUpdateLeadFieldsSecurity:
    """Test field update security - prevent unauthorized field changes"""
    
    @pytest.fixture
    def mock_lead(self):
        """Create mock lead for testing"""
        mock = MagicMock()
        mock.id = 1
        mock.tenant_id = 1
        mock.status = "new"
        mock.tags = []
        mock.notes = ""
        mock.summary = None
        mock.service_type = None
        mock.city = None
        mock.first_name = "Test"
        mock.last_name = "User"
        mock.email = "test@example.com"
        return mock
    
    def test_blocked_fields_cannot_be_updated(self, mock_lead):
        """Blocked fields should be rejected"""
        from server.agent_tools.tools_crm_context import BLOCKED_FIELDS
        
        # Verify blocked fields list
        assert 'tenant_id' in BLOCKED_FIELDS
        assert 'business_id' in BLOCKED_FIELDS
        assert 'owner_user_id' in BLOCKED_FIELDS
        assert 'id' in BLOCKED_FIELDS
    
    def test_allowed_fields_can_be_updated(self):
        """Allowed fields should be in the whitelist"""
        from server.agent_tools.tools_crm_context import ALLOWED_UPDATE_FIELDS
        
        # Verify allowed fields
        assert 'status' in ALLOWED_UPDATE_FIELDS
        assert 'tags' in ALLOWED_UPDATE_FIELDS
        assert 'notes' in ALLOWED_UPDATE_FIELDS
        assert 'summary' in ALLOWED_UPDATE_FIELDS
        assert 'service_type' in ALLOWED_UPDATE_FIELDS
        assert 'city' in ALLOWED_UPDATE_FIELDS


class TestCallSummaryNote:
    """Test call summary note creation"""
    
    def test_call_summary_note_type(self):
        """Call summary notes should use correct note_type"""
        from server.agent_tools.tools_crm_context import CreateLeadNoteInput
        
        input_data = CreateLeadNoteInput(
            business_id=1,
            lead_id=1,
            note_type="call_summary",
            content="Summary content"
        )
        
        assert input_data.note_type == "call_summary"
    
    def test_call_summary_structured_data(self):
        """Call summary can include structured data"""
        from server.agent_tools.tools_crm_context import CreateLeadNoteInput
        
        input_data = CreateLeadNoteInput(
            business_id=1,
            lead_id=1,
            note_type="call_summary",
            content="Summary content",
            structured_data={
                "sentiment": "positive",
                "outcome": "appointment_set",
                "next_step_date": "2024-01-20"
            }
        )
        
        assert input_data.structured_data is not None
        assert input_data.structured_data["sentiment"] == "positive"
        assert input_data.structured_data["outcome"] == "appointment_set"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
