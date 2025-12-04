"""
BUILD 186: Shared Appointment Information Parser
100% DYNAMIC - No hardcoded city patterns!

Extracts area, property type, budget from conversation text.
City patterns loaded dynamically from israeli_places.json.
"""
import re
import json
import os
from typing import Dict, Set
from functools import lru_cache


@lru_cache(maxsize=1)
def _load_dynamic_area_patterns() -> Dict[str, list]:
    """
    BUILD 186: Load city patterns dynamically from israeli_places.json
    Returns dict mapping canonical name -> list of aliases
    """
    patterns = {}
    
    try:
        base_path = os.path.join(os.path.dirname(__file__), '..', 'data')
        cities_path = os.path.join(base_path, 'israeli_places.json')
        
        if os.path.exists(cities_path):
            with open(cities_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for city in data.get('cities', []):
                canonical = city.get('canonical', '')
                if canonical:
                    aliases = [canonical]
                    for alias in city.get('aliases', []):
                        if alias and alias not in aliases:
                            aliases.append(alias)
                    patterns[canonical] = aliases
    except Exception as e:
        print(f"[APPOINTMENT_PARSER] Warning: Could not load cities: {e}")
    
    return patterns


def extract_area(text: str) -> str:
    """חילוץ אזור מטקסט - using dynamic patterns from JSON"""
    if not text:
        return ""
    
    text_lower = text.lower()
    area_patterns = _load_dynamic_area_patterns()
    
    for area_name, keywords in area_patterns.items():
        if any(keyword.lower() in text_lower for keyword in keywords):
            return area_name
    
    return ""


def extract_property_type(text: str) -> str:
    """חילוץ סוג נכס מטקסט"""
    if not text:
        return ""
    
    room_match = re.search(r'(\d+)\s*חדרים?', text)
    if room_match:
        return f"דירת {room_match.group(1)} חדרים"
    
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
    BUILD 186: UNIFIED appointment parsing - 100% dynamic
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
