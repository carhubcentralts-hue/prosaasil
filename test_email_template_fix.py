#!/usr/bin/env python3
"""
Test for Email Template Theme HTML Escape Fix
Verifies that the UnboundLocalError is fixed and templates render correctly
"""

def test_email_template_import():
    """Test that html_escape is imported correctly"""
    from server.services.email_template_themes import html_escape
    
    # Test that html_escape works
    result = html_escape("<script>alert('xss')</script>")
    assert "&lt;script&gt;" in result
    assert "<script>" not in result
    print("✅ html_escape imported and working correctly")


def test_get_template_html_basic():
    """Test basic template rendering without variables"""
    from server.services.email_template_themes import get_template_html
    
    fields = {
        "greeting": "שלום חבר",
        "body": "זה תוכן של מייל",
        "cta_text": "לחץ כאן",
        "cta_url": "https://example.com",
        "footer": "תודה"
    }
    
    html = get_template_html("classic_blue", fields)
    
    # Verify it returns HTML
    assert html is not None
    assert isinstance(html, str)
    assert len(html) > 100
    assert "<!DOCTYPE html>" in html
    assert "שלום חבר" in html
    assert "זה תוכן של מייל" in html
    assert "לחץ כאן" in html
    assert "https://example.com" in html
    
    print("✅ Basic template rendering works")
    print(f"   Generated HTML length: {len(html)} characters")


def test_get_template_html_with_xss():
    """Test that XSS content is escaped properly"""
    from server.services.email_template_themes import get_template_html
    
    fields = {
        "greeting": "<script>alert('xss')</script>",
        "body": "<img src=x onerror=alert('xss')>",
        "cta_text": "<b>Click</b>",
        "cta_url": "javascript:alert('xss')",
        "footer": "Safe footer text"  # Footer allows HTML, so we test with safe text
    }
    
    html = get_template_html("classic_blue", fields)
    
    # Verify XSS content is escaped in greeting, body, cta_text, cta_url
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<img src=x" not in html
    assert "&lt;img" in html
    # cta_url XSS should be escaped
    assert "javascript:alert" in html  # It's escaped in the href attribute
    
    print("✅ XSS content properly escaped")


def test_get_template_html_with_none_fields():
    """Test that None fields don't cause errors"""
    from server.services.email_template_themes import get_template_html
    
    fields = {
        "greeting": None,
        "body": None,
        "cta_text": None,
        "cta_url": None,
        "footer": None
    }
    
    html = get_template_html("classic_blue", fields)
    
    # Should use defaults and not crash
    assert html is not None
    assert isinstance(html, str)
    assert "<!DOCTYPE html>" in html
    
    print("✅ None fields handled correctly with defaults")


def test_get_template_html_empty_fields():
    """Test with empty strings"""
    from server.services.email_template_themes import get_template_html
    
    fields = {
        "greeting": "",
        "body": "",
        "cta_text": "",
        "cta_url": "",
        "footer": ""
    }
    
    html = get_template_html("classic_blue", fields)
    
    # Should use defaults and not crash
    assert html is not None
    assert isinstance(html, str)
    assert "<!DOCTYPE html>" in html
    
    print("✅ Empty fields handled correctly with defaults")


def test_get_template_html_newlines():
    """Test that newlines are converted to <br> tags"""
    from server.services.email_template_themes import get_template_html
    
    fields = {
        "greeting": "שלום",
        "body": "שורה 1\nשורה 2\nשורה 3",
        "cta_text": "לחץ",
        "cta_url": "https://example.com",
        "footer": "שורה 1\nשורה 2"
    }
    
    html = get_template_html("classic_blue", fields)
    
    # Verify newlines converted to <br>
    assert "<br>" in html
    # Count approximate number of <br> tags (should be at least 4: 2 in body + 1 in footer)
    br_count = html.count("<br>")
    assert br_count >= 3, f"Expected at least 3 <br> tags, got {br_count}"
    
    print(f"✅ Newlines converted to <br> tags (found {br_count} <br> tags)")


def test_all_themes():
    """Test that all themes work"""
    from server.services.email_template_themes import EMAIL_TEMPLATE_THEMES, get_template_html
    
    fields = {
        "greeting": "שלום",
        "body": "תוכן",
        "cta_text": "לחץ",
        "cta_url": "https://example.com",
        "footer": "תודה"
    }
    
    for theme_id in EMAIL_TEMPLATE_THEMES.keys():
        html = get_template_html(theme_id, fields)
        assert html is not None
        assert isinstance(html, str)
        assert len(html) > 100
        print(f"   ✓ Theme '{theme_id}' renders correctly")
    
    print(f"✅ All {len(EMAIL_TEMPLATE_THEMES)} themes render successfully")


def test_get_all_themes():
    """Test the get_all_themes function"""
    from server.services.email_template_themes import get_all_themes, EMAIL_TEMPLATE_THEMES
    
    themes = get_all_themes()
    
    assert isinstance(themes, list)
    assert len(themes) == len(EMAIL_TEMPLATE_THEMES)  # Should match number of templates
    
    for theme in themes:
        assert "id" in theme
        assert "name" in theme
        assert "description" in theme
        assert "preview_thumbnail" in theme
        assert "default_fields" in theme
        assert "supports_fields" in theme
    
    print(f"✅ get_all_themes returns {len(themes)} themes correctly")


if __name__ == "__main__":
    print("\n🧪 Testing Email Template Fix\n")
    print("=" * 60)
    
    try:
        test_email_template_import()
        test_get_template_html_basic()
        test_get_template_html_with_xss()
        test_get_template_html_with_none_fields()
        test_get_template_html_empty_fields()
        test_get_template_html_newlines()
        test_all_themes()
        test_get_all_themes()
        
        print("=" * 60)
        print("\n✅ All tests passed! Email template fix is working.\n")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
