"""
Phone number utilities for phone numbers (primarily Israeli)
Handles normalization to E.164 format (+972...)
"""
import re
from typing import Optional


def normalize_phone(raw: Optional[str]) -> Optional[str]:
    """
    Universal phone normalization function - Single source of truth for all phone numbers.
    Normalizes phone numbers to E.164 format (primarily Israeli +972..., but handles others).
    
    This function MUST be used for ALL phone number inputs from ANY source:
    - WhatsApp inbound/outbound
    - Twilio inbound/outbound  
    - Manual lead creation
    - Imported leads
    
    Args:
        raw: Raw phone number string (can be None, empty, or various formats)
        
    Returns:
        Normalized phone in E.164 format (+...) or None if invalid
        
    Examples:
        Israeli numbers:
        "0501234567" -> "+972501234567"
        "050-123-4567" -> "+972501234567"
        "+972501234567" -> "+972501234567"
        "972501234567" -> "+972501234567"
        "501234567" -> "+972501234567"
        
        International:
        "+1234567890" -> "+1234567890"
        "1234567890" -> "+1234567890" (if 10+ digits, assume E.164)
        
        Invalid:
        "" -> None
        "UNKNOWN" -> None
        "abc123" -> None
    """
    if not raw:
        return None
    
    # Remove spaces, dashes, parentheses, and other non-digit characters (except +)
    s = re.sub(r"[^\d+]", "", raw)
    
    # Empty after cleanup
    if not s or s == '+':
        return None
    
    # Already in E.164 format (starts with +)
    if s.startswith("+"):
        # Must have at least 8 digits after + (minimum valid international number)
        if len(s) >= 9:  # + plus at least 8 digits
            return s
        return None
    
    # 🔥 Israeli format: 972 without + prefix (e.g., "972501234567")
    if s.startswith("972") and len(s) >= 12:
        return "+" + s
    
    # 🔥 Israeli format: starting with 0 (local format)
    if s.startswith("0"):
        # Israeli local: 0xx... -> +972xx...
        if len(s) >= 9:  # 0 + at least 8 digits
            return "+972" + s[1:]
        return None
    
    # 🔥 Israeli mobile: 9 digits starting with 5 (mobile without leading 0)
    if s.isdigit() and len(s) == 9 and s.startswith("5"):
        return "+972" + s
    
    # 🔥 Israeli mobile: 10 digits starting with 05
    if s.isdigit() and len(s) == 10 and s.startswith("05"):
        return "+972" + s[1:]
    
    # 🔥 International format: Any other digits-only format with 10+ digits
    # Assume it's E.164 without + prefix
    if s.isdigit() and len(s) >= 10:
        return "+" + s
    
    # Can't normalize - invalid format
    return None


# Backward compatibility alias
def normalize_il_phone(raw: Optional[str]) -> Optional[str]:
    """
    Legacy alias for normalize_phone().
    Kept for backward compatibility with existing code.
    New code should use normalize_phone() directly.
    """
    return normalize_phone(raw)
