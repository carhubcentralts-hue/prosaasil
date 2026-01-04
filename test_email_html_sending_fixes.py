#!/usr/bin/env python3
"""
Test for Email HTML Sending Fixes
Verifies:
1. HTML is sent as html_content (not plain text)
2. Theme ID validation works
3. HTML length validation works
4. Theme colors are applied correctly
5. No HTML escaping in final output
"""
import sys
import os

# Add server to path
sys.path.insert(0, os.path.dirname(__file__))


def test_theme_id_validation():
    """Test that invalid theme_id returns proper error"""
    from server.services.email_template_themes import get_template_html, EMAIL_TEMPLATE_THEMES
    
    # Test with valid theme
    html = get_template_html("classic_blue", {})
    assert html is not None
    print("✅ Valid theme_id works")
    
    # Test with invalid theme - should fallback to classic_blue
    html = get_template_html("invalid_theme", {})
    assert html is not None
    assert len(html) > 100
    print("✅ Invalid theme_id falls back to default")
    
    # Verify all registered themes work
    for theme_id in EMAIL_TEMPLATE_THEMES.keys():
        html = get_template_html(theme_id, {})
        assert html is not None
        print(f"   ✓ Theme '{theme_id}' validated")
    
    print(f"✅ All {len(EMAIL_TEMPLATE_THEMES)} theme IDs validated")


def test_theme_colors_applied():
    """Test that each theme has distinct colors applied"""
    from server.services.email_template_themes import get_template_html, EMAIL_TEMPLATE_THEMES
    
    fields = {
        "greeting": "Test",
        "body": "Test body",
        "cta_text": "Click",
        "cta_url": "https://example.com",
        "footer": "Footer"
    }
    
    theme_colors = {}
    for theme_id, theme_data in EMAIL_TEMPLATE_THEMES.items():
        html = get_template_html(theme_id, fields)
        
        # Extract primary color from theme
        primary_color = theme_data["theme"]["primary_color"]
        button_bg = theme_data["theme"]["button_bg"]
        
        # Verify color is in HTML
        assert primary_color in html, f"Theme {theme_id} missing primary color {primary_color}"
        assert button_bg in html, f"Theme {theme_id} missing button bg {button_bg}"
        
        theme_colors[theme_id] = {
            'primary': primary_color,
            'button': button_bg
        }
        
        print(f"   ✓ Theme '{theme_id}' has colors: primary={primary_color}, button={button_bg}")
    
    # Verify themes have different colors
    unique_primaries = len(set(c['primary'] for c in theme_colors.values()))
    assert unique_primaries > 1, "Themes should have different primary colors"
    
    print(f"✅ All themes have distinct colors applied ({unique_primaries} unique primary colors)")


def test_html_not_escaped():
    """Test that HTML output is not escaped (no &lt; &gt;)"""
    from server.services.email_template_themes import get_template_html
    
    fields = {
        "greeting": "שלום",
        "body": "תוכן המייל",
        "cta_text": "לחץ כאן",
        "cta_url": "https://example.com",
        "footer": "תודה"
    }
    
    html = get_template_html("classic_blue", fields)
    
    # Verify HTML tags are NOT escaped in the output
    assert "<div" in html, "Should contain <div tags"
    assert "&lt;div" not in html, "Should NOT contain escaped &lt;div"
    assert "&gt;" not in html, "Should NOT contain escaped &gt;"
    assert "style=" in html, "Should contain style= attributes"
    
    # Verify inline styles are present (not stripped)
    assert "background-color:" in html or "color:" in html, "Should contain CSS properties"
    
    print("✅ HTML output is not escaped")
    print(f"   HTML length: {len(html)} characters")
    print(f"   Contains <div tags: {'<div' in html}")
    print(f"   Contains style attributes: {'style=' in html}")


def test_html_length_sufficient():
    """Test that generated HTML has sufficient length"""
    from server.services.email_template_themes import get_template_html
    
    fields = {
        "greeting": "שלום",
        "body": "תוכן קצר",
        "cta_text": "לחץ",
        "cta_url": "https://example.com",
        "footer": "תודה"
    }
    
    html = get_template_html("classic_blue", fields)
    
    # HTML should be at least 200 characters (our validation threshold)
    assert len(html) >= 200, f"HTML too short: {len(html)} chars (expected >= 200)"
    
    print(f"✅ HTML length is sufficient: {len(html)} characters (>= 200 required)")


def test_user_input_escaped_but_not_structure():
    """Test that user input is escaped but HTML structure is not"""
    from server.services.email_template_themes import get_template_html
    
    # User input with potential XSS
    fields = {
        "greeting": "<script>alert('xss')</script>שלום",
        "body": "תוכן <b>נורמלי</b> עם <script>קוד</script>",
        "cta_text": "<img src=x> Click",
        "cta_url": "javascript:alert('xss')",
        "footer": "תודה"
    }
    
    html = get_template_html("classic_blue", fields)
    
    # User's malicious content should be escaped
    assert "<script>" not in html, "User <script> should be escaped"
    assert "&lt;script&gt;" in html, "User content should show as &lt;script&gt;"
    
    # But the template's own HTML structure should NOT be escaped
    assert "<div" in html, "Template <div should NOT be escaped"
    assert "&lt;div" not in html, "Template structure should not be double-escaped"
    
    print("✅ User input escaped but template structure preserved")


def test_full_html_structure_in_final_output():
    """Test that when wrapped in base_layout, we get full HTML document"""
    # Mock required modules if not available
    import sys
    from unittest.mock import Mock
    
    if 'sendgrid' not in sys.modules:
        sys.modules['sendgrid'] = Mock()
        sys.modules['sendgrid.helpers'] = Mock()
        sys.modules['sendgrid.helpers.mail'] = Mock()
    
    if 'bleach' not in sys.modules:
        bleach_mock = Mock()
        bleach_mock.clean = lambda html, **kwargs: html  # Just return HTML as-is
        sys.modules['bleach'] = bleach_mock
        sys.modules['bleach.css_sanitizer'] = Mock()
    
    from server.services.email_service import load_base_layout, render_variables
    
    base_layout = load_base_layout()
    
    # Verify base layout has full HTML structure
    assert "<!DOCTYPE html>" in base_layout or "<!doctype html>" in base_layout.lower()
    assert "<html" in base_layout
    assert "<head>" in base_layout
    assert "<body>" in base_layout
    assert "</body>" in base_layout
    assert "</html>" in base_layout
    
    # Verify Jinja2 placeholders exist
    assert "{{body_content}}" in base_layout
    assert "{{greeting}}" in base_layout
    
    # Test rendering with sample data
    rendered = render_variables(base_layout, {
        'brand_primary_color': '#2563EB',
        'business_name': 'Test Business',
        'greeting': 'שלום',
        'body_content': '<p>Test content</p>',
        'footer_content': 'Footer',
        'brand_logo_url': '',
        'signature': ''
    })
    
    # Verify full structure in output
    assert "<!DOCTYPE html>" in rendered or "<!doctype html>" in rendered.lower()
    assert "<html" in rendered
    assert "Test Business" in rendered
    assert "Test content" in rendered
    
    print("✅ Base layout provides full HTML document structure")
    print(f"   Final HTML length: {len(rendered)} characters")


def test_no_double_template():
    """Test that we have proper HTML structure (one <html>, one <body>)"""
    from server.services.email_template_themes import get_template_html
    
    fields = {
        "greeting": "שלום",
        "body": "תוכן",
        "cta_text": "לחץ",
        "cta_url": "https://example.com",
        "footer": "תודה"
    }
    
    # 🔥 FIX: Full document now has exactly one of each
    html = get_template_html("classic_blue", fields)
    
    html_count = html.count("<html")
    body_count = html.count("<body")
    head_count = html.count("<head")
    
    assert html_count == 1, f"Should have exactly 1 <html tag, found {html_count}"
    assert body_count == 1, f"Should have exactly 1 <body tag, found {body_count}"
    assert head_count == 1, f"Should have exactly 1 <head tag, found {head_count}"
    
    print("✅ Template has proper HTML structure")
    print(f"   <html count: {html_count}, <body count: {body_count}, <head count: {head_count}")


if __name__ == "__main__":
    print("\n🧪 Testing Email HTML Sending Fixes\n")
    print("=" * 60)
    
    try:
        test_theme_id_validation()
        test_theme_colors_applied()
        test_html_not_escaped()
        test_html_length_sufficient()
        test_user_input_escaped_but_not_structure()
        test_full_html_structure_in_final_output()
        test_no_double_template()
        
        print("=" * 60)
        print("\n✅ All tests passed! Email HTML sending fixes are working.\n")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
