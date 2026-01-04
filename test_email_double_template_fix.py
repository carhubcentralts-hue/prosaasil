#!/usr/bin/env python3
"""
Test for Email Double Template Fix
Verifies that emails have single HTML/style/body tags and no CSS leak
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_template_returns_fragment():
    """Verify get_template_html returns body fragment, not full document"""
    from server.services.email_template_themes import get_template_html
    
    fields = {
        "greeting": "שלום",
        "body": "תוכן",
        "cta_text": "לחץ",
        "cta_url": "https://example.com",
        "footer": "תודה"
    }
    
    html = get_template_html("classic_blue", fields)
    
    # Should be fragment, not full document
    assert "<!DOCTYPE html>" not in html, "Should not contain DOCTYPE"
    assert "<html" not in html.lower(), "Should not contain <html> tag"
    assert "<head>" not in html, "Should not contain <head> tag"
    assert "<body" not in html.lower(), "Should not contain <body> tag"
    
    # Should contain content
    assert "שלום" in html
    assert "תוכן" in html
    
    print("✅ get_template_html returns body fragment (not full HTML)")


def test_base_layout_wrapping():
    """Verify base_layout.html properly wraps fragment"""
    from server.services.email_service import render_variables, load_base_layout
    
    # Simulate what send_crm_email does
    base_layout = load_base_layout()
    
    # Mock fragment from theme
    fragment = """
    <div style="padding: 20px;">
        <h2>שלום</h2>
        <p>זה תוכן</p>
    </div>
    """
    
    variables = {
        'brand_primary_color': '#2563EB',
        'business_name': 'עסק בדיקה',
        'greeting': 'שלום חבר',
        'body_content': fragment,
        'footer_content': 'תודה',
        'brand_logo_url': '',
        'signature': ''
    }
    
    final_html = render_variables(base_layout, variables)
    
    # Should have full document structure
    assert "<!DOCTYPE html>" in final_html
    assert "<html" in final_html
    assert "<head>" in final_html
    assert "<style>" in final_html
    assert "<body>" in final_html
    
    # Should contain the fragment content
    assert "זה תוכן" in final_html
    
    # Count key tags - should be exactly 1 of each
    html_count = final_html.count("<html")
    head_count = final_html.count("<head>")
    style_count = final_html.count("<style>")
    body_count = final_html.count("<body>")
    
    assert html_count == 1, f"Should have 1 <html> tag, found {html_count}"
    assert head_count == 1, f"Should have 1 <head> tag, found {head_count}"
    assert style_count == 1, f"Should have 1 <style> tag, found {style_count}"
    assert body_count == 1, f"Should have 1 <body> tag, found {body_count}"
    
    print("✅ base_layout.html wraps fragment correctly")
    print(f"   HTML tags: {html_count}, Style tags: {style_count}, Body tags: {body_count}")


def test_no_css_leak():
    """Verify CSS doesn't leak as text into body"""
    from server.services.email_service import render_variables, load_base_layout
    
    base_layout = load_base_layout()
    
    variables = {
        'brand_primary_color': '#2563EB',
        'business_name': 'עסק',
        'greeting': 'שלום',
        'body_content': '<p>תוכן</p>',
        'footer_content': 'תודה',
        'brand_logo_url': '',
        'signature': ''
    }
    
    final_html = render_variables(base_layout, variables)
    
    # Extract body content (between <body> and </body>)
    body_start = final_html.find("<body>")
    body_end = final_html.find("</body>")
    body_content = final_html[body_start:body_end]
    
    # CSS properties should NOT appear as plain text in body
    # They should only be in <style> tag or inline style attributes
    css_patterns_as_text = [
        "body {",
        "body{",
        "margin: 0",
        "padding: 0",
        "font-family:",
    ]
    
    style_tag_start = final_html.find("<style>")
    style_tag_end = final_html.find("</style>")
    style_content = final_html[style_tag_start:style_tag_end] if style_tag_start != -1 else ""
    
    for pattern in css_patterns_as_text:
        # Pattern should be in <style> tag
        if pattern in style_content:
            # OK - it's in the style tag
            pass
        # Pattern should NOT be in body as plain text (outside style attributes)
        # Check if it appears outside of style="" attributes
        body_plain_text = body_content
        # Remove all style="..." attributes to get plain text
        import re
        body_plain_text = re.sub(r'style="[^"]*"', '', body_plain_text)
        body_plain_text = re.sub(r"style='[^']*'", '', body_plain_text)
        
        if pattern in body_plain_text:
            print(f"❌ CSS leak detected: '{pattern}' found as plain text in body")
            print(f"   Body excerpt: {body_plain_text[max(0, body_plain_text.find(pattern)-50):body_plain_text.find(pattern)+100]}")
            assert False, f"CSS pattern '{pattern}' leaked as text into body"
    
    print("✅ No CSS leak - all CSS properly contained in <style> tags or inline styles")


def test_complete_email_flow():
    """Test complete flow: theme render → wrap in base_layout → final HTML"""
    from server.services.email_template_themes import get_template_html
    from server.services.email_service import render_variables, load_base_layout
    
    # Step 1: Render theme (returns fragment)
    theme_fields = {
        "greeting": "שלום {{lead.first_name}}",
        "body": "זהו מייל בדיקה\nעם שורות מרובות",
        "cta_text": "לחץ כאן",
        "cta_url": "https://example.com",
        "footer": "תודה רבה"
    }
    
    # Render variables first
    variables_for_theme = {
        'lead': {'first_name': 'יוסי', 'last_name': 'כהן', 'email': '', 'phone': ''},
        'business': {'name': 'עסק דוגמה', 'phone': ''}
    }
    
    rendered_fields = {}
    for key, value in theme_fields.items():
        if isinstance(value, str):
            # Simple variable substitution
            result = value
            for var_key, var_dict in variables_for_theme.items():
                if isinstance(var_dict, dict):
                    for subkey, subvalue in var_dict.items():
                        placeholder = f"{{{{{var_key}.{subkey}}}}}"
                        result = result.replace(placeholder, str(subvalue) if subvalue else '')
            rendered_fields[key] = result
        else:
            rendered_fields[key] = value
    
    fragment = get_template_html("green_success", rendered_fields)
    
    # Verify fragment doesn't have full document structure
    assert "<!DOCTYPE html>" not in fragment
    assert "<html" not in fragment
    
    # Step 2: Wrap in base_layout
    base_layout = load_base_layout()
    
    layout_vars = {
        'brand_primary_color': '#059669',
        'business_name': 'עסק דוגמה',
        'greeting': 'שלום יוסי',
        'body_content': fragment,
        'footer_content': 'פרטי יצירת קשר',
        'brand_logo_url': '',
        'signature': ''
    }
    
    final_html = render_variables(base_layout, layout_vars)
    
    # Step 3: Verify final HTML is correct
    assert "<!DOCTYPE html>" in final_html
    html_count = final_html.count("<html")
    style_count = final_html.count("<style>")
    body_count = final_html.count("<body>")
    
    assert html_count == 1, f"Expected 1 <html> tag, found {html_count}"
    assert style_count == 1, f"Expected 1 <style> tag, found {style_count}"
    assert body_count == 1, f"Expected 1 <body> tag, found {body_count}"
    
    # Verify content is present
    assert "שלום יוסי" in final_html
    assert "זהו מייל בדיקה" in final_html
    assert "לחץ כאן" in final_html
    
    # Verify no CSS leak
    body_start = final_html.find("<body>")
    body_content = final_html[body_start:]
    # Remove style attributes
    import re
    plain_body = re.sub(r'style="[^"]*"', '', body_content)
    
    assert "body {" not in plain_body and "body{" not in plain_body, "CSS should not leak as plain text"
    
    print("✅ Complete flow works: theme fragment → base_layout wrapper → single HTML")
    print(f"   Final HTML: {len(final_html)} chars")
    print(f"   Structure: {html_count} html, {style_count} style, {body_count} body tags")


if __name__ == "__main__":
    print("\n🧪 Testing Email Double Template Fix\n")
    print("=" * 70)
    print("Verifying: Single HTML source, no CSS leak, proper wrapping\n")
    
    try:
        test_template_returns_fragment()
        test_base_layout_wrapping()
        test_no_css_leak()
        test_complete_email_flow()
        
        print("\n" + "=" * 70)
        print("\n✅ All tests passed!")
        print("\n📝 Summary:")
        print("   ✓ get_template_html returns body fragment (not full HTML)")
        print("   ✓ base_layout.html wraps fragment correctly")
        print("   ✓ Final HTML has exactly 1 <html>, 1 <style>, 1 <body>")
        print("   ✓ No CSS leaking as plain text into body")
        print("   ✓ Complete email flow produces valid single-source HTML")
        print("\n🎉 Double Template Bug: FIXED\n")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
