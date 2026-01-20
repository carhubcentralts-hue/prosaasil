"""
Test Gmail Sync Resilience Fixes
Tests for NUL character sanitization and error handling
"""

import pytest
from server.services.gmail_sync_service import sanitize_for_postgres


def test_sanitize_simple_string():
    """Test sanitization of simple strings with NUL characters"""
    # String with NUL character
    input_str = "Hello\x00World"
    result = sanitize_for_postgres(input_str)
    assert result == "HelloWorld"
    assert "\x00" not in result
    
    # String without NUL character
    input_str = "Hello World"
    result = sanitize_for_postgres(input_str)
    assert result == "Hello World"


def test_sanitize_dict():
    """Test sanitization of dictionaries with NUL characters"""
    input_dict = {
        "name": "John\x00Doe",
        "email": "john@example.com",
        "data": {
            "nested": "value\x00with\x00nul"
        }
    }
    
    result = sanitize_for_postgres(input_dict)
    
    assert result["name"] == "JohnDoe"
    assert result["email"] == "john@example.com"
    assert result["data"]["nested"] == "valuewithnul"
    assert "\x00" not in str(result)


def test_sanitize_list():
    """Test sanitization of lists with NUL characters"""
    input_list = [
        "item1\x00",
        "item2",
        {"key": "value\x00"}
    ]
    
    result = sanitize_for_postgres(input_list)
    
    assert result[0] == "item1"
    assert result[1] == "item2"
    assert result[2]["key"] == "value"
    assert "\x00" not in str(result)


def test_sanitize_complex_json():
    """Test sanitization of complex JSON-like structure (like raw_extraction_json)"""
    input_data = {
        "metadata": {
            "subject": "Receipt\x00from vendor",
            "from_email": "vendor@example.com",
            "attachments": [
                {
                    "filename": "receipt\x00.pdf",
                    "size": 1024
                }
            ]
        },
        "extracted": {
            "vendor_name": "Vendor\x00Inc",
            "amount": 100.50,
            "currency": "USD"
        },
        "pdf_text_preview": "Total: $100.50\x00\x00End"
    }
    
    result = sanitize_for_postgres(input_data)
    
    # Check all NUL characters are removed
    assert result["metadata"]["subject"] == "Receiptfrom vendor"
    assert result["metadata"]["attachments"][0]["filename"] == "receipt.pdf"
    assert result["extracted"]["vendor_name"] == "VendorInc"
    assert result["pdf_text_preview"] == "Total: $100.50End"
    
    # Check numbers are preserved
    assert result["extracted"]["amount"] == 100.50
    assert result["metadata"]["attachments"][0]["size"] == 1024
    
    # Verify no NUL characters remain
    assert "\x00" not in str(result)


def test_sanitize_replacement_character():
    """Test removal of replacement character \ufffd"""
    input_str = "Hello\ufffdWorld"
    result = sanitize_for_postgres(input_str)
    assert result == "HelloWorld"
    assert "\ufffd" not in result


def test_sanitize_none_and_numbers():
    """Test that None and numbers pass through unchanged"""
    assert sanitize_for_postgres(None) is None
    assert sanitize_for_postgres(42) == 42
    assert sanitize_for_postgres(3.14) == 3.14
    assert sanitize_for_postgres(True) is True
    assert sanitize_for_postgres(False) is False


def test_sanitize_empty_structures():
    """Test sanitization of empty structures"""
    assert sanitize_for_postgres({}) == {}
    assert sanitize_for_postgres([]) == []
    assert sanitize_for_postgres("") == ""


def test_sanitize_tuple():
    """Test sanitization of tuples"""
    input_tuple = ("a\x00", "b", "c\x00")
    result = sanitize_for_postgres(input_tuple)
    
    # Should return tuple with sanitized values
    assert isinstance(result, tuple)
    assert result == ("a", "b", "c")
    assert "\x00" not in str(result)


def test_real_world_receipt_data():
    """Test with real-world receipt extraction data structure"""
    receipt_json = {
        "metadata": {
            "subject": "Your receipt from Amazon",
            "from": "auto-confirm@amazon.com",
            "date": "2024-01-15T10:30:00Z",
            "snippet": "Thank you for your order\x00",
            "attachments": [
                {
                    "id": "att123",
                    "filename": "invoice\x00.pdf",
                    "mime_type": "application/pdf",
                    "size": 45678
                }
            ],
            "has_attachment": True,
            "from_email": "auto-confirm@amazon.com",
            "from_domain": "amazon.com"
        },
        "extracted": {
            "vendor_name": "Amazon\x00",
            "amount": 29.99,
            "currency": "USD",
            "invoice_number": "INV-2024-001",
            "invoice_date": "2024-01-15"
        },
        "pdf_text_preview": "Order Total: $29.99\x00\nThank you for shopping with us\x00"
    }
    
    result = sanitize_for_postgres(receipt_json)
    
    # Verify structure is preserved
    assert "metadata" in result
    assert "extracted" in result
    assert "pdf_text_preview" in result
    
    # Verify NUL characters are removed
    assert "\x00" not in result["metadata"]["snippet"]
    assert "\x00" not in result["metadata"]["attachments"][0]["filename"]
    assert "\x00" not in result["extracted"]["vendor_name"]
    assert "\x00" not in result["pdf_text_preview"]
    
    # Verify data integrity
    assert result["extracted"]["amount"] == 29.99
    assert result["metadata"]["attachments"][0]["size"] == 45678
    assert result["metadata"]["has_attachment"] is True


if __name__ == "__main__":
    # Run tests
    print("Running Gmail sync resilience tests...")
    
    test_sanitize_simple_string()
    print("✅ test_sanitize_simple_string passed")
    
    test_sanitize_dict()
    print("✅ test_sanitize_dict passed")
    
    test_sanitize_list()
    print("✅ test_sanitize_list passed")
    
    test_sanitize_complex_json()
    print("✅ test_sanitize_complex_json passed")
    
    test_sanitize_replacement_character()
    print("✅ test_sanitize_replacement_character passed")
    
    test_sanitize_none_and_numbers()
    print("✅ test_sanitize_none_and_numbers passed")
    
    test_sanitize_empty_structures()
    print("✅ test_sanitize_empty_structures passed")
    
    test_sanitize_tuple()
    print("✅ test_sanitize_tuple passed")
    
    test_real_world_receipt_data()
    print("✅ test_real_world_receipt_data passed")
    
    print("\n✅ All tests passed!")
