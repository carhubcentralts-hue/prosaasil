"""
Phone Normalization Utility - Single Source of Truth
Use this everywhere for consistent phone number handling
"""
import re
from typing import Optional

def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Normalize phone number to consistent format.
    
    This is the SINGLE SOURCE OF TRUTH for phone normalization.
    Use this function everywhere in the codebase.
    
    Rules:
    1. Remove all spaces, dashes, parentheses
    2. Keep + and digits only
    3. For Israeli local numbers (starting with 0): convert to E.164 (+972...)
    4. For numbers starting with 972 without +: add +
    5. For numbers already in E.164 format: keep as-is
    6. For other international numbers with +: keep as-is
    
    Examples:
        "050-1234567" -> "+972501234567"
        "0501234567" -> "+972501234567"
        "972501234567" -> "+972501234567"
        "+972501234567" -> "+972501234567"
        "+1-555-1234567" -> "+15551234567"
        "555 123 4567" -> "5551234567" (no country code, keep as-is)
    
    Args:
        phone: Raw phone number string (can be None)
    
    Returns:
        Normalized phone number or None if input is invalid
    """
    if not phone:
        return None
    
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone.strip())
    
    if not cleaned:
        return None
    
    # Already in E.164 format with +972 (Israeli)
    if cleaned.startswith('+972'):
        # Validate length (should be +972 + 9 digits = 13 chars total)
        if len(cleaned) >= 12:  # At least +972 + some digits
            return cleaned
        return None
    
    # Has 972 prefix but missing + (Israeli)
    if cleaned.startswith('972') and len(cleaned) >= 12:
        return '+' + cleaned
    
    # Israeli local format (starts with 0)
    if cleaned.startswith('0') and len(cleaned) >= 10:
        # Remove leading 0 and add +972
        return '+972' + cleaned[1:]
    
    # Already has + for another country - keep as-is
    if cleaned.startswith('+'):
        return cleaned
    
    # Check if it's a 9-digit Israeli mobile without leading 0
    # Israeli mobiles start with 5 (050, 052, 053, 054, 055, 058)
    if len(cleaned) == 9 and cleaned[0] in ['5']:
        return '+972' + cleaned
    
    # For anything else without country code - return as-is
    # (might be internal extension, short code, etc.)
    return cleaned if len(cleaned) >= 7 else None


def phones_match(phone1: Optional[str], phone2: Optional[str]) -> bool:
    """
    Check if two phone numbers match after normalization.
    
    Args:
        phone1: First phone number
        phone2: Second phone number
    
    Returns:
        True if both numbers normalize to the same value
    """
    if not phone1 or not phone2:
        return False
    
    norm1 = normalize_phone(phone1)
    norm2 = normalize_phone(phone2)
    
    if not norm1 or not norm2:
        return False
    
    return norm1 == norm2


def get_phone_digits(phone: Optional[str]) -> Optional[str]:
    """
    Extract just the digits from a phone number (no + or country code).
    Useful for matching against databases that store phones inconsistently.
    
    Args:
        phone: Phone number
    
    Returns:
        Just the digits (last 10 for IL numbers)
    """
    if not phone:
        return None
    
    normalized = normalize_phone(phone)
    if not normalized:
        return None
    
    # Remove + and any leading country code
    digits = re.sub(r'[^\d]', '', normalized)
    
    # For Israeli numbers, get last 9-10 digits
    if normalized.startswith('+972'):
        return digits[-9:] if len(digits) >= 9 else digits
    
    return digits


# For backward compatibility - alias to the main function
normalize_il_phone = normalize_phone
normalize_israeli_phone = normalize_phone
