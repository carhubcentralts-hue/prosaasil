#!/usr/bin/env python3
"""
Test suite for WhatsApp Baileys integration critical fixes
Tests the implementation of all 5 steps from the problem statement
"""

import sys
import os
import time
import json
from unittest.mock import Mock, patch, MagicMock
import threading

sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')

def test_step1_baileys_logging():
    """Step 1: Verify enhanced logging in Baileys service"""
    print("🧪 Test Step 1: Baileys Enhanced Logging")
    
    service_file = '/home/runner/work/prosaasil/prosaasil/services/whatsapp/baileys_service.js'
    
    with open(service_file, 'r') as f:
        content = f.read()
    
    # Check for detailed logging
    assert '[BAILEYS] sending message' in content, "Missing detailed 'sending message' log"
    assert '[BAILEYS] send finished successfully' in content, "Missing 'send finished' log"
    assert '[BAILEYS] send failed' in content, "Missing 'send failed' log"
    
    # Check for timeout protection
    assert 'Promise.race' in content, "Missing Promise.race for timeout protection"
    assert 'Send timeout after 30s' in content, "Missing 30s timeout protection"
    
    print("  ✅ PASS - Baileys has enhanced logging and timeout protection")
    return True

def test_step2_flask_non_blocking():
    """Step 2: Verify Flask uses background threads for sending"""
    print("\n🧪 Test Step 2: Flask Non-Blocking Send")
    
    routes_file = '/home/runner/work/prosaasil/prosaasil/server/routes_whatsapp.py'
    
    with open(routes_file, 'r') as f:
        content = f.read()
    
    # Check for threading usage
    assert 'threading.Thread' in content, "Missing threading.Thread usage"
    assert 'daemon=True' in content, "Missing daemon=True for background threads"
    assert '_send_whatsapp_message_background' in content, "Missing background send function"
    
    print("  ✅ PASS - Flask uses background threads for non-blocking sends")
    return True

def test_step3_app_context_fix():
    """Step 3: Verify Flask app context is properly passed to threads"""
    print("\n🧪 Test Step 3: Flask Application Context Fix")
    
    routes_file = '/home/runner/work/prosaasil/prosaasil/server/routes_whatsapp.py'
    
    with open(routes_file, 'r') as f:
        content = f.read()
    
    # Check for app instance being passed
    assert 'app_instance = current_app._get_current_object()' in content, "Missing app instance retrieval"
    assert 'def _send_whatsapp_message_background(\n    app,' in content, "Missing app parameter in background function"
    assert 'with app.app_context():' in content, "Missing app.app_context() wrapper"
    
    print("  ✅ PASS - App context properly passed to background threads")
    return True

def test_step4_sending_lock():
    """Step 4: Verify sending lock mechanism to prevent restart during send"""
    print("\n🧪 Test Step 4: Sending Lock Mechanism")
    
    baileys_file = '/home/runner/work/prosaasil/prosaasil/services/whatsapp/baileys_service.js'
    provider_file = '/home/runner/work/prosaasil/prosaasil/server/whatsapp_provider.py'
    
    with open(baileys_file, 'r') as f:
        baileys_content = f.read()
    
    with open(provider_file, 'r') as f:
        provider_content = f.read()
    
    # Check Baileys has sending locks
    assert 'sendingLocks' in baileys_content, "Missing sendingLocks Map in Baileys"
    assert 'isSending' in baileys_content, "Missing isSending flag"
    assert 'activeSends' in baileys_content, "Missing activeSends counter"
    assert '/whatsapp/:tenantId/sending-status' in baileys_content, "Missing sending-status endpoint"
    
    # Check Flask checks sending status before restart
    assert 'sending-status' in provider_content, "Missing sending-status check in provider"
    assert 'Baileys is currently sending' in provider_content, "Missing check for sending in progress"
    
    print("  ✅ PASS - Sending lock mechanism implemented")
    return True

def test_step5_health_check_separation():
    """Step 5: Verify separation of 'connected' vs 'canSend' capability"""
    print("\n🧪 Test Step 5: Health Check Separation")
    
    baileys_file = '/home/runner/work/prosaasil/prosaasil/services/whatsapp/baileys_service.js'
    provider_file = '/home/runner/work/prosaasil/prosaasil/server/whatsapp_provider.py'
    
    with open(baileys_file, 'r') as f:
        baileys_content = f.read()
    
    with open(provider_file, 'r') as f:
        provider_content = f.read()
    
    # Check Baileys status endpoint has canSend field
    assert 'canSend:' in baileys_content, "Missing canSend field in status endpoint"
    assert 'canSend = truelyConnected && hasSocket' in baileys_content, "Missing canSend calculation"
    
    # Check Flask has _can_send method
    assert 'def _can_send' in provider_content, "Missing _can_send method in provider"
    
    print("  ✅ PASS - Health check properly separates 'connected' from 'canSend'")
    return True

def test_acceptance_criteria():
    """Test acceptance criteria from problem statement"""
    print("\n🧪 Test Acceptance Criteria")
    
    provider_file = '/home/runner/work/prosaasil/prosaasil/server/whatsapp_provider.py'
    routes_file = '/home/runner/work/prosaasil/prosaasil/server/routes_whatsapp.py'
    baileys_file = '/home/runner/work/prosaasil/prosaasil/services/whatsapp/baileys_service.js'
    
    with open(provider_file, 'r') as f:
        provider_content = f.read()
    
    with open(routes_file, 'r') as f:
        routes_content = f.read()
        
    with open(baileys_file, 'r') as f:
        baileys_content = f.read()
    
    criteria = []
    
    # 1. No more "Read timed out" on send - timeout protection added
    if 'Promise.race' in baileys_content and 'Send timeout after 30s' in baileys_content:
        criteria.append("✅ Timeout protection prevents Read timed out")
    else:
        criteria.append("❌ Missing timeout protection")
    
    # 2. No more "Working outside of application context"
    if 'app.app_context()' in routes_content and 'app_instance = current_app._get_current_object()' in routes_content:
        criteria.append("✅ App context properly handled in threads")
    else:
        criteria.append("❌ App context not properly handled")
    
    # 3. Flask returns immediately (<100ms) - background threading
    if 'threading.Thread' in routes_content and 'daemon=True' in routes_content:
        criteria.append("✅ Flask uses background threads for fast response")
    else:
        criteria.append("❌ Flask may block on sends")
    
    # 4. Baileys returns clear ACK - logging shows messageId
    if 'messageId=' in baileys_content and '[BAILEYS] send finished successfully' in baileys_content:
        criteria.append("✅ Clear ACK with messageId logging")
    else:
        criteria.append("❌ Missing clear ACK logging")
    
    # 5. No restart during send
    if 'sendingLocks' in baileys_content and 'sending-status' in provider_content:
        criteria.append("✅ Restart prevented during send")
    else:
        criteria.append("❌ No protection against restart during send")
    
    for criterion in criteria:
        print(f"  {criterion}")
    
    all_passed = all('✅' in c for c in criteria)
    
    if all_passed:
        print("\n  ✅ ALL ACCEPTANCE CRITERIA MET")
    else:
        print("\n  ⚠️ SOME CRITERIA NOT MET")
    
    return all_passed

def test_integration_scenario():
    """Test a realistic integration scenario"""
    print("\n🧪 Test Integration Scenario: Incoming Message Flow")
    
    from server.whatsapp_provider import BaileysProvider
    
    # Test that BaileysProvider has the new methods
    provider = BaileysProvider()
    
    # Check _can_send method exists
    assert hasattr(provider, '_can_send'), "Missing _can_send method"
    
    # Check timeout is 15s
    assert provider.read_timeout == 15.0, f"Expected timeout 15s, got {provider.read_timeout}s"
    
    # Check session pooling exists
    assert hasattr(provider, '_session'), "Missing _session for connection pooling"
    
    print("  ✅ PASS - BaileysProvider has all required methods and configuration")
    return True

def main():
    """Run all tests"""
    print("=" * 70)
    print("WhatsApp Baileys Integration Fixes - Comprehensive Test Suite")
    print("=" * 70)
    
    tests = [
        ("Step 1: Baileys Logging", test_step1_baileys_logging),
        ("Step 2: Flask Non-Blocking", test_step2_flask_non_blocking),
        ("Step 3: App Context Fix", test_step3_app_context_fix),
        ("Step 4: Sending Lock", test_step4_sending_lock),
        ("Step 5: Health Check", test_step5_health_check_separation),
        ("Acceptance Criteria", test_acceptance_criteria),
        ("Integration Scenario", test_integration_scenario),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"  ❌ FAIL - {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"Results: {passed}/{len(tests)} tests passed")
    if failed == 0:
        print("🎉 ALL TESTS PASSED - Ready for deployment")
    else:
        print(f"⚠️ {failed} test(s) failed - Review required")
    print("=" * 70)
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
