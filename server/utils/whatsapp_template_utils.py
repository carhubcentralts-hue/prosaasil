"""
WhatsApp Template Rendering Utility

Provides reusable template rendering for WhatsApp messages with placeholder replacement.
Supports both English and Hebrew placeholders.
"""
import logging
import re

logger = logging.getLogger(__name__)


def render_whatsapp_template(text: str, lead, business) -> str:
    """
    Render WhatsApp message template with lead/business placeholders.
    
    This function replaces placeholders in WhatsApp messages with actual values
    from the lead and business objects. It handles both English and Hebrew placeholders,
    with fallbacks for missing data.
    
    Supported English placeholders:
    - {lead_name} - Lead's full name
    - {first_name} - Lead's first name only
    - {phone} - Lead's phone number
    - {business_name} - Business name
    
    Supported Hebrew placeholders (double braces for easier typing):
    - {{שם}} - Lead's full name
    - {{שם פרטי}} - Lead's first name
    - {{טלפון}} - Lead's phone number
    - {{עסק}} - Business name
    
    Args:
        text: Message text with placeholders
        lead: Lead object with name/phone fields
        business: Business object with name field
    
    Returns:
        str: Rendered message with placeholders replaced
    
    Examples:
        >>> render_whatsapp_template("Hi {first_name}!", lead, business)
        "Hi John!"
        
        >>> render_whatsapp_template("שלום {{שם פרטי}}", lead, business)
        "שלום יוחנן"
    """
    if not text:
        return text
    
    # Get lead name with fallback
    lead_full_name = lead.full_name or lead.name or 'Customer'
    
    # Extract first name with proper fallbacks
    if lead.first_name:
        lead_first_name = lead.first_name
    elif lead_full_name.strip() and lead_full_name != 'Customer':
        # Try to extract first word from full name
        name_parts = lead_full_name.split()
        lead_first_name = name_parts[0] if name_parts else 'Customer'
    else:
        lead_first_name = 'Customer'
    
    # Build replacement dictionary - English placeholders
    replacements = {
        '{lead_name}': lead_full_name,
        '{first_name}': lead_first_name,
        '{phone}': lead.phone_e164 or lead.phone_raw or '',
        '{business_name}': business.name if business else ''
    }
    
    # Hebrew placeholders (with double braces for easier typing)
    hebrew_replacements = {
        '{{שם}}': lead_full_name,
        '{{שם פרטי}}': lead_first_name,
        '{{טלפון}}': lead.phone_e164 or lead.phone_raw or '',
        '{{עסק}}': business.name if business else ''
    }
    
    # Apply replacements - Hebrew first (to handle {{}} before single {})
    rendered = text
    for placeholder, value in hebrew_replacements.items():
        rendered = rendered.replace(placeholder, str(value))
    
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, str(value))
    
    # Check for remaining placeholders and log warning
    remaining_placeholders = re.findall(r'\{[^}]+\}|\{\{[^}]+\}\}', rendered)
    if remaining_placeholders:
        logger.warning(
            f"[TEMPLATE] Unreplaced placeholders found: {remaining_placeholders} "
            f"in message: {text[:50]}..."
        )
        # Replace remaining placeholders with empty string to avoid sending them to customers
        for placeholder in remaining_placeholders:
            rendered = rendered.replace(placeholder, '')
    
    return rendered
