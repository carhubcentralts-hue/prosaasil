"""
Test simplified WhatsApp broadcast recipient extraction
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test the simplified extraction logic
def test_phone_extraction():
    """Test that phones are extracted from various input formats"""
    from server.routes_whatsapp import extract_phones_simplified, normalize_phone
    from werkzeug.datastructures import ImmutableMultiDict, FileStorage
    
    print("=" * 60)
    print("TEST 1: Direct phones as JSON array string")
    print("=" * 60)
    payload = {
        'phones': '["0521234567", "0527654321"]',
        'message_text': 'Test message'
    }
    phones = extract_phones_simplified(payload, {}, business_id=1)
    print(f"Result: {len(phones)} phones extracted")
    print(f"Phones: {phones}")
    assert len(phones) == 2, f"Expected 2 phones, got {len(phones)}"
    print("✅ PASS\n")
    
    print("=" * 60)
    print("TEST 2: Direct phones as list")
    print("=" * 60)
    payload = {
        'phones': ['972521234567', '972527654321'],
        'message_text': 'Test message'
    }
    phones = extract_phones_simplified(payload, {}, business_id=1)
    print(f"Result: {len(phones)} phones extracted")
    print(f"Phones: {phones}")
    assert len(phones) == 2, f"Expected 2 phones, got {len(phones)}"
    print("✅ PASS\n")
    
    print("=" * 60)
    print("TEST 3: Direct phones as CSV string")
    print("=" * 60)
    payload = {
        'phones': '0521234567, 0527654321, 0531111111',
        'message_text': 'Test message'
    }
    phones = extract_phones_simplified(payload, {}, business_id=1)
    print(f"Result: {len(phones)} phones extracted")
    print(f"Phones: {phones}")
    assert len(phones) == 3, f"Expected 3 phones, got {len(phones)}"
    print("✅ PASS\n")
    
    print("=" * 60)
    print("TEST 4: Single phone in different field name")
    print("=" * 60)
    payload = {
        'to': '+972521234567',
        'message_text': 'Test message'
    }
    phones = extract_phones_simplified(payload, {}, business_id=1)
    print(f"Result: {len(phones)} phones extracted")
    print(f"Phones: {phones}")
    assert len(phones) == 1, f"Expected 1 phone, got {len(phones)}"
    print("✅ PASS\n")
    
    print("=" * 60)
    print("TEST 5: Phone numbers in message text (last resort)")
    print("=" * 60)
    payload = {
        'message_text': 'Call me at 052-123-4567 or 0527654321'
    }
    phones = extract_phones_simplified(payload, {}, business_id=1)
    print(f"Result: {len(phones)} phones extracted")
    print(f"Phones: {phones}")
    assert len(phones) >= 2, f"Expected at least 2 phones, got {len(phones)}"
    print("✅ PASS\n")
    
    print("=" * 60)
    print("TEST 6: Alternative field name 'recipients'")
    print("=" * 60)
    payload = {
        'recipients': ['0521234567', '+972527654321'],
        'message_text': 'Test'
    }
    phones = extract_phones_simplified(payload, {}, business_id=1)
    print(f"Result: {len(phones)} phones extracted")
    print(f"Phones: {phones}")
    assert len(phones) == 2, f"Expected 2 phones, got {len(phones)}"
    print("✅ PASS\n")
    
    print("=" * 60)
    print("TEST 7: Empty payload (should return 0 phones)")
    print("=" * 60)
    payload = {}
    phones = extract_phones_simplified(payload, {}, business_id=1)
    print(f"Result: {len(phones)} phones extracted")
    assert len(phones) == 0, f"Expected 0 phones, got {len(phones)}"
    print("✅ PASS\n")
    
    print("=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == '__main__':
    # Set up minimal app context for testing
    try:
        from server.app_factory import create_app
        app = create_app()
        with app.app_context():
            test_phone_extraction()
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
