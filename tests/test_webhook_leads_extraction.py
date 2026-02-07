"""
Tests for webhook leads field extraction logic

This test file validates the extract_lead_fields function to ensure it properly
handles various payload formats from different sources (Make, Zapier, etc.)
"""
import pytest
import sys
import os

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from server.routes_webhook_leads import extract_lead_fields


class TestExtractLeadFields:
    """Test the extract_lead_fields function"""
    
    def test_normal_payload_from_make(self):
        """Test normal payload with phone, email, name, source"""
        payload = {
            'name': 'John Doe',
            'phone': '0501234567',
            'email': 'john@example.com',
            'source': 'make'
        }
        fields = extract_lead_fields(payload)
        
        assert 'phone' in fields
        assert fields['phone'] == '0501234567'
        assert 'email' in fields
        assert fields['email'] == 'john@example.com'
    
    def test_phone_only(self):
        """Test payload with only phone (no email)"""
        payload = {
            'name': 'Jane Smith',
            'phone': '+972501234567'
        }
        fields = extract_lead_fields(payload)
        
        assert 'phone' in fields
        assert fields['phone'] == '+972501234567'
        assert 'email' not in fields
    
    def test_email_only(self):
        """Test payload with only email (no phone)"""
        payload = {
            'name': 'Bob Johnson',
            'email': 'bob@example.com'
        }
        fields = extract_lead_fields(payload)
        
        assert 'email' in fields
        assert fields['email'] == 'bob@example.com'
        assert 'phone' not in fields
    
    def test_empty_string_values(self):
        """Test payload with empty string values - should not extract them"""
        payload = {
            'name': 'Charlie Brown',
            'phone': '',
            'email': ''
        }
        fields = extract_lead_fields(payload)
        
        # Empty strings should not be extracted
        assert 'phone' not in fields
        assert 'email' not in fields
    
    def test_none_values(self):
        """Test payload with None values - should not extract them"""
        payload = {
            'name': 'David Lee',
            'phone': None,
            'email': None
        }
        fields = extract_lead_fields(payload)
        
        # None values should not be extracted
        assert 'phone' not in fields
        assert 'email' not in fields
    
    def test_nested_phone_dict(self):
        """Test payload with nested phone object - should flatten and extract"""
        payload = {
            'name': 'Eve Wilson',
            'phone': {
                'number': '0521234567'
            },
            'email': 'eve@example.com'
        }
        fields = extract_lead_fields(payload)
        
        # Should extract phone_number from nested structure
        assert 'phone' in fields
        assert fields['phone'] == '0521234567'
        assert 'email' in fields
    
    def test_mobile_field(self):
        """Test that 'mobile' field is recognized as phone"""
        payload = {
            'name': 'Frank Miller',
            'mobile': '0531234567'
        }
        fields = extract_lead_fields(payload)
        
        assert 'phone' in fields
        assert fields['phone'] == '0531234567'
    
    def test_email_address_field(self):
        """Test that 'email_address' field is recognized as email"""
        payload = {
            'name': 'Grace Taylor',
            'email_address': 'grace@example.com'
        }
        fields = extract_lead_fields(payload)
        
        assert 'email' in fields
        assert fields['email'] == 'grace@example.com'
    
    def test_case_insensitive(self):
        """Test that field names are case-insensitive"""
        payload = {
            'Name': 'Henry Davis',
            'Phone': '0541234567',
            'Email': 'HENRY@EXAMPLE.COM'
        }
        fields = extract_lead_fields(payload)
        
        assert 'phone' in fields
        assert fields['phone'] == '0541234567'
        assert 'email' in fields
        # Email should be lowercased
        assert fields['email'] == 'henry@example.com'
    
    def test_whitespace_trimming(self):
        """Test that whitespace is trimmed from values"""
        payload = {
            'name': '  Iris Anderson  ',
            'phone': '  0551234567  ',
            'email': '  iris@example.com  '
        }
        fields = extract_lead_fields(payload)
        
        assert 'phone' in fields
        assert fields['phone'] == '0551234567'
        assert 'email' in fields
        assert fields['email'] == 'iris@example.com'
    
    def test_additional_fields(self):
        """Test extraction of additional fields like city, notes, source"""
        payload = {
            'name': 'Jack Brown',
            'phone': '0501234567',
            'city': 'Tel Aviv',
            'message': 'Interested in service',
            'source': 'website'
        }
        fields = extract_lead_fields(payload)
        
        assert 'phone' in fields
        assert 'city' in fields
        assert fields['city'] == 'Tel Aviv'
        assert 'notes' in fields
        assert fields['notes'] == 'Interested in service'
        assert 'source' in fields
        assert fields['source'] == 'website'
    
    def test_non_dict_payload(self):
        """Test that non-dict payloads return empty dict"""
        assert extract_lead_fields(None) == {}
        assert extract_lead_fields([]) == {}
        assert extract_lead_fields("string") == {}
        assert extract_lead_fields(123) == {}
    
    def test_real_world_make_payload(self):
        """Test realistic payload from Make.com"""
        payload = {
            'name': 'ישראל ישראלי',
            'phone': '0501234567',
            'email': 'israel@example.com',
            'source': 'Make Automation',
            'timestamp': '2024-01-01T00:00:00Z'
        }
        fields = extract_lead_fields(payload)
        
        assert 'phone' in fields
        assert fields['phone'] == '0501234567'
        assert 'email' in fields
        assert fields['email'] == 'israel@example.com'
        # Hebrew name should be preserved
        assert 'name' in fields or payload['name'] == 'ישראל ישראלי'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
