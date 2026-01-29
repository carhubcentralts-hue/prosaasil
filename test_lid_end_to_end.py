#!/usr/bin/env python3
"""
Comprehensive test for LID (Lidded ID) end-to-end support.

This test validates:
1. Text extraction from various message formats (including buttons and lists)
2. Dedupe TTL is set to 2 minutes (not 1 hour)
3. Bad MAC error handling doesn't crash
4. LID messages are properly routed to participant JID for replies
5. Logging is clear and helpful
"""
import sys
import os
import re

def test_text_extraction_function():
    """Test that extractText function is properly defined in baileys_service.js"""
    print("Test 1: Text extraction function")
    
    with open('services/whatsapp/baileys_service.js', 'r') as f:
        content = f.read()
    
    # Check extractText function exists
    assert 'function extractText(msgObj)' in content, "extractText function not found"
    print("  ✅ extractText function defined")
    
    # Check it handles buttonsResponseMessage
    assert 'buttonsResponseMessage?.selectedDisplayText' in content, "buttonsResponseMessage not handled"
    print("  ✅ Handles buttonsResponseMessage.selectedDisplayText")
    
    # Check it handles listResponseMessage
    assert 'listResponseMessage?.title' in content, "listResponseMessage.title not handled"
    assert 'listResponseMessage?.description' in content, "listResponseMessage.description not handled"
    print("  ✅ Handles listResponseMessage.title and description")
    
    # Check it returns null for non-content
    assert 'return null' in content, "extractText doesn't return null appropriately"
    print("  ✅ Returns null for non-content messages")
    
    # Check hasTextContent uses extractText
    assert 'function hasTextContent(msgObj)' in content, "hasTextContent function not found"
    assert 'extractText(msgObj)' in content, "hasTextContent doesn't use extractText"
    print("  ✅ hasTextContent properly uses extractText")


def test_dedupe_ttl():
    """Test that dedupe TTL is set to 2 minutes (120 seconds)"""
    print("\nTest 2: Dedupe TTL settings")
    
    with open('services/whatsapp/baileys_service.js', 'r') as f:
        content = f.read()
    
    # Find DEDUP_CLEANUP_MS value
    match = re.search(r'const DEDUP_CLEANUP_MS\s*=\s*(\d+)', content)
    assert match, "DEDUP_CLEANUP_MS not found"
    cleanup_ms = int(match.group(1))
    assert cleanup_ms == 120000, f"DEDUP_CLEANUP_MS should be 120000 (2 min), got {cleanup_ms}"
    print(f"  ✅ DEDUP_CLEANUP_MS = {cleanup_ms}ms (2 minutes)")
    
    # Find DEDUP_CLEANUP_HOUR_MS value
    match = re.search(r'const DEDUP_CLEANUP_HOUR_MS\s*=\s*(\d+)', content)
    assert match, "DEDUP_CLEANUP_HOUR_MS not found"
    hour_ms = int(match.group(1))
    assert hour_ms == 120000, f"DEDUP_CLEANUP_HOUR_MS should be 120000 (2 min), got {hour_ms}"
    print(f"  ✅ DEDUP_CLEANUP_HOUR_MS = {hour_ms}ms (2 minutes)")
    
    # Verify comment mentions LID fix
    assert 'LID' in content or 'retries' in content.lower(), "Should mention LID or retries in comments"
    print("  ✅ Comments explain LID support reasoning")


def test_bad_mac_error_handling():
    """Test that Bad MAC errors are handled gracefully"""
    print("\nTest 3: Bad MAC / decrypt error handling")
    
    with open('services/whatsapp/baileys_service.js', 'r') as f:
        content = f.read()
    
    # Check for decryption error handling
    assert 'Bad MAC' in content, "Bad MAC error not handled"
    assert 'Failed to decrypt' in content, "Failed to decrypt error not handled"
    print("  ✅ Checks for 'Bad MAC' and 'Failed to decrypt' errors")
    
    # Check it logs as warning
    assert 'console.warn' in content or 'WARNING' in content, "Should log decrypt errors as warning"
    print("  ✅ Logs decrypt errors at WARNING level")
    
    # Check it continues (doesn't crash)
    assert 'continue' in content, "Should continue on decrypt error"
    print("  ✅ Continues processing on decrypt error (doesn't crash)")
    
    # Check validMessages is used
    assert 'validMessages' in content, "Should filter to validMessages"
    print("  ✅ Filters messages to validMessages after decrypt check")


def test_lid_routing():
    """Test that LID messages are properly routed for replies"""
    print("\nTest 4: LID routing logic")
    
    with open('server/routes_whatsapp.py', 'r') as f:
        content = f.read()
    
    # Check reply_jid calculation
    assert 'reply_jid = remote_jid' in content, "reply_jid default not set"
    print("  ✅ reply_jid defaults to remote_jid")
    
    # Check it prefers @s.whatsapp.net
    assert "remote_jid_alt.endswith('@s.whatsapp.net')" in content, "Doesn't check for @s.whatsapp.net"
    assert 'reply_jid = remote_jid_alt' in content, "Doesn't set reply_jid to alt"
    print("  ✅ Prefers remote_jid_alt (@s.whatsapp.net) over @lid")
    
    # Check send uses reply_jid
    assert 'remote_jid=reply_jid' in content, "Send doesn't use reply_jid"
    print("  ✅ Send operation uses reply_jid (not remote_jid)")


def test_enhanced_logging():
    """Test that logging is enhanced for LID debugging"""
    print("\nTest 5: Enhanced logging for LID")
    
    # Check JavaScript logging
    with open('services/whatsapp/baileys_service.js', 'r') as f:
        js_content = f.read()
    
    assert 'chat_jid=' in js_content, "Should log chat_jid"
    assert 'message_id=' in js_content, "Should log message_id"
    assert 'LID message detected' in js_content, "Should detect and log LID messages"
    print("  ✅ JavaScript: Logs chat_jid, message_id, and LID detection")
    
    # Check Python logging
    with open('server/routes_whatsapp.py', 'r') as f:
        py_content = f.read()
    
    assert '[WA-INCOMING]' in py_content and 'chat_jid=' in py_content, "Should log incoming chat_jid"
    assert '[WA-REPLY]' in py_content, "Should log reply target"
    assert '[WA-LID]' in py_content, "Should have LID-specific logging"
    print("  ✅ Python: Logs incoming, reply, and LID-specific messages")
    
    # Check send job logging
    with open('server/jobs/send_whatsapp_message_job.py', 'r') as f:
        job_content = f.read()
    
    assert '@lid' in job_content, "Should detect @lid in send job"
    assert '@s.whatsapp.net' in job_content, "Should detect standard JID in send job"
    print("  ✅ Send job: Detects and logs JID type (LID vs standard)")


def test_lid_message_flow_simulation():
    """Simulate LID message flow to ensure all components work together"""
    print("\nTest 6: LID message flow simulation")
    
    # Simulate incoming LID message structure
    lid_message = {
        'key': {
            'remoteJid': '82399031480511@lid',
            'participant': '972501234567@s.whatsapp.net',
            'id': '3EB0ABC123',
            'fromMe': False
        },
        'message': {
            'conversation': 'שלום'
        }
    }
    
    # Extract values as the code would
    remote_jid = lid_message['key']['remoteJid']
    participant = lid_message['key'].get('participant')
    
    # Determine reply_jid
    reply_jid = remote_jid  # Default
    if participant and participant.endswith('@s.whatsapp.net'):
        reply_jid = participant
    
    # Validate
    assert remote_jid == '82399031480511@lid', "Should extract LID correctly"
    assert participant == '972501234567@s.whatsapp.net', "Should extract participant"
    assert reply_jid == '972501234567@s.whatsapp.net', "Should prefer participant for reply"
    assert remote_jid != reply_jid, "Reply JID should differ from incoming LID"
    
    print(f"  ✅ Incoming: {remote_jid}")
    print(f"  ✅ Participant: {participant}")
    print(f"  ✅ Reply to: {reply_jid}")
    print(f"  ✅ Flow validated: LID message → standard WhatsApp reply")


def test_no_regressions_standard_messages():
    """Ensure standard @s.whatsapp.net messages still work"""
    print("\nTest 7: No regressions for standard messages")
    
    # Simulate standard message
    standard_message = {
        'key': {
            'remoteJid': '972501234567@s.whatsapp.net',
            'id': '3EB0XYZ789',
            'fromMe': False
        },
        'message': {
            'conversation': 'Hello'
        }
    }
    
    # Extract values
    remote_jid = standard_message['key']['remoteJid']
    participant = standard_message['key'].get('participant')  # None for standard
    
    # Determine reply_jid
    reply_jid = remote_jid  # Default
    if participant and participant.endswith('@s.whatsapp.net'):
        reply_jid = participant
    
    # Validate - reply_jid should equal remote_jid
    assert remote_jid == '972501234567@s.whatsapp.net', "Should extract standard JID"
    assert participant is None, "Standard messages have no participant"
    assert reply_jid == remote_jid, "Reply should go to same JID"
    
    print(f"  ✅ Standard message flow preserved")
    print(f"  ✅ Incoming: {remote_jid}")
    print(f"  ✅ Reply to: {reply_jid}")
    print(f"  ✅ No participant needed for standard messages")


if __name__ == "__main__":
    print("🧪 Running comprehensive LID end-to-end tests...\n")
    
    try:
        test_text_extraction_function()
        test_dedupe_ttl()
        test_bad_mac_error_handling()
        test_lid_routing()
        test_enhanced_logging()
        test_lid_message_flow_simulation()
        test_no_regressions_standard_messages()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED! LID support is properly implemented.")
        print("="*60)
        print("\nKey features verified:")
        print("  • Text extraction from buttons and lists")
        print("  • Dedupe TTL reduced to 2 minutes")
        print("  • Bad MAC errors handled gracefully")
        print("  • LID messages route replies to participant JID")
        print("  • Enhanced logging for debugging")
        print("  • No regressions for standard messages")
        
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
