"""
Shared Appointment Information Parser
Extracts area, property type, budget from conversation text
"""
import re
from typing import Dict

# ✅ Centralized area patterns - used by both phone and WhatsApp
AREA_PATTERNS = {
    'תל אביב': ['תל אביב', 'ת״א', 'דיזנגוף', 'פלורנטין', 'נווה צדק'],
    'רמת גן': ['רמת גן', 'רמ״ג', 'גבעתיים', 'הבורסה'],
    'הרצליה': ['הרצליה', 'פיתוח'],
    'פתח תקווה': ['פתח תקווה', 'פ״ת', 'פתח תקוה'],
    'רחובות': ['רחובות'],
    'מודיעין': ['מודיעין'],
    'בית שמש': ['בית שמש'],
    'לוד': ['לוד'],
    'רמלה': ['רמלה'],
    'ירושלים': ['ירושלים', 'יר״ן', 'י-ם'],
    'מעלה אדומים': ['מעלה אדומים']
}


def extract_area(text: str) -> str:
    """חילוץ אזור מטקסט"""
    if not text:
        return ""
    
    text_lower = text.lower()
    for area_name, keywords in AREA_PATTERNS.items():
        if any(keyword.lower() in text_lower for keyword in keywords):
            return area_name
    
    return ""


def extract_property_type(text: str) -> str:
    """חילוץ סוג נכס מטקסט"""
    if not text:
        return ""
    
    # חיפוש מספר חדרים
    room_match = re.search(r'(\d+)\s*חדרים?', text)
    if room_match:
        return f"דירת {room_match.group(1)} חדרים"
    
    # חיפוש כללי
    if any(word in text for word in ['דירה', 'בית']):
        return "דירה"
    elif 'משרד' in text:
        return "משרד"
    elif 'דופלקס' in text:
        return "דופלקס"
    elif 'פנטהאוז' in text:
        return "פנטהאוז"
    
    return ""


def extract_budget(text: str) -> str:
    """חילוץ תקציב מטקסט"""
    if not text:
        return ""
    
    # חיפוש סכומים: 1.5 מיליון, 500 אלף, וכו'
    budget_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:מיליון|אלף|k)', text, re.IGNORECASE)
    if budget_match:
        amount = budget_match.group(1)
        match_text = budget_match.group(0).lower()
        
        if 'מיליון' in match_text:
            unit = 'מיליון'
        elif 'k' in match_text:
            unit = 'אלף'
        else:
            unit = 'אלף'
        
        return f"{amount} {unit} ש״ח"
    
    return ""


def parse_appointment_info(text: str) -> Dict[str, str]:
    """
    ✅ UNIFIED: Single source of truth for appointment parsing
    Used by both phone and WhatsApp handlers
    
    Args:
        text: Conversation text (phone) or message (WhatsApp)
    
    Returns:
        Dict with area, property_type, budget
    """
    return {
        'area': extract_area(text),
        'property_type': extract_property_type(text),
        'budget': extract_budget(text)
    }
