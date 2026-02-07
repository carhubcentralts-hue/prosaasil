#!/usr/bin/env python3
"""
Manual test script for webhook leads endpoint

This script can be used to manually test the webhook endpoint with various payloads.
Run this after starting the server to verify the fixes work correctly.

Usage:
    python tests/manual_test_webhook_leads.py

Note: This is a manual test script, not an automated test.
"""
import json


def print_test_case(name, payload, expected_status, notes=""):
    """Print a test case for manual testing"""
    print(f"\n{'='*80}")
    print(f"TEST CASE: {name}")
    print(f"{'='*80}")
    print(f"\nPayload:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\nExpected Status: {expected_status}")
    if notes:
        print(f"Notes: {notes}")
    print(f"\ncURL Command:")
    print(f"curl -X POST http://localhost:5000/api/webhook/leads/{{webhook_id}} \\")
    print(f"  -H 'X-Webhook-Secret: {{your_secret}}' \\")
    print(f"  -H 'Content-Type: application/json; charset=utf-8' \\")
    print(f"  -d '{json.dumps(payload, ensure_ascii=False)}'")
    print()


def main():
    print("=" * 80)
    print("WEBHOOK LEADS ENDPOINT - MANUAL TEST CASES")
    print("=" * 80)
    print("\nThese test cases verify the fixes made to the webhook leads endpoint:")
    print("1. CSRF exemption and OPTIONS support")
    print("2. Proper error responses with 'ok' field")
    print("3. Hebrew/UTF-8 content support")
    print("4. URL path using singular 'webhook' not 'webhooks'")
    
    # Test 1: Valid payload with phone
    print_test_case(
        "Valid Lead - Phone Only",
        {
            "name": "ישראל ישראלי",
            "phone": "+972501234567"
        },
        "200 OK",
        "Should create new lead successfully"
    )
    
    # Test 2: Valid payload with email
    print_test_case(
        "Valid Lead - Email Only",
        {
            "name": "שרה כהן",
            "email": "sara@example.com"
        },
        "200 OK",
        "Should create new lead successfully"
    )
    
    # Test 3: Valid payload with both phone and email
    print_test_case(
        "Valid Lead - Phone and Email",
        {
            "name": "דוד לוי",
            "phone": "0501234567",
            "email": "david@example.com",
            "city": "תל אביב",
            "notes": "מעוניין בשירות חשמלאי"
        },
        "200 OK",
        "Should create new lead with all fields"
    )
    
    # Test 4: Missing contact identifier
    print_test_case(
        "Invalid - Missing Contact Identifier",
        {
            "name": "יוסי אברהם",
            "city": "ירושלים"
        },
        "400 Bad Request",
        "Should return error with 'ok': false and 'error': 'phone_or_email_required'"
    )
    
    # Test 5: Phone variant field names
    print_test_case(
        "Valid Lead - Phone Variant (mobile)",
        {
            "name": "מיכל שלום",
            "mobile": "+972521234567"
        },
        "200 OK",
        "Should recognize 'mobile' as phone field"
    )
    
    # Test 6: Email variant field names
    print_test_case(
        "Valid Lead - Email Variant (email_address)",
        {
            "name": "רונית גולן",
            "email_address": "ronit@example.com"
        },
        "200 OK",
        "Should recognize 'email_address' as email field"
    )
    
    # Test 7: OPTIONS request (CORS preflight)
    print(f"\n{'='*80}")
    print(f"TEST CASE: CORS Preflight (OPTIONS)")
    print(f"{'='*80}")
    print(f"\ncURL Command:")
    print(f"curl -X OPTIONS http://localhost:5000/api/webhook/leads/{{webhook_id}} \\")
    print(f"  -H 'Access-Control-Request-Method: POST' \\")
    print(f"  -H 'Access-Control-Request-Headers: Content-Type, X-Webhook-Secret' \\")
    print(f"  -v")
    print(f"\nExpected Status: 200 OK")
    print(f"Expected Headers:")
    print(f"  - Access-Control-Allow-Origin: *")
    print(f"  - Access-Control-Allow-Methods: POST, OPTIONS")
    print(f"  - Access-Control-Allow-Headers: Content-Type, X-Webhook-Secret")
    print()
    
    # Test 8: Invalid secret
    print(f"\n{'='*80}")
    print(f"TEST CASE: Invalid Secret")
    print(f"{'='*80}")
    print(f"\ncURL Command:")
    print(f"curl -X POST http://localhost:5000/api/webhook/leads/{{webhook_id}} \\")
    print(f"  -H 'X-Webhook-Secret: invalid_secret' \\")
    print(f"  -H 'Content-Type: application/json' \\")
    print(f"  -d '{{\"name\": \"Test\", \"phone\": \"+972501234567\"}}'")
    print(f"\nExpected Status: 401 Unauthorized")
    print(f"Expected Response: {{\"ok\": false, \"error\": \"invalid_secret\"}}")
    print()
    
    print("=" * 80)
    print("SETUP INSTRUCTIONS")
    print("=" * 80)
    print("\n1. Start the server:")
    print("   python run_dev_server.py")
    print("\n2. Create a webhook via the UI:")
    print("   - Go to Settings → Integrations")
    print("   - Create a new webhook")
    print("   - Copy the webhook ID and secret")
    print("\n3. Replace {webhook_id} and {your_secret} in the commands above")
    print("\n4. Run the cURL commands to test")
    print("\n5. Expected responses:")
    print("   - Success: {\"ok\": true, \"lead_id\": 123, \"status_id\": 9}")
    print("   - Error: {\"ok\": false, \"error\": \"phone_or_email_required\"}")
    print("\n6. Verify in UI that leads are created correctly")
    print()
    
    print("=" * 80)
    print("KEY FIXES TO VERIFY")
    print("=" * 80)
    print("\n✅ URL uses /api/webhook/leads/ (singular) not /api/webhooks/leads/")
    print("✅ OPTIONS method returns 200 OK with CORS headers")
    print("✅ Success responses use 'ok': true with status_id field")
    print("✅ Error responses use 'ok': false")
    print("✅ Missing contact identifier returns error: 'phone_or_email_required'")
    print("✅ Hebrew content works correctly in all fields")
    print("✅ Content-Type includes charset=utf-8")
    print("✅ Webhook creates lead with target status_id from webhook config")
    print("✅ Falls back to business default status if target status missing/deleted")
    print()


if __name__ == "__main__":
    main()
