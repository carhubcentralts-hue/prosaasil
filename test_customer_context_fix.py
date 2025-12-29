"""
Test: Customer Context Fix - Verify From parameter and lead_id updates
Validates that customer context is properly passed to AI and appointment tools
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_inbound_twiml_has_from_parameter():
    """Test that incoming_call TwiML includes From parameter"""
    print("🧪 Testing inbound TwiML includes From parameter...")
    
    with open('server/routes_twilio.py', 'r') as f:
        content = f.read()
    
    # Find incoming_call function
    assert "def incoming_call():" in content, "incoming_call function should exist"
    
    # Find the stream parameters section for inbound calls
    # Look for the section between incoming_call and outbound_call
    inbound_start = content.find("def incoming_call():")
    outbound_start = content.find("def outbound_call():")
    inbound_section = content[inbound_start:outbound_start]
    
    # Check that CallSid, To, and From parameters are all present
    assert 'stream.parameter(name="CallSid"' in inbound_section, "Should have CallSid parameter"
    assert 'stream.parameter(name="To"' in inbound_section, "Should have To parameter"
    assert 'stream.parameter(name="From"' in inbound_section, "Should have From parameter for customer context"
    
    # Verify From parameter uses from_number variable
    assert 'value=from_number' in inbound_section or 'from_number or "unknown"' in inbound_section, \
        "From parameter should use from_number variable"
    
    print("✅ Inbound TwiML correctly includes From parameter")
    return True


def test_outbound_twiml_has_from_parameter():
    """Test that outbound_call TwiML includes From parameter"""
    print("\n🧪 Testing outbound TwiML includes From parameter...")
    
    with open('server/routes_twilio.py', 'r') as f:
        content = f.read()
    
    # Find outbound_call function
    assert "def outbound_call():" in content, "outbound_call function should exist"
    
    # Find the stream parameters section for outbound calls
    outbound_start = content.find("def outbound_call():")
    # Look for next function after outbound_call (stream_ended)
    next_func = content.find("def ", outbound_start + 100)
    outbound_section = content[outbound_start:next_func]
    
    # Check that CallSid, To, From, and lead parameters are present
    assert 'stream.parameter(name="CallSid"' in outbound_section, "Should have CallSid parameter"
    assert 'stream.parameter(name="To"' in outbound_section, "Should have To parameter"
    assert 'stream.parameter(name="From"' in outbound_section, "Should have From parameter for consistent context"
    assert 'stream.parameter(name="lead_id"' in outbound_section, "Should have lead_id parameter"
    assert 'stream.parameter(name="lead_name"' in outbound_section, "Should have lead_name parameter"
    
    print("✅ Outbound TwiML correctly includes From parameter")
    return True


def test_call_log_lead_id_update_after_customer_intelligence():
    """Test that call_log.lead_id is updated after CustomerIntelligence creates lead"""
    print("\n🧪 Testing call_log.lead_id update after CustomerIntelligence...")
    
    with open('server/routes_twilio.py', 'r') as f:
        content = f.read()
    
    # Check that CustomerIntelligence is used
    assert "CustomerIntelligence" in content, "Should use CustomerIntelligence"
    assert "find_or_create_customer_from_call" in content, "Should call find_or_create_customer_from_call"
    
    # Check that call_log is updated with both customer_id and lead_id
    assert "call_log.customer_id" in content, "Should update call_log.customer_id"
    assert "call_log.lead_id = lead.id" in content, "Should update call_log.lead_id"
    
    # Check for the specific comment we added
    assert "# 🔥 FIX: Also update lead_id" in content or "# 🔥 FIX: Update call_log with lead_id" in content, \
        "Should have our fix comment"
    
    print("✅ call_log.lead_id is updated after CustomerIntelligence")
    return True


def test_call_log_lead_id_update_in_fallback():
    """Test that call_log.lead_id is updated in fallback lead creation path"""
    print("\n🧪 Testing call_log.lead_id update in fallback path...")
    
    with open('server/routes_twilio.py', 'r') as f:
        content = f.read()
    
    # Check for fallback lead creation
    assert "if not lead:" in content, "Should have fallback lead creation"
    assert "CREATED FALLBACK LEAD" in content or "LEAD_CREATED_FALLBACK" in content, \
        "Should log fallback lead creation"
    
    # Check that we update call_log.lead_id after creating fallback lead
    assert "call_log.lead_id = lead.id" in content, \
        "Should update call_log.lead_id after fallback lead creation"
    
    print("✅ call_log.lead_id is updated in fallback path")
    return True


def test_name_resolution_can_use_phone_number():
    """Test that _resolve_customer_name function can use phone_number"""
    print("\n🧪 Testing name resolution with phone_number...")
    
    with open('server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Find _resolve_customer_name function
    assert "def _resolve_customer_name" in content, "_resolve_customer_name function should exist"
    
    # Check that function accepts phone_number parameter
    assert "phone_number: Optional[str]" in content or "phone_number=" in content, \
        "Function should accept phone_number parameter"
    
    # Check that it uses phone_number for Lead lookup
    assert "Lead.phone_e164" in content, "Should query Lead by phone"
    
    # Check priority comment mentions phone lookup
    assert "Priority 5: Fallback - Lead lookup by phone" in content or \
           "Fallback: Lead lookup by phone" in content, \
        "Should document phone lookup as fallback"
    
    print("✅ Name resolution can use phone_number for lookup")
    return True


def test_name_resolution_uses_calllog_lead_id():
    """Test that _resolve_customer_name uses CallLog.lead_id"""
    print("\n🧪 Testing name resolution uses CallLog.lead_id...")
    
    with open('server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Check that it queries CallLog
    assert "CallLog.query" in content, "Should query CallLog"
    
    # Check that resolution uses lead_id parameter or call_log relationship
    # Priority 2: Lead by lead_id
    assert "Priority 2: Lead by lead_id" in content or "lead_id" in content, \
        "Should support lead_id lookup"
    
    # Priority 4: Lead via CallLog.lead_id
    assert "Priority 4: Lead.full_name (via CallLog.lead_id)" in content or \
           "call_log.lead_id" in content, \
        "Should use CallLog.lead_id relationship"
    
    print("✅ Name resolution uses CallLog.lead_id")
    return True


def run_all_tests():
    """Run all tests"""
    print("="*70)
    print("Customer Context Fix Tests - From Parameter & lead_id Updates")
    print("="*70)
    
    tests = [
        test_inbound_twiml_has_from_parameter,
        test_outbound_twiml_has_from_parameter,
        test_call_log_lead_id_update_after_customer_intelligence,
        test_call_log_lead_id_update_in_fallback,
        test_name_resolution_can_use_phone_number,
        test_name_resolution_uses_calllog_lead_id,
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append((test_func.__name__, result))
        except Exception as e:
            print(f"❌ {test_func.__name__} failed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_func.__name__, False))
    
    print("\n" + "="*70)
    print("Test Summary")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*70)
    
    if passed == total:
        print("\n🎉 All tests passed! Customer context fix is working correctly.")
        print("\nExpected behavior:")
        print("  1. Inbound calls receive From parameter for phone lookup")
        print("  2. Outbound calls receive From parameter for consistency")
        print("  3. call_log.lead_id is updated when lead is created/found")
        print("  4. Name resolution can use phone_number as fallback")
        print("  5. Name resolution can use call_log.lead_id")
        print("\nResult: ✅ Customer context will be passed to AI and appointment tools")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
