#!/usr/bin/env python3
"""
Test webhook lead extraction with Google Sheets payloads
Tests the fixes for numeric phone values and field alias support
"""
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from server.routes_webhook_leads import extract_lead_fields


def test_google_sheets_payload():
    """Test extraction with Google Sheets payload (numeric phone)"""
    payload = {
        "name": "צוריאל ארביב",
        "email": "tzurielarviv@gmail.com",
        "phone": 549750505,  # Numeric phone without leading zero
        "source": "google_sheet"
    }
    
    fields = extract_lead_fields(payload)
    
    print(f"✅ Test 1: Google Sheets payload")
    print(f"   Input: {payload}")
    print(f"   Extracted: {fields}")
    
    # Assertions
    assert fields.get('name') == "צוריאל ארביב", f"Expected name 'צוריאל ארביב', got {fields.get('name')}"
    assert fields.get('email') == "tzurielarviv@gmail.com", f"Expected email 'tzurielarviv@gmail.com', got {fields.get('email')}"
    assert fields.get('phone') == "549750505", f"Expected phone '549750505', got {fields.get('phone')}"
    assert fields.get('source') == "google_sheet", f"Expected source 'google_sheet', got {fields.get('source')}"
    
    print(f"   ✅ All fields extracted correctly\n")


def test_phone_aliases():
    """Test phone field aliases"""
    test_cases = [
        ({"whatsapp": "+972501234567"}, "whatsapp"),
        ({"phoneNumber": "0541234567"}, "phoneNumber (camelCase)"),
        ({"phone_number": "0521234567"}, "phone_number"),
        ({"mobile": "0531234567"}, "mobile"),
        ({"tel": 501234567}, "tel (numeric)"),
    ]
    
    print(f"✅ Test 2: Phone field aliases")
    for payload, desc in test_cases:
        fields = extract_lead_fields(payload)
        phone = fields.get('phone')
        print(f"   {desc}: {list(payload.keys())[0]}={list(payload.values())[0]} → phone={phone}")
        assert phone, f"Failed to extract phone from {desc}"
    print(f"   ✅ All phone aliases work\n")


def test_source_aliases():
    """Test source field aliases"""
    test_cases = [
        ({"source": "google_sheet", "phone": "123"}, "source"),
        ({"utm_source": "facebook", "phone": "123"}, "utm_source"),
        ({"lead_source": "linkedin", "phone": "123"}, "lead_source"),
        ({"origin": "website", "phone": "123"}, "origin"),
    ]
    
    print(f"✅ Test 3: Source field aliases")
    for payload, desc in test_cases:
        fields = extract_lead_fields(payload)
        source = fields.get('source')
        expected = list(payload.values())[0]
        print(f"   {desc}: value={expected} → source={source}")
        assert source == expected, f"Failed to extract source from {desc}"
    print(f"   ✅ All source aliases work\n")


def test_numeric_phone_types():
    """Test various numeric phone types"""
    test_cases = [
        ({"phone": 549750505, "name": "Test1"}, "int without leading zero"),
        ({"phone": 972501234567, "name": "Test2"}, "int with country code"),
        ({"phone": 501234567, "name": "Test3"}, "int short format"),
        ({"phone": "0501234567", "name": "Test4"}, "string with leading zero"),
        ({"phone": "+972501234567", "name": "Test5"}, "string with +"),
    ]
    
    print(f"✅ Test 4: Numeric phone types")
    for payload, desc in test_cases:
        fields = extract_lead_fields(payload)
        phone = fields.get('phone')
        print(f"   {desc}: input={payload['phone']!r} (type={type(payload['phone']).__name__}) → phone={phone!r}")
        assert phone, f"Failed to extract phone from {desc}"
        assert isinstance(phone, str), f"Phone should be string, got {type(phone)}"
    print(f"   ✅ All numeric phone types handled\n")


def test_empty_and_edge_cases():
    """Test edge cases"""
    test_cases = [
        ({}, "empty payload"),
        ({"name": "Test"}, "only name (no contact)"),
        ({"phone": ""}, "empty phone string"),
        ({"phone": 0}, "phone=0 (falsy but valid)"),
        ({"email": ""}, "empty email"),
    ]
    
    print(f"✅ Test 5: Edge cases")
    for payload, desc in test_cases:
        fields = extract_lead_fields(payload)
        print(f"   {desc}: payload={payload} → fields={fields}")
    print(f"   ✅ Edge cases handled without crashing\n")


if __name__ == "__main__":
    print("=" * 80)
    print("WEBHOOK GOOGLE SHEETS EXTRACTION TESTS")
    print("=" * 80)
    print()
    
    try:
        test_google_sheets_payload()
        test_phone_aliases()
        test_source_aliases()
        test_numeric_phone_types()
        test_empty_and_edge_cases()
        
        print("=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        
    except AssertionError as e:
        print("\n" + "=" * 80)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 80)
        sys.exit(1)
    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ UNEXPECTED ERROR: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        sys.exit(1)
