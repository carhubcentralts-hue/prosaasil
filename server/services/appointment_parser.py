"""
BUILD 200: Shared Appointment Information Parser
100% DYNAMIC - Works for ANY business type!

CRITICAL: No hardcoded business-specific values!
- Area patterns loaded dynamically from israeli_places.json
- All other field extraction is handled by AI prompts per business
- Business defines their own required fields in settings

This module ONLY provides:
1. Dynamic area/city extraction from JSON
2. Generic text utilities
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
    
    This is 100% dynamic - cities come from JSON, not hardcoded!
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
    """
    חילוץ אזור/עיר מטקסט - using dynamic patterns from JSON
    
    This is 100% dynamic - works for any business that needs city/area!
    """
    if not text:
        return ""
    
    text_lower = text.lower()
    area_patterns = _load_dynamic_area_patterns()
    
    for area_name, keywords in area_patterns.items():
        if any(keyword.lower() in text_lower for keyword in keywords):
            return area_name
    
    return ""


# 🔥 BUILD 200: REMOVED extract_property_type() function
# It contained hardcoded real estate terms (דירה, בית, משרד, דופלקס, פנטהאוז)
# Field extraction is now 100% handled by AI prompts per business

# 🔥 BUILD 200: REMOVED extract_budget() function  
# It contained hardcoded budget patterns (מיליון, אלף, ש"ח)
# Budget is a business-specific field - not all businesses need it

# 🔥 BUILD 200: REMOVED parse_appointment_info() function
# It returned property_type/budget which are real estate-specific
# Each business defines their own required fields in AI prompts


def parse_appointment_info_dynamic(text: str, required_fields: list = None) -> Dict[str, str]:
    """
    BUILD 200: 100% DYNAMIC appointment parsing
    
    Only extracts area (from dynamic JSON) - all other fields
    are extracted by the AI based on business-specific prompts.
    
    Args:
        text: Conversation text
        required_fields: Business-defined required fields (for logging only)
    
    Returns:
        Dict with area only - other fields come from AI/lead capture
    """
    result = {}
    
    # Area extraction is 100% dynamic from JSON
    area = extract_area(text)
    if area:
        result['area'] = area
    
    # Log for debugging
    if required_fields:
        print(f"[APPOINTMENT_PARSER] Business requires: {required_fields}")
        print(f"[APPOINTMENT_PARSER] Extracted area: {area or 'none'}")
        print(f"[APPOINTMENT_PARSER] Other fields extracted by AI prompt")
    
    return result
