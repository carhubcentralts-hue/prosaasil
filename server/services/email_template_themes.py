"""
Email Template Themes - Luxury Pre-built Templates
Professional email templates with different visual styles
"""
from html import escape as html_escape

# 🎨 Luxury Email Templates Catalog
# Each template has a unique visual style with colors, buttons, and layout
EMAIL_TEMPLATE_THEMES = {
    "classic_blue": {
        "id": "classic_blue",
        "name": "Classic Blue",
        "description": "תבנית כחולה קלאסית ומקצועית",
        "theme": {
            "primary_color": "#2563EB",
            "secondary_color": "#60A5FA",
            "text_color": "#1F2937",
            "background_color": "#F3F4F6",
            "button_bg": "#2563EB",
            "button_text": "#FFFFFF",
            "border_radius": "8px"
        },
        "preview_thumbnail": "/static/email-templates/classic-blue-preview.png",
        "default_fields": {
            "subject": "הצעה מיוחדת ממש בשבילך",
            "greeting": "שלום {{lead.first_name}},",
            "body": "אנחנו שמחים להציע לך את השירותים שלנו.\n\nאנחנו ב-{{business.name}} מספקים פתרונות מתקדמים ומותאמים אישית.\n\nנשמח לשמוע ממך!",
            "cta_text": "צור קשר עכשיו",
            "cta_url": "https://example.com/contact",
            "footer": "אם אינך מעוניין לקבל הודעות נוספות, אנא לחץ כאן להסרה מהרשימה.\n\n© {{business.name}} | כל הזכויות שמורות"
        },
        "supports_fields": ["subject", "greeting", "body", "cta_text", "cta_url", "footer"]
    },
    "dark_luxury": {
        "id": "dark_luxury",
        "name": "Dark Luxury",
        "description": "תבנית כהה ויוקרתית",
        "theme": {
            "primary_color": "#1F2937",
            "secondary_color": "#D4AF37",
            "text_color": "#F9FAFB",
            "background_color": "#111827",
            "button_bg": "#D4AF37",
            "button_text": "#000000",
            "border_radius": "12px"
        },
        "preview_thumbnail": "/static/email-templates/dark-luxury-preview.png",
        "default_fields": {
            "subject": "חווית פרימיום רק בשבילך",
            "greeting": "שלום {{lead.first_name}},",
            "body": "אנחנו מזמינים אותך לחוות שירות ברמה הגבוהה ביותר.\n\nהצטרף למועדון הלקוחות המובחרים שלנו.\n\nחווית יוקרה שמתחילה כאן.",
            "cta_text": "גלה עוד",
            "cta_url": "https://example.com/premium",
            "footer": "אם אינך מעוניין לקבל הודעות נוספות, לחץ כאן.\n\n© {{business.name}}"
        },
        "supports_fields": ["subject", "greeting", "body", "cta_text", "cta_url", "footer"]
    },
    "minimal_white": {
        "id": "minimal_white",
        "name": "Minimal White",
        "description": "תבנית לבנה מינימליסטית",
        "theme": {
            "primary_color": "#000000",
            "secondary_color": "#6B7280",
            "text_color": "#1F2937",
            "background_color": "#FFFFFF",
            "button_bg": "#000000",
            "button_text": "#FFFFFF",
            "border_radius": "4px"
        },
        "preview_thumbnail": "/static/email-templates/minimal-white-preview.png",
        "default_fields": {
            "subject": "עדכון חשוב עבורך",
            "greeting": "שלום {{lead.first_name}},",
            "body": "רצינו לעדכן אותך בנושאים החשובים.\n\nהשירותים שלנו כאן בשבילך.\n\nנשמח לעזור.",
            "cta_text": "למידע נוסף",
            "cta_url": "https://example.com/info",
            "footer": "להסרה מהרשימה לחץ כאן.\n\n{{business.name}}"
        },
        "supports_fields": ["subject", "greeting", "body", "cta_text", "cta_url", "footer"]
    },
    "green_success": {
        "id": "green_success",
        "name": "Green Success",
        "description": "תבנית ירוקה להצלחה",
        "theme": {
            "primary_color": "#059669",
            "secondary_color": "#10B981",
            "text_color": "#064E3B",
            "background_color": "#ECFDF5",
            "button_bg": "#059669",
            "button_text": "#FFFFFF",
            "border_radius": "8px"
        },
        "preview_thumbnail": "/static/email-templates/green-success-preview.png",
        "default_fields": {
            "subject": "הצעה מוצלחת במיוחד",
            "greeting": "שלום {{lead.first_name}},",
            "body": "יש לנו חדשות טובות!\n\nהשירותים שלנו זמינים עכשיו במחיר מיוחד.\n\nאל תפספס את ההזדמנות!",
            "cta_text": "קבל את ההצעה",
            "cta_url": "https://example.com/offer",
            "footer": "להסרה מרשימת התפוצה לחץ כאן.\n\n© {{business.name}}"
        },
        "supports_fields": ["subject", "greeting", "body", "cta_text", "cta_url", "footer"]
    },
    "modern_purple": {
        "id": "modern_purple",
        "name": "Modern Purple",
        "description": "תבנית סגולה מודרנית",
        "theme": {
            "primary_color": "#7C3AED",
            "secondary_color": "#A78BFA",
            "text_color": "#1F2937",
            "background_color": "#F5F3FF",
            "button_bg": "#7C3AED",
            "button_text": "#FFFFFF",
            "border_radius": "10px"
        },
        "preview_thumbnail": "/static/email-templates/modern-purple-preview.png",
        "default_fields": {
            "subject": "טכנולוגיה מתקדמת רק בשבילך",
            "greeting": "שלום {{lead.first_name}},",
            "body": "גלה את הפתרונות החדשניים שלנו.\n\nאנחנו משלבים טכנולוגיה מתקדמת עם שירות אישי.\n\nבוא להיות חלק מהמהפכה.",
            "cta_text": "גלה את הטכנולוגיה",
            "cta_url": "https://example.com/tech",
            "footer": "אם אינך מעוניין לקבל עדכונים נוספים, לחץ כאן.\n\n© {{business.name}}"
        },
        "supports_fields": ["subject", "greeting", "body", "cta_text", "cta_url", "footer"]
    }
}


def get_template_html(theme_id: str, fields: dict) -> str:
    """
    Generate BODY FRAGMENT HTML from theme and fields
    
    ✅ FIX: Returns ONLY inner content (no <html>, <head>, <style>, <body> tags)
    The wrapper (base_layout.html) will be applied by send_crm_email() to avoid double templates
    
    Args:
        theme_id: Theme ID (e.g., "classic_blue")
        fields: Dict with user-provided content (subject, greeting, body, cta_text, cta_url, footer)
        
    Returns:
        Body fragment HTML (inner content only) with inline styles for theme colors
    """
    if theme_id not in EMAIL_TEMPLATE_THEMES:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"[EMAIL_THEMES] Invalid theme_id '{theme_id}', using classic_blue fallback")
        theme_id = "classic_blue"  # Fallback to default
    
    theme = EMAIL_TEMPLATE_THEMES[theme_id]
    colors = theme["theme"]
    
    # 🔥 FIX 7: Log theme colors to verify correct theme is being used
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[EMAIL_THEMES] Rendering theme_id={theme_id} primary_color={colors['primary_color']} button_bg={colors['button_bg']}")
    
    # Extract fields with defaults
    greeting = fields.get("greeting", theme["default_fields"]["greeting"])
    body = fields.get("body", theme["default_fields"]["body"])
    cta_text = fields.get("cta_text", theme["default_fields"]["cta_text"])
    cta_url = fields.get("cta_url", theme["default_fields"]["cta_url"])
    footer = fields.get("footer", theme["default_fields"]["footer"])
    
    # 🔒 SECURITY: Escape HTML in user-provided content to prevent XSS
    greeting = html_escape(greeting or "")
    body = html_escape(body or "")
    cta_text = html_escape(cta_text or "")
    cta_url = html_escape(cta_url or "")
    footer = footer or ""  # footer can be plain text or html
    
    # Convert newlines to <br> tags in body (after escaping)
    body_html = body.replace("\n", "<br>")
    footer_html = footer.replace("\n", "<br>")
    
    # Build CTA button HTML (only if text and URL provided)
    cta_html = ""
    if cta_text and cta_url:
        cta_html = f"""
        <div style="text-align: center; margin: 32px 0;">
            <a href="{cta_url}" 
               style="display: inline-block; 
                      padding: 14px 32px; 
                      background-color: {colors['button_bg']}; 
                      color: {colors['button_text']}; 
                      text-decoration: none; 
                      border-radius: {colors['border_radius']}; 
                      font-weight: bold;
                      font-size: 16px;">
                {cta_text}
            </a>
        </div>
        """
    
    # ✅ FIX: Return ONLY body fragment (no <html>, <head>, <style>, <body>)
    # The base_layout.html wrapper will be applied by send_crm_email()
    html_fragment = f"""
    <!-- Main content card with theme: {theme_id} -->
    <div style="background-color: #FFFFFF; 
                border-radius: {colors['border_radius']}; 
                padding: 40px; 
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);">
        
        <!-- Greeting -->
        <div style="color: {colors['primary_color']}; 
                    font-size: 20px; 
                    font-weight: bold; 
                    margin-bottom: 20px;">
            {greeting}
        </div>
        
        <!-- Body content -->
        <div style="color: {colors['text_color']}; 
                    font-size: 16px; 
                    line-height: 1.6; 
                    margin-bottom: 24px;">
            {body_html}
        </div>
        
        <!-- CTA Button -->
        {cta_html}
    </div>
    
    <!-- Footer -->
    <div style="margin-top: 32px; 
                padding: 20px; 
                text-align: center; 
                color: {colors['secondary_color']}; 
                font-size: 12px; 
                line-height: 1.4;">
        {footer_html}
    </div>
    """
    
    return html_fragment


def get_all_themes():
    """Get list of all available themes"""
    return [
        {
            "id": theme["id"],
            "name": theme["name"],
            "description": theme["description"],
            "preview_thumbnail": theme["preview_thumbnail"],
            "default_fields": theme["default_fields"],
            "supports_fields": theme["supports_fields"]
        }
        for theme in EMAIL_TEMPLATE_THEMES.values()
    ]
