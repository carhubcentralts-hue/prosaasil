#!/usr/bin/env python3
"""
Validate that the fix is backward compatible with existing test cases
(Adapted from test_webhook_leads_extraction.py)
"""

# Import the validation functions
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from validate_webhook_fix import extract_lead_fields, normalize_phone_number, test_case


def main():
    """Run existing test cases to ensure backward compatibility"""
    print("=" * 80)
    print("BACKWARD COMPATIBILITY VALIDATION")
    print("Testing against existing test cases from test_webhook_leads_extraction.py")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    # Test: normal_payload_from_make
    def test_normal_payload_from_make():
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
    
    if test_case("test_normal_payload_from_make", test_normal_payload_from_make):
        passed += 1
    else:
        failed += 1
    
    # Test: phone_only
    def test_phone_only():
        payload = {
            'name': 'Jane Smith',
            'phone': '+972501234567'
        }
        fields = extract_lead_fields(payload)
        
        assert 'phone' in fields
        assert fields['phone'] == '+972501234567'
        assert 'email' not in fields
    
    if test_case("test_phone_only", test_phone_only):
        passed += 1
    else:
        failed += 1
    
    # Test: email_only
    def test_email_only():
        payload = {
            'name': 'Bob Johnson',
            'email': 'bob@example.com'
        }
        fields = extract_lead_fields(payload)
        
        assert 'email' in fields
        assert fields['email'] == 'bob@example.com'
        assert 'phone' not in fields
    
    if test_case("test_email_only", test_email_only):
        passed += 1
    else:
        failed += 1
    
    # Test: empty_string_values
    def test_empty_string_values():
        payload = {
            'name': 'Charlie Brown',
            'phone': '',
            'email': ''
        }
        fields = extract_lead_fields(payload)
        
        # Empty strings should not be extracted
        assert 'phone' not in fields
        assert 'email' not in fields
    
    if test_case("test_empty_string_values", test_empty_string_values):
        passed += 1
    else:
        failed += 1
    
    # Test: none_values
    def test_none_values():
        payload = {
            'name': 'David Lee',
            'phone': None,
            'email': None
        }
        fields = extract_lead_fields(payload)
        
        # None values should not be extracted
        assert 'phone' not in fields
        assert 'email' not in fields
    
    if test_case("test_none_values", test_none_values):
        passed += 1
    else:
        failed += 1
    
    # Test: nested_phone_dict
    def test_nested_phone_dict():
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
    
    if test_case("test_nested_phone_dict", test_nested_phone_dict):
        passed += 1
    else:
        failed += 1
    
    # Test: mobile_field
    def test_mobile_field():
        payload = {
            'name': 'Frank Miller',
            'mobile': '0531234567'
        }
        fields = extract_lead_fields(payload)
        
        assert 'phone' in fields
        assert fields['phone'] == '0531234567'
    
    if test_case("test_mobile_field", test_mobile_field):
        passed += 1
    else:
        failed += 1
    
    # Test: email_address_field
    def test_email_address_field():
        payload = {
            'name': 'Grace Taylor',
            'email_address': 'grace@example.com'
        }
        fields = extract_lead_fields(payload)
        
        assert 'email' in fields
        assert fields['email'] == 'grace@example.com'
    
    if test_case("test_email_address_field", test_email_address_field):
        passed += 1
    else:
        failed += 1
    
    # Test: case_insensitive
    def test_case_insensitive():
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
    
    if test_case("test_case_insensitive", test_case_insensitive):
        passed += 1
    else:
        failed += 1
    
    # Test: whitespace_trimming
    def test_whitespace_trimming():
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
    
    if test_case("test_whitespace_trimming", test_whitespace_trimming):
        passed += 1
    else:
        failed += 1
    
    # Test: non_dict_payload
    def test_non_dict_payload():
        assert extract_lead_fields(None) == {}
        assert extract_lead_fields([]) == {}
        assert extract_lead_fields("string") == {}
        assert extract_lead_fields(123) == {}
    
    if test_case("test_non_dict_payload", test_non_dict_payload):
        passed += 1
    else:
        failed += 1
    
    # Test: real_world_make_payload
    def test_real_world_make_payload():
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
        assert 'name' in fields
        assert fields['name'] == 'ישראל ישראלי'
    
    if test_case("test_real_world_make_payload", test_real_world_make_payload):
        passed += 1
    else:
        failed += 1
    
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)
    
    if failed == 0:
        print("✅ ALL BACKWARD COMPATIBILITY TESTS PASSED!")
        return 0
    else:
        print(f"❌ {failed} TESTS FAILED - Breaking changes detected")
        return 1


if __name__ == '__main__':
    exit(main())
