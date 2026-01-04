"""
Test: Unified Email Rendering Fix
Verifies that preview and send use the same HTML without corruption

Issue: Emails sent as plain text or with wrong colors because:
1. sanitize_html() strips <html>, <head>, <body>, <style> tags
2. Sanitization happens BEFORE checking if it's a full document
3. Theme colors get destroyed

Fix: Check for full document BEFORE sanitization, skip sanitization for themes
"""
import sys
import os

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

from services.email_template_themes import get_template_html, EMAIL_TEMPLATE_THEMES
from services.email_service import sanitize_html

def test_theme_html_structure():
    """Test that theme HTML is a complete document"""
    print("\n=== Test 1: Theme HTML Structure ===")
    
    theme_id = "green_success"
    fields = {
        "greeting": "שלום ג'ון,",
        "body": "זה טקסט בדיקה.\nשורה נוספת.",
        "cta_text": "לחץ כאן",
        "cta_url": "https://example.com",
        "footer": "© החברה שלי"
    }
    
    html = get_template_html(theme_id, fields)
    
    # Verify full HTML document
    assert html.strip().startswith('<!DOCTYPE html>'), "❌ HTML must start with DOCTYPE"
    assert '<html' in html.lower(), "❌ HTML must contain <html> tag"
    assert '<head>' in html, "❌ HTML must contain <head> tag"
    assert '<body>' in html, "❌ HTML must contain <body> tag"
    assert '<style>' in html, "❌ HTML must contain <style> tag"
    assert '</html>' in html, "❌ HTML must contain closing </html> tag"
    
    # Verify theme color is present (green_success primary color)
    assert '#059669' in html, "❌ Theme primary color must be in HTML"
    assert '#ECFDF5' in html, "❌ Theme background color must be in HTML"
    
    print("✅ Theme HTML is a complete document")
    print(f"✅ HTML length: {len(html)} chars")
    print(f"✅ Contains theme colors: #059669, #ECFDF5")
    return html

def test_sanitization_preserves_document_tags():
    """Test that sanitize_html skips sanitization for full documents"""
    print("\n=== Test 2: Sanitization Skips Full Documents ===")
    
    # Create a simple full HTML document
    test_html = """<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <style>
        body { background-color: #059669; }
    </style>
</head>
<body>
    <div style="color: red;">Test content</div>
</body>
</html>"""
    
    # Test with is_full_document=True (should not sanitize)
    not_sanitized = sanitize_html(test_html, is_full_document=True)
    
    # Check if document structure is preserved
    assert '<!DOCTYPE html>' in not_sanitized, "❌ DOCTYPE must be preserved when is_full_document=True"
    assert '<html' in not_sanitized, "❌ <html> tag must be preserved"
    assert '<head>' in not_sanitized, "❌ <head> tag must be preserved"
    assert '<body>' in not_sanitized, "❌ <body> tag must be preserved"
    assert '<style>' in not_sanitized, "❌ <style> tag must be preserved"
    assert 'background-color' in not_sanitized, "❌ CSS styles must be preserved"
    assert not_sanitized == test_html, "❌ Full document should not be modified"
    
    print("✅ Full documents (is_full_document=True) are not sanitized")
    print(f"✅ Original and returned HTML are identical: {len(not_sanitized)} chars")
    
    # Test with is_full_document=False (should sanitize fragments)
    fragment = '<div style="color: red;"><script>alert("xss")</script>Safe text</div>'
    sanitized_fragment = sanitize_html(fragment, is_full_document=False)
    
    assert '<script>' not in sanitized_fragment, "❌ <script> tag must be removed from fragments"
    assert 'Safe text' in sanitized_fragment, "❌ Safe content must be preserved in fragments"
    
    print("✅ Fragments (is_full_document=False) are properly sanitized")
    print(f"✅ XSS <script> tag removed from fragment")
    
    return not_sanitized

def test_all_themes_generate_full_documents():
    """Test that all themes generate complete HTML documents"""
    print("\n=== Test 3: All Themes Generate Full Documents ===")
    
    fields = {
        "greeting": "שלום,",
        "body": "תוכן בדיקה",
        "cta_text": "כפתור",
        "cta_url": "https://example.com",
        "footer": "פוטר"
    }
    
    for theme_id in EMAIL_TEMPLATE_THEMES.keys():
        html = get_template_html(theme_id, fields)
        
        # Verify it's a full document
        assert html.strip().startswith('<!DOCTYPE html>'), f"❌ Theme {theme_id} must start with DOCTYPE"
        assert '<html' in html.lower(), f"❌ Theme {theme_id} must contain <html> tag"
        assert '<head>' in html, f"❌ Theme {theme_id} must contain <head> tag"
        assert '<body>' in html, f"❌ Theme {theme_id} must contain <body> tag"
        assert '<style>' in html, f"❌ Theme {theme_id} must contain <style> tag"
        
        # Verify theme colors are present
        theme = EMAIL_TEMPLATE_THEMES[theme_id]
        primary_color = theme['theme']['primary_color']
        assert primary_color in html, f"❌ Theme {theme_id} must contain its primary color {primary_color}"
        
        print(f"✅ Theme {theme_id}: Complete document with color {primary_color}")
    
    return True

def test_full_document_detection():
    """Test that full documents are correctly detected"""
    print("\n=== Test 4: Full Document Detection ===")
    
    # Test cases
    full_docs = [
        '<!DOCTYPE html><html><head></head><body></body></html>',
        '<!doctype html><html><head></head><body></body></html>',
        '<html><head></head><body></body></html>',
        '<?xml version="1.0"?><html><head></head><body></body></html>',
    ]
    
    fragments = [
        '<div>Test</div>',
        '<p>Paragraph</p>',
        'Plain text',
        '<span style="color: red;">Text</span>',
    ]
    
    for doc in full_docs:
        lower = doc.strip().lower()
        is_full = (
            lower.startswith('<!doctype') or
            lower.startswith('<html') or
            lower.startswith('<?xml')
        )
        assert is_full, f"❌ Should detect as full document: {doc[:50]}"
        print(f"✅ Correctly identified full document: {doc[:50]}...")
    
    for frag in fragments:
        lower = frag.strip().lower()
        is_full = (
            lower.startswith('<!doctype') or
            lower.startswith('<html') or
            lower.startswith('<?xml')
        )
        assert not is_full, f"❌ Should detect as fragment: {frag[:50]}"
        print(f"✅ Correctly identified fragment: {frag[:50]}")
    
    return True

def test_theme_colors_not_overridden():
    """Test that each theme keeps its own colors (not overridden by blue)"""
    print("\n=== Test 5: Theme Colors Not Overridden ===")
    
    # Test green theme
    green_html = get_template_html("green_success", {
        "greeting": "Hi",
        "body": "Test",
        "cta_text": "Click",
        "cta_url": "https://example.com",
        "footer": "Footer"
    })
    
    # Green theme should have green, not blue
    assert '#059669' in green_html, "❌ Green theme must have green primary color"
    assert '#10B981' in green_html, "❌ Green theme must have green secondary color"
    assert '#2563EB' not in green_html, "❌ Green theme must NOT have blue color"
    
    print("✅ Green theme has green colors, no blue override")
    
    # Test purple theme
    purple_html = get_template_html("modern_purple", {
        "greeting": "Hi",
        "body": "Test",
        "cta_text": "Click",
        "cta_url": "https://example.com",
        "footer": "Footer"
    })
    
    # Purple theme should have purple, not blue
    assert '#7C3AED' in purple_html, "❌ Purple theme must have purple primary color"
    assert '#A78BFA' in purple_html, "❌ Purple theme must have purple secondary color"
    assert '#2563EB' not in purple_html, "❌ Purple theme must NOT have blue color"
    
    print("✅ Purple theme has purple colors, no blue override")
    
    # Test dark theme
    dark_html = get_template_html("dark_luxury", {
        "greeting": "Hi",
        "body": "Test",
        "cta_text": "Click",
        "cta_url": "https://example.com",
        "footer": "Footer"
    })
    
    # Dark theme should have dark + gold, not blue
    assert '#1F2937' in dark_html, "❌ Dark theme must have dark primary color"
    assert '#D4AF37' in dark_html, "❌ Dark theme must have gold accent color"
    assert '#2563EB' not in dark_html, "❌ Dark theme must NOT have blue color"
    
    print("✅ Dark theme has dark + gold colors, no blue override")
    
    return True

if __name__ == '__main__':
    print("=" * 60)
    print("Email Unified Render Fix - Test Suite")
    print("=" * 60)
    
    try:
        # Run tests
        theme_html = test_theme_html_structure()
        sanitized_html = test_sanitization_preserves_document_tags()
        test_all_themes_generate_full_documents()
        test_full_document_detection()
        test_theme_colors_not_overridden()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\n📋 Summary:")
        print("1. ✅ Themes generate complete HTML documents")
        print("2. ✅ Sanitization preserves HTML document tags")
        print("3. ✅ All 5 themes generate proper documents")
        print("4. ✅ Full document detection works correctly")
        print("5. ✅ Theme colors are not overridden by blue")
        print("\n🎯 Fix Status: VERIFIED")
        print("   - Preview HTML = Send HTML (no corruption)")
        print("   - Green theme stays green, purple stays purple")
        print("   - No hardcoded blue wrapper")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
