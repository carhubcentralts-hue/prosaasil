"""
Test Content Filter Fixes - PII Sanitization & Detection
Tests the new sanitize_for_realtime and analyze_text_for_pii functions
"""
import sys
import os

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

from server.services.realtime_prompt_builder import (
    sanitize_for_realtime,
    analyze_text_for_pii,
    sanitize_realtime_instructions
)


def test_email_removal():
    """Test that emails are removed"""
    text = "Contact me at john@example.com or support@company.co.il for help"
    sanitized = sanitize_for_realtime(text)
    
    assert "@example.com" not in sanitized, "Email should be removed"
    assert "@company.co.il" not in sanitized, "Email should be removed"
    assert "[email]" in sanitized, "Email placeholder should be present"
    print("✅ Email removal test passed")


def test_phone_removal():
    """Test that phone numbers are removed"""
    # Israeli mobile
    text1 = "Call me at 054-1234567 or +972-54-1234567"
    sanitized1 = sanitize_for_realtime(text1)
    assert "054-1234567" not in sanitized1, "Israeli phone should be removed"
    assert "+972-54-1234567" not in sanitized1, "International format should be removed"
    assert "[phone]" in sanitized1, "Phone placeholder should be present"
    
    # Israeli landline
    text2 = "Office: 03-1234567"
    sanitized2 = sanitize_for_realtime(text2)
    assert "03-1234567" not in sanitized2, "Landline should be removed"
    
    print("✅ Phone removal test passed")


def test_url_removal():
    """Test that URLs are removed"""
    text = "Visit https://example.com or www.company.co.il for more info"
    sanitized = sanitize_for_realtime(text)
    
    assert "https://example.com" not in sanitized, "HTTPS URL should be removed"
    assert "www.company.co.il" not in sanitized, "WWW URL should be removed"
    print("✅ URL removal test passed")


def test_id_removal():
    """Test that technical IDs are removed"""
    text1 = "Lead ID: 12345 and call_id=abc-def"
    sanitized1 = sanitize_for_realtime(text1)
    assert "Lead ID: 12345" not in sanitized1, "Lead ID should be removed"
    assert "call_id=abc-def" not in sanitized1, "call_id should be removed"
    
    text2 = "Business ID: 789, tenant_id: 456"
    sanitized2 = sanitize_for_realtime(text2)
    assert "Business ID: 789" not in sanitized2, "Business ID should be removed"
    
    print("✅ ID removal test passed")


def test_technical_markers_removal():
    """Test that technical markers are removed"""
    text = "##CRM_CONTEXT_START## Customer info here ##CRM_CONTEXT_END##"
    sanitized = sanitize_for_realtime(text)
    
    assert "##CRM_CONTEXT_START##" not in sanitized, "Start marker should be removed"
    assert "##CRM_CONTEXT_END##" not in sanitized, "End marker should be removed"
    assert "##" not in sanitized, "Hash markers should be removed"
    
    text2 = "BEGIN_BUSINESS_PROMPT content here END_BUSINESS_PROMPT"
    sanitized2 = sanitize_for_realtime(text2)
    assert "BEGIN_BUSINESS_PROMPT" not in sanitized2, "BEGIN marker should be removed"
    assert "END_BUSINESS_PROMPT" not in sanitized2, "END marker should be removed"
    
    print("✅ Technical markers removal test passed")


def test_excessive_punctuation_normalization():
    """Test that excessive punctuation is normalized"""
    text = "Really???? Yes!!!! Wait..."
    sanitized = sanitize_for_realtime(text)
    
    assert "????" not in sanitized, "Excessive question marks should be normalized"
    assert "!!!!" not in sanitized, "Excessive exclamation marks should be normalized"
    assert "..." not in sanitized or sanitized.count('.') <= 1, "Excessive dots should be normalized"
    
    print("✅ Excessive punctuation normalization test passed")


def test_pii_analysis():
    """Test PII analysis without extraction"""
    # Text with email
    text1 = "Contact john@example.com"
    analysis1 = analyze_text_for_pii(text1)
    assert analysis1['contains_email'] == True, "Should detect email"
    assert analysis1['contains_phone'] == False, "Should not detect phone"
    assert "john@example.com" not in str(analysis1), "Should not contain actual email"
    
    # Text with phone
    text2 = "Call 054-1234567"
    analysis2 = analyze_text_for_pii(text2)
    assert analysis2['contains_phone'] == True, "Should detect phone"
    assert analysis2['contains_email'] == False, "Should not detect email"
    assert "054-1234567" not in str(analysis2), "Should not contain actual phone"
    
    # Text with URL
    text3 = "Visit https://example.com"
    analysis3 = analyze_text_for_pii(text3)
    assert analysis3['contains_url'] == True, "Should detect URL"
    assert "https://example.com" not in str(analysis3), "Should not contain actual URL"
    
    # Text with ID
    text4 = "Lead ID: 12345"
    analysis4 = analyze_text_for_pii(text4)
    assert analysis4['contains_id'] == True, "Should detect ID"
    assert "12345" not in str(analysis4), "Should not contain actual ID"
    
    # Text with no PII
    text5 = "שלום, איך אפשר לעזור?"
    analysis5 = analyze_text_for_pii(text5)
    assert analysis5['contains_email'] == False, "Should not detect email"
    assert analysis5['contains_phone'] == False, "Should not detect phone"
    assert analysis5['contains_url'] == False, "Should not detect URL"
    assert analysis5['contains_id'] == False, "Should not detect ID"
    
    # Check hash is present
    assert 'text_hash' in analysis5, "Should have hash"
    assert len(analysis5['text_hash']) > 0, "Hash should not be empty"
    
    print("✅ PII analysis test passed")


def test_length_capping():
    """Test that text is capped at specified length"""
    long_text = "א" * 5000  # 5000 characters
    sanitized = sanitize_for_realtime(long_text, max_chars=3000)
    
    assert len(sanitized) <= 3000, f"Text should be capped at 3000 chars, got {len(sanitized)}"
    print("✅ Length capping test passed")


def test_real_world_prompt_with_pii():
    """Test realistic prompt with multiple PII types"""
    prompt = """
    You are a representative for Tech Company.
    Customer name: John Doe
    Email: john.doe@company.com
    Phone: 054-1234567
    Lead ID: 12345
    Website: https://company.co.il
    
    Business ID: 789
    
    ##CRM_CONTEXT_START##
    Full context here...
    ##CRM_CONTEXT_END##
    
    Help the customer with their inquiry!!!!
    """
    
    # Analyze before
    before_analysis = analyze_text_for_pii(prompt)
    assert before_analysis['contains_email'] == True
    assert before_analysis['contains_phone'] == True
    assert before_analysis['contains_url'] == True
    assert before_analysis['contains_id'] == True
    
    # Sanitize
    sanitized = sanitize_for_realtime(prompt)
    
    # Analyze after
    after_analysis = analyze_text_for_pii(sanitized)
    
    # Should have no PII after sanitization
    assert after_analysis['contains_email'] == False, f"Email should be removed: {sanitized}"
    assert after_analysis['contains_phone'] == False, f"Phone should be removed: {sanitized}"
    assert after_analysis['contains_url'] == False, f"URL should be removed: {sanitized}"
    assert after_analysis['contains_id'] == False, f"ID should be removed: {sanitized}"
    
    # Check content
    assert "john.doe@company.com" not in sanitized
    assert "054-1234567" not in sanitized
    assert "https://company.co.il" not in sanitized
    assert "Lead ID: 12345" not in sanitized
    assert "Business ID: 789" not in sanitized
    assert "##CRM_CONTEXT_START##" not in sanitized
    assert "##CRM_CONTEXT_END##" not in sanitized
    assert "!!!!" not in sanitized
    
    # Should still have business context
    assert "Tech Company" in sanitized
    assert "customer" in sanitized.lower()
    
    print("✅ Real-world prompt sanitization test passed")
    print(f"   Original length: {len(prompt)}")
    print(f"   Sanitized length: {len(sanitized)}")
    print(f"   Sample: {sanitized[:200]}...")


def test_hebrew_content_preserved():
    """Test that Hebrew content is preserved during sanitization"""
    text = "שלום, אני נציג של החברה. איך אפשר לעזור היום?"
    sanitized = sanitize_for_realtime(text)
    
    # Should preserve Hebrew
    assert "שלום" in sanitized
    assert "נציג" in sanitized
    assert "לעזור" in sanitized
    
    print("✅ Hebrew content preservation test passed")


def run_all_tests():
    """Run all test functions"""
    print("🧪 Running Content Filter Fix Tests\n")
    print("=" * 60)
    
    test_email_removal()
    test_phone_removal()
    test_url_removal()
    test_id_removal()
    test_technical_markers_removal()
    test_excessive_punctuation_normalization()
    test_pii_analysis()
    test_length_capping()
    test_real_world_prompt_with_pii()
    test_hebrew_content_preserved()
    
    print("=" * 60)
    print("✅ All Content Filter Fix tests passed!")


if __name__ == "__main__":
    run_all_tests()
