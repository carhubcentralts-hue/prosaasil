#!/usr/bin/env python3
"""
Visual test for all themes - verify each has distinct colors
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from server.services.email_template_themes import get_template_html, EMAIL_TEMPLATE_THEMES

def test_all_themes_visual():
    """Generate sample HTML for each theme to verify colors"""
    
    fields = {
        "greeting": "שלום מרים",
        "body": "זהו מייל דוגמה.\n\nאנחנו רוצים לראות את הצבעים של התבנית.\n\nתודה!",
        "cta_text": "לחצי כאן",
        "cta_url": "https://example.com",
        "footer": "להסרה מרשימת התפוצה לחצי כאן.\n\n© החברה שלנו"
    }
    
    print("\n" + "="*70)
    print("🎨 Testing All Email Themes - Visual Verification")
    print("="*70 + "\n")
    
    for theme_id, theme_data in EMAIL_TEMPLATE_THEMES.items():
        print(f"\n📧 Theme: {theme_data['name']} ({theme_id})")
        print("-" * 70)
        
        # Get theme colors
        colors = theme_data['theme']
        print(f"   Primary Color:    {colors['primary_color']}")
        print(f"   Secondary Color:  {colors['secondary_color']}")
        print(f"   Button BG:        {colors['button_bg']}")
        print(f"   Background:       {colors['background_color']}")
        
        # Render HTML
        html = get_template_html(theme_id, fields)
        
        # Verify it's a full document
        html_lower = html.strip().lower()
        assert html_lower.startswith('<!doctype'), f"Theme {theme_id} should return full HTML"
        assert '</html>' in html_lower, f"Theme {theme_id} should have closing </html> tag"
        assert '</body>' in html_lower, f"Theme {theme_id} should have closing </body> tag"
        
        # Verify theme colors are in the HTML
        assert colors['primary_color'] in html, f"Primary color missing in {theme_id}"
        assert colors['button_bg'] in html, f"Button color missing in {theme_id}"
        assert colors['background_color'] in html, f"Background color missing in {theme_id}"
        
        # Verify NO hardcoded blue (#2563EB) unless it's the blue theme
        if theme_id != 'classic_blue':
            blue_count = html.count('#2563EB')
            if blue_count > 0:
                print(f"   ⚠️  WARNING: Found {blue_count} instances of hardcoded blue #2563EB!")
            else:
                print(f"   ✅ No hardcoded blue - theme colors preserved")
        else:
            print(f"   ✅ Blue theme - blue color is expected")
        
        print(f"   HTML Length: {len(html)} chars")
        print(f"   Full Document: {'<!DOCTYPE html>' in html}")
        
        # Save sample to file for manual inspection
        filename = f"/tmp/theme_{theme_id}_sample.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"   💾 Sample saved: {filename}")
    
    print("\n" + "="*70)
    print("✅ All themes tested successfully!")
    print("="*70 + "\n")
    
    print("📝 To visually inspect themes:")
    print("   Open the saved HTML files in a browser:")
    for theme_id in EMAIL_TEMPLATE_THEMES.keys():
        print(f"   - /tmp/theme_{theme_id}_sample.html")
    print()

if __name__ == "__main__":
    test_all_themes_visual()
