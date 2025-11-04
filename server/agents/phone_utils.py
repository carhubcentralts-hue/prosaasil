"""
Phone number utilities for Israeli phone numbers
Handles normalization to E.164 format (+972...)
"""
import re
from typing import Optional


def normalize_il_phone(raw: Optional[str]) -> Optional[str]:
    """
    Normalize Israeli phone number to E.164 format (+972...)
    
    Args:
        raw: Raw phone number string (can be None, empty, or various formats)
        
    Returns:
        Normalized phone in E.164 format (+972...) or None if invalid
        
    Examples:
        "0501234567" -> "+972501234567"
        "050-123-4567" -> "+972501234567"
        "+972501234567" -> "+972501234567"
        "501234567" -> "+972501234567" (mobile without leading 0)
        "" -> None
        "UNKNOWN" -> None
    """
    if not raw:
        return None
    
    # Remove spaces, dashes, parentheses
    s = re.sub(r"[^\d+]", "", raw)
    
    # Already in E.164 format
    if s.startswith("+972"):
        return s if len(s) >= 12 else None  # +972 + at least 9 digits
    
    # Israeli format starting with 0
    if s.startswith("0"):
        # 0xx... -> +972x...
        if len(s) >= 9:  # 0 + 9 digits
            return "+972" + s[1:]
        return None
    
    # Mobile number without leading 0 (5xxxxxxxx)
    if s.isdigit() and len(s) == 9 and s.startswith("5"):
        return "+972" + s
    
    # Other digit-only formats
    if s.isdigit() and len(s) == 10 and s.startswith("05"):
        return "+972" + s[1:]
    
    # Can't normalize
    return None
