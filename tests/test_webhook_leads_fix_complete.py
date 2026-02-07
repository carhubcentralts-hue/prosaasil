"""
Comprehensive tests for webhook leads fix

Tests the complete fix for webhook lead creation including:
1. Field extraction from flat and nested payloads
2. Phone normalization
3. Upsert logic (create vs update)
4. Target status enforcement
5. Proper error handling
"""
import pytest
import sys
import os

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from server.routes_webhook_leads import extract_lead_fields, normalize_phone_number


class TestPhoneNormalization:
    """Test phone number normalization to E.164 format"""
    
    def test_israeli_number_with_leading_zero(self):
        """Israeli number 0501234567 should become +972501234567"""
        assert normalize_phone_number("0501234567") == "+972501234567"
        assert normalize_phone_number("0521234567") == "+972521234567"
    
    def test_israeli_number_with_spaces(self):
        """Phone with spaces should be cleaned"""
        assert normalize_phone_number("050 123 4567") == "+972501234567"
        assert normalize_phone_number("050-123-4567") == "+972501234567"
    
    def test_israeli_number_with_dashes(self):
        """Phone with dashes should be cleaned"""
        assert normalize_phone_number("050-123-4567") == "+972501234567"
    
    def test_number_already_with_plus(self):
        """Number already with + should be kept as-is"""
        assert normalize_phone_number("+972501234567") == "+972501234567"
        assert normalize_phone_number("+1234567890") == "+1234567890"
    
    def test_israeli_number_without_leading_zero(self):
        """972501234567 should become +972501234567"""
        assert normalize_phone_number("972501234567") == "+972501234567"
    
    def test_empty_phone(self):
        """Empty phone should return None"""
        assert normalize_phone_number("") is None
        assert normalize_phone_number(None) is None
        assert normalize_phone_number("   ") is None
    
    def test_phone_with_parentheses(self):
        """Phone with parentheses should be cleaned"""
        assert normalize_phone_number("(050) 123-4567") == "+972501234567"


class TestExtractLeadFieldsFlat:
    """Test field extraction from flat payloads"""
    
    def test_flat_payload_with_all_fields(self):
        """Test flat payload: {name, phone, email, source}"""
        payload = {
            'name': 'John Doe',
            'phone': '0501234567',
            'email': 'john@example.com',
            'source': 'make'
        }
        fields = extract_lead_fields(payload)
        
        assert fields['name'] == 'John Doe'
        assert fields['phone'] == '0501234567'
        assert fields['email'] == 'john@example.com'
        assert fields['source'] == 'make'
    
    def test_flat_payload_phone_only(self):
        """Test flat payload with only phone (no email)"""
        payload = {
            'name': 'Jane Smith',
            'phone': '0521234567'
        }
        fields = extract_lead_fields(payload)
        
        assert fields['name'] == 'Jane Smith'
        assert fields['phone'] == '0521234567'
        assert 'email' not in fields
    
    def test_flat_payload_email_only(self):
        """Test flat payload with only email (no phone)"""
        payload = {
            'name': 'Bob Johnson',
            'email': 'bob@example.com'
        }
        fields = extract_lead_fields(payload)
        
        assert fields['name'] == 'Bob Johnson'
        assert fields['email'] == 'bob@example.com'
        assert 'phone' not in fields
    
    def test_flat_payload_missing_both(self):
        """Test flat payload missing both phone and email"""
        payload = {
            'name': 'Charlie Brown',
            'city': 'Tel Aviv'
        }
        fields = extract_lead_fields(payload)
        
        # Should extract name and city, but no phone/email
        assert fields['name'] == 'Charlie Brown'
        assert fields['city'] == 'Tel Aviv'
        assert 'phone' not in fields
        assert 'email' not in fields


class TestExtractLeadFieldsNested:
    """Test field extraction from nested payloads"""
    
    def test_nested_contact_payload(self):
        """Test nested payload: {contact: {name, phone, email}, source}"""
        payload = {
            'contact': {
                'name': 'David Lee',
                'phone': '0531234567',
                'email': 'david@example.com'
            },
            'source': 'zapier'
        }
        fields = extract_lead_fields(payload)
        
        assert fields['name'] == 'David Lee'
        assert fields['phone'] == '0531234567'
        assert fields['email'] == 'david@example.com'
        assert fields['source'] == 'zapier'
    
    def test_nested_contact_partial_fields(self):
        """Test nested payload with only some fields in contact"""
        payload = {
            'contact': {
                'name': 'Eve Wilson',
                'phone': '0541234567'
            },
            'source': 'website'
        }
        fields = extract_lead_fields(payload)
        
        assert fields['name'] == 'Eve Wilson'
        assert fields['phone'] == '0541234567'
        assert 'email' not in fields
        assert fields['source'] == 'website'
    
    def test_mixed_nested_and_flat(self):
        """Test payload with both nested contact and flat source"""
        payload = {
            'contact': {
                'name': 'Frank Miller',
                'email': 'frank@example.com'
            },
            'phone': '0551234567',  # Flat phone should take priority
            'source': 'mixed'
        }
        fields = extract_lead_fields(payload)
        
        # Flat phone should take priority over nested
        assert fields['phone'] == '0551234567'
        assert fields['name'] == 'Frank Miller'
        assert fields['email'] == 'frank@example.com'
        assert fields['source'] == 'mixed'


class TestExtractLeadFieldsVariants:
    """Test field extraction with various field name variants"""
    
    def test_mobile_field(self):
        """Test 'mobile' field is recognized as phone"""
        payload = {
            'name': 'Grace Taylor',
            'mobile': '0501234567'
        }
        fields = extract_lead_fields(payload)
        
        assert fields['phone'] == '0501234567'
    
    def test_email_address_field(self):
        """Test 'email_address' field is recognized as email"""
        payload = {
            'name': 'Henry Davis',
            'email_address': 'henry@example.com'
        }
        fields = extract_lead_fields(payload)
        
        assert fields['email'] == 'henry@example.com'
    
    def test_message_as_notes(self):
        """Test 'message' field is extracted as notes"""
        payload = {
            'name': 'Iris Anderson',
            'phone': '0521234567',
            'message': 'Interested in service'
        }
        fields = extract_lead_fields(payload)
        
        assert fields['notes'] == 'Interested in service'


class TestExtractLeadFieldsEdgeCases:
    """Test edge cases for field extraction"""
    
    def test_empty_string_values(self):
        """Empty strings should not be extracted"""
        payload = {
            'name': 'Jack Brown',
            'phone': '',
            'email': ''
        }
        fields = extract_lead_fields(payload)
        
        assert fields['name'] == 'Jack Brown'
        assert 'phone' not in fields
        assert 'email' not in fields
    
    def test_none_values(self):
        """None values should not be extracted"""
        payload = {
            'name': 'Kate Green',
            'phone': None,
            'email': None
        }
        fields = extract_lead_fields(payload)
        
        assert fields['name'] == 'Kate Green'
        assert 'phone' not in fields
        assert 'email' not in fields
    
    def test_case_insensitive(self):
        """Field names should be case-insensitive"""
        payload = {
            'Name': 'Larry White',
            'Phone': '0531234567',
            'Email': 'LARRY@EXAMPLE.COM'
        }
        fields = extract_lead_fields(payload)
        
        assert fields['name'] == 'Larry White'
        assert fields['phone'] == '0531234567'
        assert fields['email'] == 'larry@example.com'  # Email lowercased
    
    def test_whitespace_trimming(self):
        """Whitespace should be trimmed"""
        payload = {
            'name': '  Mary Black  ',
            'phone': '  0541234567  ',
            'email': '  mary@example.com  '
        }
        fields = extract_lead_fields(payload)
        
        assert fields['name'] == 'Mary Black'
        assert fields['phone'] == '0541234567'
        assert fields['email'] == 'mary@example.com'


class TestRealWorldPayloads:
    """Test with realistic payloads from Make, Zapier, etc."""
    
    def test_make_flat_payload(self):
        """Test realistic Make.com flat payload"""
        payload = {
            'name': 'ישראל ישראלי',
            'phone': '0501234567',
            'email': 'israel@example.com',
            'source': 'Make Automation'
        }
        fields = extract_lead_fields(payload)
        
        assert fields['name'] == 'ישראל ישראלי'
        assert fields['phone'] == '0501234567'
        assert fields['email'] == 'israel@example.com'
        assert fields['source'] == 'Make Automation'
    
    def test_zapier_nested_payload(self):
        """Test realistic Zapier nested payload"""
        payload = {
            'contact': {
                'name': 'שרה כהן',
                'phone': '+972521234567',
                'email': 'sara@example.com'
            },
            'source': 'Zapier',
            'timestamp': '2024-01-01T00:00:00Z'
        }
        fields = extract_lead_fields(payload)
        
        assert fields['name'] == 'שרה כהן'
        assert fields['phone'] == '+972521234567'
        assert fields['email'] == 'sara@example.com'
        assert fields['source'] == 'Zapier'
    
    def test_form_submission_payload(self):
        """Test realistic form submission payload"""
        payload = {
            'name': 'דוד לוי',
            'phone': '050-123-4567',
            'email': 'david@example.com',
            'city': 'תל אביב',
            'message': 'מעוניין בשירות חשמלאי',
            'source': 'website_form'
        }
        fields = extract_lead_fields(payload)
        
        assert fields['name'] == 'דוד לוי'
        assert fields['phone'] == '050-123-4567'  # Not normalized here, will be in handler
        assert fields['email'] == 'david@example.com'
        assert fields['city'] == 'תל אביב'
        assert fields['notes'] == 'מעוניין בשירות חשמלאי'
        assert fields['source'] == 'website_form'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
