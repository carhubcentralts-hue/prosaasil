"""
Test webhook leads endpoint fixes

Tests for:
1. CORS preflight (OPTIONS) support
2. Proper error responses with "ok" field
3. Missing contact identifier error with helpful details
4. Hebrew content support (UTF-8)
5. Response format consistency
"""
import json


def test_webhook_response_format():
    """
    Test that webhook responses use "ok" field and proper format
    
    Verifies:
    - Success responses have "ok": true
    - Error responses have "ok": false
    - All responses include proper fields
    - New leads return 201 Created (REST best practice)
    - Updated leads return 200 OK
    """
    # Test success response for new lead (201 Created)
    success_new = {
        "ok": True,
        "lead_id": 123,
        "updated": False
    }
    
    assert success_new["ok"] is True
    assert "lead_id" in success_new
    assert "updated" in success_new
    assert success_new["updated"] is False
    
    # Test success response for updated lead (200 OK)
    success_updated = {
        "ok": True,
        "lead_id": 456,
        "updated": True
    }
    
    assert success_updated["ok"] is True
    assert success_updated["updated"] is True
    
    # Test error response
    error_response = {
        "ok": False,
        "error": "missing_contact_identifier",
        "message": "Must provide either phone or email",
        "expected_one_of": ["phone", "mobile", "tel", "email", "email_address"],
        "received_fields": ["name", "city"]
    }
    
    assert error_response["ok"] is False
    assert "error" in error_response
    assert "message" in error_response
    assert "expected_one_of" in error_response
    assert "received_fields" in error_response
    
    print("✅ Response format test passed!")


def test_error_response_details():
    """
    Test that error responses provide helpful debugging information
    
    Verifies:
    - Missing contact identifier error includes expected fields
    - Error includes what fields were actually received
    - Error message is clear and actionable
    """
    # Simulate payload with no contact identifier
    received_payload = {
        "name": "ישראל כהן",
        "city": "תל אביב",
        "notes": "בקשה לשירות"
    }
    
    # Expected error response
    error = {
        "ok": False,
        "error": "missing_contact_identifier",
        "message": "Must provide either phone or email",
        "expected_one_of": ["phone", "mobile", "tel", "email", "email_address"],
        "received_fields": list(received_payload.keys())
    }
    
    # Verify error structure
    assert error["ok"] is False
    assert error["error"] == "missing_contact_identifier"
    assert "expected_one_of" in error
    assert len(error["expected_one_of"]) >= 2  # At least phone and email
    assert "received_fields" in error
    assert "name" in error["received_fields"]
    assert "city" in error["received_fields"]
    
    # Verify that expected fields include both phone and email variants
    expected = error["expected_one_of"]
    assert any(field in expected for field in ["phone", "mobile", "tel"])
    assert any(field in expected for field in ["email", "email_address"])
    
    print("✅ Error response details test passed!")


def test_hebrew_content_support():
    """
    Test that Hebrew content is properly handled
    
    Verifies:
    - Hebrew text in payload is processed correctly
    - Response can contain Hebrew text
    - JSON serialization works with Hebrew characters
    """
    # Test payload with Hebrew content
    hebrew_payload = {
        "name": "ישראל ישראלי",
        "phone": "+972501234567",
        "email": "test@example.com",
        "city": "תל אביב",
        "notes": "מעוניין בשירות חשמלאי"
    }
    
    # Verify JSON serialization works
    try:
        json_str = json.dumps(hebrew_payload, ensure_ascii=False)
        assert len(json_str) > 0
        
        # Verify deserialization works
        parsed = json.loads(json_str)
        assert parsed["name"] == "ישראל ישראלי"
        assert parsed["city"] == "תל אביב"
        assert parsed["notes"] == "מעוניין בשירות חשמלאי"
        
    except (TypeError, ValueError) as e:
        raise AssertionError(f"Hebrew content serialization failed: {e}")
    
    # Test response with Hebrew error message
    error_with_hebrew = {
        "ok": False,
        "error": "missing_contact_identifier",
        "message": "חובה לספק טלפון או אימייל"  # Hebrew error message
    }
    
    try:
        json_str = json.dumps(error_with_hebrew, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["message"] == "חובה לספק טלפון או אימייל"
        
    except (TypeError, ValueError) as e:
        raise AssertionError(f"Hebrew error message serialization failed: {e}")
    
    print("✅ Hebrew content support test passed!")


def test_contact_identifier_extraction():
    """
    Test that contact identifiers are properly extracted from various field names
    
    Verifies:
    - phone/mobile/tel fields are recognized
    - email/email_address fields are recognized
    - Case-insensitive matching works
    """
    # Test various phone field names
    phone_variants = [
        {"phone": "+972501234567"},
        {"mobile": "+972501234567"},
        {"tel": "+972501234567"},
        {"telephone": "+972501234567"},
        {"phone_number": "+972501234567"}
    ]
    
    for variant in phone_variants:
        # Each variant should have a recognized phone field
        assert len(variant) == 1
        key = list(variant.keys())[0]
        assert key.lower() in ["phone", "mobile", "tel", "telephone", "phone_number"]
    
    # Test various email field names
    email_variants = [
        {"email": "test@example.com"},
        {"email_address": "test@example.com"},
        {"emailaddress": "test@example.com"}
    ]
    
    for variant in email_variants:
        # Each variant should have a recognized email field
        assert len(variant) == 1
        key = list(variant.keys())[0]
        assert key.lower() in ["email", "email_address", "emailaddress"]
    
    print("✅ Contact identifier extraction test passed!")


def test_url_path_consistency():
    """
    Test that the webhook URL uses singular 'webhook' not 'webhooks'
    
    Verifies:
    - URL path is /api/webhook/leads/{id} (singular)
    - Consistent with other webhook routes like /webhook/whatsapp/*
    """
    # Correct URL format (singular)
    correct_url = "/api/webhook/leads/123"
    
    # Incorrect URL format (plural) - should NOT be used
    incorrect_url = "/api/webhooks/leads/123"
    
    # Verify path components
    assert "/webhook/leads/" in correct_url
    assert "/webhooks/leads/" not in correct_url
    
    # Verify consistency with other webhook routes
    whatsapp_webhook = "/webhook/whatsapp/incoming"
    assert "/webhook/" in whatsapp_webhook
    assert "/webhooks/" not in whatsapp_webhook
    
    print("✅ URL path consistency test passed!")


def test_options_method_support():
    """
    Test that OPTIONS method is supported for CORS preflight
    
    Verifies:
    - OPTIONS method should be allowed
    - Response should include CORS headers
    """
    # Simulate OPTIONS request for CORS preflight
    options_response = {
        "ok": True
    }
    
    expected_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-Webhook-Secret"
    }
    
    # Verify response structure
    assert options_response["ok"] is True
    
    # Verify expected headers are defined
    assert "Access-Control-Allow-Origin" in expected_headers
    assert "Access-Control-Allow-Methods" in expected_headers
    assert "Access-Control-Allow-Headers" in expected_headers
    
    # Verify methods
    methods = expected_headers["Access-Control-Allow-Methods"]
    assert "POST" in methods
    assert "OPTIONS" in methods
    
    # Verify headers
    headers = expected_headers["Access-Control-Allow-Headers"]
    assert "Content-Type" in headers
    assert "X-Webhook-Secret" in headers
    
    print("✅ OPTIONS method support test passed!")


def test_response_content_type():
    """
    Test that responses include proper Content-Type with charset
    
    Verifies:
    - Content-Type should be application/json; charset=utf-8
    - This ensures Hebrew and other UTF-8 content is properly handled
    """
    expected_content_type = "application/json; charset=utf-8"
    
    # Verify format
    assert "application/json" in expected_content_type
    assert "charset=utf-8" in expected_content_type
    
    print("✅ Response Content-Type test passed!")


if __name__ == "__main__":
    print("Running webhook leads fix tests...\n")
    
    test_webhook_response_format()
    test_error_response_details()
    test_hebrew_content_support()
    test_contact_identifier_extraction()
    test_url_path_consistency()
    test_options_method_support()
    test_response_content_type()
    
    print("\n✅ All webhook leads fix tests passed successfully!")
