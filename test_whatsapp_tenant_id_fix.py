#!/usr/bin/env python3
"""
Test for WhatsApp webhook tenantId fix.

This test ensures that:
1. The baileys_service.js sends tenantId in the webhook payload
2. The webhook payload structure matches Flask's expectations
"""
import re


def test_webhook_payload_structure():
    """Test that webhookPayload includes tenantId"""
    print("Test 1: Webhook payload structure")
    
    with open('services/whatsapp/baileys_service.js', 'r') as f:
        content = f.read()
    
    # Check that webhookPayload is created with tenantId
    assert 'const webhookPayload' in content, "webhookPayload not found"
    print("  ✅ webhookPayload is created")
    
    # Check that webhookPayload includes tenantId
    # Look for the pattern: const webhookPayload = { tenantId, ...
    webhook_pattern = r'const webhookPayload\s*=\s*\{\s*tenantId'
    assert re.search(webhook_pattern, content), "webhookPayload doesn't include tenantId"
    print("  ✅ webhookPayload includes tenantId field")
    
    # Check that webhookPayload includes payload field
    webhook_pattern_full = r'const webhookPayload\s*=\s*\{[^}]*payload:\s*filteredPayload'
    assert re.search(webhook_pattern_full, content), "webhookPayload doesn't include payload field"
    print("  ✅ webhookPayload includes payload: filteredPayload")
    
    # Check that webhookPayload is used in axios.post
    assert 'axios.post(`${FLASK_BASE_URL}/api/whatsapp/webhook/incoming`,\n            webhookPayload,' in content, \
        "webhookPayload not used in axios.post call"
    print("  ✅ webhookPayload is sent to Flask")


def test_queue_payload_structure():
    """Test that queued messages also include tenantId"""
    print("\nTest 2: Queue payload structure")
    
    with open('services/whatsapp/baileys_service.js', 'r') as f:
        content = f.read()
    
    # Check that queued messages include tenantId in their payload
    queue_pattern = r'payload:\s*\{\s*tenantId,\s*payload:\s*\{'
    assert re.search(queue_pattern, content), "Queued message payload doesn't include tenantId"
    print("  ✅ Queued messages include tenantId in payload")
    
    # Verify the comment explains the fix
    assert '🔥 FIX: Include tenantId' in content or 'Use correct webhook structure' in content, \
        "Missing comment explaining tenantId fix"
    print("  ✅ Code includes explanatory comment")


def test_flask_endpoint_expectation():
    """Test that Flask endpoint expects tenantId"""
    print("\nTest 3: Flask endpoint expectation")
    
    with open('server/routes_whatsapp.py', 'r') as f:
        content = f.read()
    
    # Check that Flask reads tenantId
    assert "tenant_id = data.get('tenantId')" in content, "Flask doesn't read tenantId"
    print("  ✅ Flask reads tenantId from payload")
    
    # Check that Flask checks for missing tenantId
    assert "missing_tenant_id" in content, "Flask doesn't check for missing tenantId"
    print("  ✅ Flask validates tenantId presence")
    
    # Check that Flask reads payload.messages
    assert "payload = data.get('payload', {})" in content, "Flask doesn't read nested payload"
    assert "messages = payload.get('messages', [])" in content, "Flask doesn't read messages from payload"
    print("  ✅ Flask reads messages from nested payload structure")


if __name__ == "__main__":
    print("🧪 Running WhatsApp tenantId fix tests...\n")
    
    try:
        test_webhook_payload_structure()
        test_queue_payload_structure()
        test_flask_endpoint_expectation()
        
        print("\n✅ All tests passed! The tenantId fix is properly implemented.")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
