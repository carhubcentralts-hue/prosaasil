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
        lead: Lead object with name/phone fields (must not be None)
        business: Business object with name field (can be None)
    
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
    
    if not lead:
        logger.warning("[TEMPLATE] Lead object is None - cannot render template")
        return text
    
    # Get lead name with fallback
    lead_full_name = getattr(lead, 'full_name', None) or getattr(lead, 'name', None) or 'Customer'
    
    # Extract first name with proper fallbacks
    lead_first_name = getattr(lead, 'first_name', None)
    if not lead_first_name:
        if lead_full_name.strip() and lead_full_name != 'Customer':
            # Try to extract first word from full name
            name_parts = lead_full_name.split()
            lead_first_name = name_parts[0] if name_parts else 'Customer'
        else:
            lead_first_name = 'Customer'
    
    # Build replacement dictionary - English placeholders
    replacements = {
        '{lead_name}': lead_full_name,
        '{first_name}': lead_first_name,
        '{phone}': getattr(lead, 'phone_e164', None) or getattr(lead, 'phone_raw', None) or '',
        '{business_name}': getattr(business, 'name', '') if business else ''
    }
    
    # Hebrew placeholders (with double braces for easier typing)
    hebrew_replacements = {
        '{{שם}}': lead_full_name,
        '{{שם פרטי}}': lead_first_name,
        '{{טלפון}}': getattr(lead, 'phone_e164', None) or getattr(lead, 'phone_raw', None) or '',
        '{{עסק}}': getattr(business, 'name', '') if business else ''
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
