"""
Name normalization utilities for lead management
Cleans and validates names from various sources (WhatsApp, phone, manual)
"""
import re
import logging

logger = logging.getLogger(__name__)

# Names to reject (invalid or placeholder names)
INVALID_NAMES = {
    'unknown', 'whatsapp', 'user', 'customer', 'guest', 'לקוח', 'משתמש',
    'null', 'none', 'n/a', 'na', 'test', 'בדיקה'
}


def normalize_name(name: str) -> str:
    """
    Normalize a name from WhatsApp pushName or phone caller ID
    
    Rules:
    - Strip whitespace
    - Remove duplicate spaces
    - Limit length to 80 chars
    - Reject phone numbers
    - Reject placeholder names
    
    Args:
        name: Raw name string
        
    Returns:
        str: Normalized name or empty string if invalid
    """
    if not name:
        return ""
    
    # Convert to string and strip
    name = str(name).strip()
    
    # Remove duplicate whitespace
    name = re.sub(r'\s+', ' ', name)
    
    # Limit length
    if len(name) > 80:
        name = name[:80].strip()
    
    # Check if it's a phone number (digits only or starts with +)
    if re.match(r'^[\d\+\-\(\)\s]+$', name):
        logger.debug(f"Rejecting name that looks like phone number: {name}")
        return ""
    
    # Check if it's a placeholder/invalid name
    if name.lower() in INVALID_NAMES:
        logger.debug(f"Rejecting invalid placeholder name: {name}")
        return ""
    
    # Must have at least 2 characters
    if len(name) < 2:
        return ""
    
    return name


def is_name_better(new_name: str, old_name: str, new_source: str, old_source: str) -> bool:
    """
    Determine if a new name is "better" than an existing name
    
    Priority:
    1. Manual names are never overwritten
    2. Longer names are generally better (more info)
    3. Non-placeholder names are better than placeholders
    
    Args:
        new_name: New name candidate
        old_name: Existing name
        new_source: Source of new name ('whatsapp', 'call', 'manual')
        old_source: Source of existing name
        
    Returns:
        bool: True if new name should replace old name
    """
    # Never overwrite manual names
    if old_source == 'manual':
        logger.debug(f"Not overwriting manual name: {old_name}")
        return False
    
    # If no old name, new name is better
    if not old_name or not old_name.strip():
        return True
    
    # If new name is empty, don't replace
    if not new_name or not new_name.strip():
        return False
    
    # Manual source always wins
    if new_source == 'manual':
        return True
    
    # Check if old name is a default placeholder
    old_lower = old_name.lower()
    if any(placeholder in old_lower for placeholder in ['ליד חדש', 'lead', 'unknown', 'ללא שם']):
        # Any real name is better than placeholder
        logger.debug(f"Replacing placeholder name '{old_name}' with '{new_name}'")
        return True
    
    # Prefer longer names (more information)
    if len(new_name) > len(old_name):
        logger.debug(f"New name is longer ({len(new_name)} vs {len(old_name)})")
        return True
    
    # Otherwise keep existing name
    return False


def extract_pushname_from_whatsapp(msg: dict) -> str:
    """
    Extract and normalize pushName from WhatsApp message
    
    Args:
        msg: WhatsApp message dictionary
        
    Returns:
        str: Normalized name or empty string
    """
    push_name = msg.get('pushName', '')
    
    if not push_name or push_name == 'Unknown':
        return ""
    
    return normalize_name(push_name)
