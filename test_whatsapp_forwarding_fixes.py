#!/usr/bin/env python3
"""
Comprehensive test for WhatsApp message forwarding fixes.
Validates all critical fixes made to baileys_service.js.
"""

import sys
import os
import re

sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')

def read_service_file():
    """Read baileys_service.js file"""
    service_file = '/home/runner/work/prosaasil/prosaasil/services/whatsapp/baileys_service.js'
    with open(service_file, 'r') as f:
        return f.read()

def test_fix_1_webhook_payload_not_nested():
    """Test that webhook payload is sent directly, not nested"""
    print("🧪 Test Fix #1: Webhook payload structure (not double-wrapped)\n")
    
    content = read_service_file()
    
    # Find the main message handler (not retry function)
    # Look for the section with filteredPayload definition
    filtered_payload_idx = content.find('const filteredPayload = {')
    if filtered_payload_idx == -1:
        print("❌ FAIL - Could not find filteredPayload definition")
        return False
    
    # Find the webhook call after filteredPayload
    webhook_section = content[filtered_payload_idx:filtered_payload_idx + 1000]
    
    # Check that we're NOT wrapping payload in another object
    if '{ tenantId, payload: filteredPayload }' in webhook_section:
        print("❌ FAIL - Payload is still double-wrapped")
        print("   Found: { tenantId, payload: filteredPayload }")
        print("   This will cause Flask to receive nested structure")
        return False
    
    # Check for direct payload send
    if 'axios.post(`${FLASK_BASE_URL}/api/whatsapp/webhook/incoming`,\n            filteredPayload,' in webhook_section:
        print("✅ PASS - Payload sent directly (not nested)")
        print("   Flask will receive correct structure")
        return True
    
    print("⚠️  WARNING - Could not verify payload structure clearly")
    # Do a secondary check
    if 'filteredPayload,' in webhook_section and '{ tenantId, payload:' not in webhook_section:
        print("✅ PASS - Payload appears to be sent directly")
        return True
    
    return False

def test_fix_3_dedup_cleanup_timing():
    """Test that dedup cleanup is longer than max retry time"""
    print("\n🧪 Test Fix #3: Deduplication cleanup timing\n")
    
    content = read_service_file()
    
    # Find DEDUP_CLEANUP_MS constant
    match = re.search(r'const DEDUP_CLEANUP_MS = (\d+);', content)
    if not match:
        print("❌ FAIL - Could not find DEDUP_CLEANUP_MS constant")
        return False
    
    dedup_cleanup_ms = int(match.group(1))
    
    # Find RETRY_BACKOFF_MS
    match = re.search(r'const RETRY_BACKOFF_MS = \[([\d,\s]+)\];', content)
    if not match:
        print("❌ FAIL - Could not find RETRY_BACKOFF_MS")
        return False
    
    backoff_values = [int(x.strip()) for x in match.group(1).split(',')]
    max_retry_time = sum(backoff_values)
    
    print(f"   Max retry time: {max_retry_time}ms ({max_retry_time/1000}s)")
    print(f"   Dedup cleanup time: {dedup_cleanup_ms}ms ({dedup_cleanup_ms/1000}s)")
    
    if dedup_cleanup_ms > max_retry_time:
        print("✅ PASS - Dedup cleanup time is longer than max retry time")
        print("   Retries will not be incorrectly marked as duplicates")
        return True
    else:
        print("❌ FAIL - Dedup cleanup time is too short")
        print(f"   Should be > {max_retry_time}ms, got {dedup_cleanup_ms}ms")
        return False

def test_fix_4_429_retry_logic():
    """Test that 429 (rate limit) errors trigger retry"""
    print("\n🧪 Test Fix #4: 429 rate limit error retry\n")
    
    content = read_service_file()
    
    # Find the section where we check for retryable errors
    # Look for the specific retry condition
    if 'e.response.status === 429' in content or 'e.response.status >= 500 || e.response.status === 429' in content:
        print("✅ PASS - 429 status code triggers retry")
        print("   Rate limited requests will be retried")
        return True
    else:
        print("❌ FAIL - 429 status code not found in retry logic")
        return False

def test_fix_5_dedup_key_format():
    """Test that dedup key format is consistent (includes remoteJid)"""
    print("\n🧪 Test Fix #5: Consistent dedup key format\n")
    
    content = read_service_file()
    
    # Find retry function
    retry_func_start = content.find('async function retryWebhookDelivery(item)')
    if retry_func_start == -1:
        print("❌ FAIL - Could not find retryWebhookDelivery function")
        return False
    
    retry_func = content[retry_func_start:retry_func_start + 2000]
    
    # Check that remoteJid is extracted from item
    if 'const { tenantId, messageId, remoteJid, payload, attempts } = item;' not in retry_func:
        print("❌ FAIL - remoteJid not extracted from retry item")
        return False
    
    # Check that dedup key uses correct format
    if '${tenantId}:${remoteJid}:${messageId}' in retry_func:
        print("✅ PASS - Dedup key format is consistent")
        print("   Format: tenantId:remoteJid:messageId")
        return True
    else:
        print("❌ FAIL - Dedup key format inconsistent in retry function")
        return False

def test_fix_6_retry_payload_structure():
    """Test that retry queue stores remoteJid"""
    print("\n🧪 Test Fix #6: Retry queue payload structure\n")
    
    content = read_service_file()
    
    # Find the messageQueue.push section
    queue_push_match = re.search(
        r'messageQueue\.push\(\{[\s\S]*?\}\);',
        content
    )
    
    if not queue_push_match:
        print("❌ FAIL - Could not find messageQueue.push")
        return False
    
    queue_push = queue_push_match.group(0)
    
    if 'remoteJid:' in queue_push:
        print("✅ PASS - remoteJid is stored in retry queue")
        print("   Retry messages can reconstruct correct dedup key")
        return True
    else:
        print("❌ FAIL - remoteJid not stored in retry queue")
        return False

def test_fix_8_timeout_increased():
    """Test that webhook timeout is increased to 30s"""
    print("\n🧪 Test Fix #8: Webhook timeout increased\n")
    
    content = read_service_file()
    
    # Find the filteredPayload section (main message handler)
    filtered_payload_idx = content.find('const filteredPayload = {')
    if filtered_payload_idx == -1:
        print("❌ FAIL - Could not find filteredPayload")
        return False
        
    # Get the webhook call after filteredPayload
    webhook_section = content[filtered_payload_idx:filtered_payload_idx + 1000]
    
    # Check for 30 second timeout in main handler
    if 'timeout: 30000' in webhook_section:
        print("✅ PASS - Webhook timeout increased to 30s")
        print("   Allows Flask more time to process messages")
        return True
    elif 'timeout: 15000' in webhook_section:
        print("❌ FAIL - Timeout still at 15s (too short)")
        return False
    else:
        print("⚠️  WARNING - Could not find timeout value in main handler")
        return False

def test_messagecontextinfo_not_filtered():
    """Test that messageContextInfo is not in filter"""
    print("\n🧪 Test: messageContextInfo not filtered\n")
    
    content = read_service_file()
    
    # Find extractText function
    extract_func_start = content.find('function extractText(msgObj) {')
    if extract_func_start == -1:
        print("❌ FAIL - Could not find extractText function")
        return False
    
    extract_func = content[extract_func_start:extract_func_start + 500]
    
    # Find the filter condition
    filter_start = extract_func.find('if (msgObj.pollUpdateMessage')
    filter_end = extract_func.find('return null;  // Ignore silently')
    
    if filter_start == -1 or filter_end == -1:
        print("❌ FAIL - Could not find filter condition")
        return False
    
    filter_condition = extract_func[filter_start:filter_end]
    
    if 'messageContextInfo' in filter_condition:
        print("❌ FAIL - messageContextInfo is still in filter")
        return False
    else:
        print("✅ PASS - messageContextInfo not in filter")
        print("   Messages with messageContextInfo will be processed")
        return True

def main():
    print("=" * 70)
    print("WhatsApp Message Forwarding - Comprehensive Fix Validation")
    print("=" * 70)
    print()
    
    tests = [
        test_messagecontextinfo_not_filtered,
        test_fix_1_webhook_payload_not_nested,
        test_fix_3_dedup_cleanup_timing,
        test_fix_4_429_retry_logic,
        test_fix_5_dedup_key_format,
        test_fix_6_retry_payload_structure,
        test_fix_8_timeout_increased,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    if all(results):
        print("\n🎉 ALL TESTS PASSED")
        print("\n✅ FIXES VERIFIED:")
        print("   1. messageContextInfo filter removed")
        print("   2. Webhook payload sent directly (not nested)")
        print("   3. Dedup cleanup timing fixed")
        print("   4. 429 rate limit errors retry correctly")
        print("   5. Dedup key format consistent everywhere")
        print("   6. Retry queue stores remoteJid")
        print("   7. Webhook timeout increased to 30s")
        print("\n🚀 Messages should now flow correctly from WhatsApp → Baileys → Flask → Agent Kit")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        print("Review the output above for details")
        return 1

if __name__ == '__main__':
    sys.exit(main())
