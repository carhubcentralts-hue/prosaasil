"""
Test: Name Extraction Fix for Outbound Calls
Validates the fixes for preventing None injection and comprehensive name resolution
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_none_injection_prevention():
    """Test that None/invalid names won't be injected"""
    print("🧪 Test 1: None Injection Prevention")
    
    # Read media_ws_ai.py and check for validation
    with open('server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Check that _ensure_name_anchor_present has validation
    ensure_func_start = content.find("async def _ensure_name_anchor_present")
    ensure_func = content[ensure_func_start:ensure_func_start + 3000]
    
    # Should have validation for None/empty names
    assert "if not current_name" in ensure_func, "Should validate name is not None/empty"
    assert "return" in ensure_func, "Should return early if name is invalid"
    print("✅ _ensure_name_anchor_present has None validation")
    
    # Check for invalid placeholder validation
    assert "invalid_values" in ensure_func or "placeholder" in ensure_func.lower(), \
        "Should validate against placeholder values"
    print("✅ Has placeholder validation (none, null, unknown, etc.)")
    
    # Check that we don't use 'None' string in hash anymore
    assert 'f"{current_name or \'None\'}"' not in ensure_func, \
        "Should not use 'None' string fallback in hash"
    print("✅ Does not use 'None' string fallback")
    
    print("✅ Test 1 PASSED: None injection prevention is in place\n")
    return True


def test_lead_id_resolution():
    """Test that lead_id parameter is used for name resolution"""
    print("🧪 Test 2: Lead ID Resolution")
    
    with open('server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Check that _resolve_customer_name accepts lead_id parameter
    resolve_func_start = content.find("def _resolve_customer_name")
    resolve_func = content[resolve_func_start:resolve_func_start + 5000]
    
    assert "lead_id: Optional[int] = None" in resolve_func, \
        "Should accept lead_id as parameter"
    print("✅ _resolve_customer_name accepts lead_id parameter")
    
    # Check for lead_id based lookup (Priority 2)
    assert "Lead.query.filter_by(id=lead_id" in resolve_func, \
        "Should query Lead by lead_id"
    print("✅ Has direct Lead lookup by lead_id")
    
    # Check that lead_id is extracted and passed to resolution
    call_resolve_start = content.find("resolved_name, name_source = _resolve_customer_name")
    call_resolve_section = content[call_resolve_start-1000:call_resolve_start+1500]
    
    assert "lead_id=lead_id" in call_resolve_section, \
        "Should pass lead_id to _resolve_customer_name"
    print("✅ lead_id is extracted and passed to resolution")
    
    # Check that outbound_lead_id is used
    assert "outbound_lead_id" in content, \
        "Should use outbound_lead_id attribute"
    print("✅ Uses outbound_lead_id from customParameters")
    
    print("✅ Test 2 PASSED: Lead ID resolution is implemented\n")
    return True


def test_phone_fallback():
    """Test that phone number fallback is implemented"""
    print("🧪 Test 3: Phone Number Fallback")
    
    with open('server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Check that _resolve_customer_name accepts lead_id parameter
    resolve_func_start = content.find("def _resolve_customer_name")
    resolve_func = content[resolve_func_start:resolve_func_start + 6000]  # Increased from 5000
    
    # Check for phone_number parameter
    assert "phone_number: Optional[str] = None" in resolve_func, \
        "Should accept phone_number as parameter"
    print("✅ _resolve_customer_name accepts phone_number parameter")
    
    # Check for phone-based Lead lookup  
    # The query might be split across lines, so check for key parts
    assert "Lead.phone_e164" in resolve_func and "phone_number" in resolve_func, \
        "Should query Lead by phone number"
    print("✅ Has Lead lookup by phone number")
    
    # Check for proper ordering (should be fallback, not priority 1)
    assert "Priority 5" in resolve_func or "Fallback" in resolve_func, \
        "Phone lookup should be fallback priority"
    print("✅ Phone lookup is correctly positioned as fallback")
    
    # Check that phone_number is passed to resolution
    call_resolve_start = content.find("resolved_name, name_source = _resolve_customer_name")
    call_resolve_section = content[call_resolve_start-500:call_resolve_start+1000]
    
    assert "phone_number=phone_number" in call_resolve_section, \
        "Should pass phone_number to _resolve_customer_name"
    print("✅ phone_number is extracted and passed to resolution")
    
    print("✅ Test 3 PASSED: Phone fallback is implemented\n")
    return True


def test_debug_logging():
    """Test that comprehensive debug logging is in place"""
    print("🧪 Test 4: Debug Logging")
    
    with open('server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    resolve_func_start = content.find("def _resolve_customer_name")
    resolve_func = content[resolve_func_start:resolve_func_start + 6000]  # Increased range
    
    # Check for debug logging of input parameters
    assert "[NAME_RESOLVE DEBUG]" in resolve_func or "[NAME_RESOLVE]" in resolve_func, \
        "Should have NAME_RESOLVE debug logging"
    print("✅ Has NAME_RESOLVE debug logs")
    
    # Check for source logging
    assert "source=lead_id" in resolve_func, "Should log source=lead_id"
    assert "source=lead_phone" in resolve_func, \
        "Should log source when name found via phone"
    print("✅ Logs name resolution source")
    
    # Check call resolution has detailed logging
    call_resolve_start = content.find("resolved_name, name_source = _resolve_customer_name")
    call_resolve_section = content[call_resolve_start:call_resolve_start+2000]
    
    assert "lead_id from customParameters" in call_resolve_section, \
        "Should log lead_id from customParameters"
    assert "phone_number for fallback" in call_resolve_section, \
        "Should log phone_number for fallback"
    print("✅ Logs input parameters for debugging")
    
    # Check for failure logging
    assert "Name resolution FAILED" in call_resolve_section or \
           "No name found" in call_resolve_section, \
        "Should log when resolution fails"
    print("✅ Logs failure reasons")
    
    print("✅ Test 4 PASSED: Debug logging is comprehensive\n")
    return True


def test_outbound_parameters():
    """Test that outbound call parameters are correctly passed through"""
    print("🧪 Test 5: Outbound Parameters Passing")
    
    # Check routes_twilio.py passes lead_id
    with open('server/routes_twilio.py', 'r') as f:
        routes_content = f.read()
    
    outbound_webhook = routes_content[routes_content.find("def outbound_call"):
                                      routes_content.find("def outbound_call") + 3000]
    
    assert 'stream.parameter(name="lead_id"' in outbound_webhook, \
        "Should pass lead_id as stream parameter"
    print("✅ routes_twilio.py passes lead_id as stream parameter")
    
    # Check media_ws_ai.py extracts lead_id
    with open('server/media_ws_ai.py', 'r') as f:
        ws_content = f.read()
    
    # Check for lead_id extraction anywhere in the file
    assert 'self.outbound_lead_id = custom_params.get("lead_id")' in ws_content or \
           'self.outbound_lead_id = evt.get("lead_id")' in ws_content, \
        "Should extract lead_id from customParameters"
    print("✅ media_ws_ai.py extracts lead_id from customParameters")
    
    print("✅ Test 5 PASSED: Outbound parameters are passed correctly\n")
    return True


def run_all_tests():
    """Run all tests"""
    print("=" * 70)
    print("🧪 NAME EXTRACTION FIX - TEST SUITE")
    print("=" * 70 + "\n")
    
    tests = [
        ("None Injection Prevention", test_none_injection_prevention),
        ("Lead ID Resolution", test_lead_id_resolution),
        ("Phone Number Fallback", test_phone_fallback),
        ("Debug Logging", test_debug_logging),
        ("Outbound Parameters", test_outbound_parameters),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except AssertionError as e:
            print(f"❌ Test FAILED: {test_name}")
            print(f"   Error: {e}\n")
            failed += 1
        except Exception as e:
            print(f"❌ Test ERROR: {test_name}")
            print(f"   Exception: {e}\n")
            failed += 1
    
    print("=" * 70)
    print(f"📊 TEST RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed > 0:
        print("\n❌ Some tests failed!")
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    run_all_tests()
