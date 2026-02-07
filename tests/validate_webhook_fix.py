#!/usr/bin/env python3
"""
Manual validation script for webhook leads fix

This script validates the core logic without requiring Flask dependencies.
It tests the key functions: extract_lead_fields and normalize_phone_number.
"""

def normalize_phone_number(phone):
    """
    Normalize phone number to E.164 format
    (Copied from routes_webhook_leads.py for standalone testing)
    """
    if not phone:
        return None
    
    phone = str(phone).strip()
    phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    
    if not phone:
        return None
    
    if phone.startswith('+'):
        return phone
    
    if phone.startswith('0') and len(phone) >= 9:
        return f"+972{phone[1:]}"
    
    if phone.startswith('972') and len(phone) >= 12:
        return f"+{phone}"
    
    if phone.isdigit() and len(phone) >= 10:
        return f"+{phone}"
    
    return phone


def extract_lead_fields(payload):
    """
    Extract lead fields from webhook payload
    (Copied from routes_webhook_leads.py for standalone testing)
    """
    if not isinstance(payload, dict):
        return {}
    
    result = {}
    flat_payload = {}
    
    # First, add all direct (non-dict) values
    for key, value in payload.items():
        if not isinstance(value, dict):
            flat_payload[key.lower()] = value
    
    # Check for nested "contact" object
    if 'contact' in payload and isinstance(payload['contact'], dict):
        contact_data = payload['contact']
        for key, value in contact_data.items():
            field_key = key.lower()
            if field_key not in flat_payload and not isinstance(value, dict):
                flat_payload[field_key] = value
    
    # Flatten other nested dicts with prefix
    for key, value in payload.items():
        if isinstance(value, dict) and key.lower() != 'contact':
            for nested_key, nested_value in value.items():
                prefixed_key = f"{key}_{nested_key}".lower()
                if prefixed_key not in flat_payload and not isinstance(nested_value, dict):
                    flat_payload[prefixed_key] = nested_value
    
    # Extract name
    name_fields = ['name', 'full_name', 'fullname', 'customer_name', 'contact_name']
    for field in name_fields:
        if field in flat_payload and flat_payload[field]:
            result['name'] = str(flat_payload[field]).strip()
            break
    
    # Extract phone
    phone_fields = ['phone', 'mobile', 'tel', 'telephone', 'phone_number', 'phonenumber', 'cell', 'cellphone']
    for field in phone_fields:
        if field in flat_payload and flat_payload[field]:
            phone_value = str(flat_payload[field]).strip()
            if phone_value:
                result['phone'] = phone_value
                break
    
    # Extract email
    email_fields = ['email', 'email_address', 'emailaddress', 'mail']
    for field in email_fields:
        if field in flat_payload and flat_payload[field]:
            email_value = str(flat_payload[field]).strip().lower()
            if email_value:
                result['email'] = email_value
                break
    
    # Extract source
    source_fields = ['source', 'lead_source', 'origin']
    for field in source_fields:
        if field in flat_payload and flat_payload[field]:
            result['source'] = str(flat_payload[field]).strip()
            break
    
    return result


def test_case(name, test_func):
    """Run a test case and print result"""
    try:
        test_func()
        print(f"✅ {name}")
        return True
    except AssertionError as e:
        print(f"❌ {name}: {e}")
        return False
    except Exception as e:
        print(f"❌ {name}: Unexpected error: {e}")
        return False


def main():
    """Run all validation tests"""
    print("=" * 80)
    print("WEBHOOK LEADS FIX - MANUAL VALIDATION")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    # Test 1: Flat payload with all fields
    def test1():
        payload = {
            'name': 'John Doe',
            'phone': '0501234567',
            'email': 'john@example.com',
            'source': 'make'
        }
        fields = extract_lead_fields(payload)
        assert fields['name'] == 'John Doe', f"Expected 'John Doe', got {fields.get('name')}"
        assert fields['phone'] == '0501234567', f"Expected '0501234567', got {fields.get('phone')}"
        assert fields['email'] == 'john@example.com', f"Expected 'john@example.com', got {fields.get('email')}"
        assert fields['source'] == 'make', f"Expected 'make', got {fields.get('source')}"
    
    if test_case("Test 1: Flat payload extraction", test1):
        passed += 1
    else:
        failed += 1
    
    # Test 2: Nested contact payload
    def test2():
        payload = {
            'contact': {
                'name': 'Jane Smith',
                'phone': '0521234567',
                'email': 'jane@example.com'
            },
            'source': 'zapier'
        }
        fields = extract_lead_fields(payload)
        assert fields['name'] == 'Jane Smith', f"Expected 'Jane Smith', got {fields.get('name')}"
        assert fields['phone'] == '0521234567', f"Expected '0521234567', got {fields.get('phone')}"
        assert fields['email'] == 'jane@example.com', f"Expected 'jane@example.com', got {fields.get('email')}"
        assert fields['source'] == 'zapier', f"Expected 'zapier', got {fields.get('source')}"
    
    if test_case("Test 2: Nested contact payload extraction", test2):
        passed += 1
    else:
        failed += 1
    
    # Test 3: Phone normalization - Israeli number
    def test3():
        phone = normalize_phone_number('0501234567')
        assert phone == '+972501234567', f"Expected '+972501234567', got {phone}"
    
    if test_case("Test 3: Phone normalization (Israeli)", test3):
        passed += 1
    else:
        failed += 1
    
    # Test 4: Phone normalization - with dashes
    def test4():
        phone = normalize_phone_number('050-123-4567')
        assert phone == '+972501234567', f"Expected '+972501234567', got {phone}"
    
    if test_case("Test 4: Phone normalization (dashes)", test4):
        passed += 1
    else:
        failed += 1
    
    # Test 5: Phone normalization - with spaces
    def test5():
        phone = normalize_phone_number('050 123 4567')
        assert phone == '+972501234567', f"Expected '+972501234567', got {phone}"
    
    if test_case("Test 5: Phone normalization (spaces)", test5):
        passed += 1
    else:
        failed += 1
    
    # Test 6: Phone only (no email)
    def test6():
        payload = {'name': 'Bob', 'phone': '0531234567'}
        fields = extract_lead_fields(payload)
        assert 'phone' in fields, "Phone should be extracted"
        assert 'email' not in fields, "Email should not be present"
    
    if test_case("Test 6: Phone only extraction", test6):
        passed += 1
    else:
        failed += 1
    
    # Test 7: Email only (no phone)
    def test7():
        payload = {'name': 'Alice', 'email': 'alice@example.com'}
        fields = extract_lead_fields(payload)
        assert 'email' in fields, "Email should be extracted"
        assert 'phone' not in fields, "Phone should not be present"
    
    if test_case("Test 7: Email only extraction", test7):
        passed += 1
    else:
        failed += 1
    
    # Test 8: Missing both phone and email
    def test8():
        payload = {'name': 'Charlie', 'source': 'test'}
        fields = extract_lead_fields(payload)
        assert 'phone' not in fields, "Phone should not be present"
        assert 'email' not in fields, "Email should not be present"
        assert fields.get('name') == 'Charlie', "Name should be extracted"
        assert fields.get('source') == 'test', "Source should be extracted"
    
    if test_case("Test 8: Missing phone/email (should extract other fields)", test8):
        passed += 1
    else:
        failed += 1
    
    # Test 9: Hebrew text support
    def test9():
        payload = {
            'name': 'ישראל ישראלי',
            'phone': '0501234567',
            'email': 'israel@example.com'
        }
        fields = extract_lead_fields(payload)
        assert fields['name'] == 'ישראל ישראלי', f"Expected Hebrew name, got {fields.get('name')}"
    
    if test_case("Test 9: Hebrew text support", test9):
        passed += 1
    else:
        failed += 1
    
    # Test 10: Mobile field variant
    def test10():
        payload = {'name': 'David', 'mobile': '0541234567'}
        fields = extract_lead_fields(payload)
        assert fields.get('phone') == '0541234567', f"Expected '0541234567', got {fields.get('phone')}"
    
    if test_case("Test 10: Mobile field variant", test10):
        passed += 1
    else:
        failed += 1
    
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)
    
    if failed == 0:
        print("✅ ALL TESTS PASSED - Fix is working correctly!")
        return 0
    else:
        print(f"❌ {failed} TESTS FAILED - Fix needs adjustment")
        return 1


if __name__ == '__main__':
    exit(main())
