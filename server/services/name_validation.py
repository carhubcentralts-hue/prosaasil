"""
Name Validation - Single Source of Truth
==========================================

Centralized validation for customer names to prevent placeholder/invalid values.
This is the ONLY place where invalid name patterns are defined.

All name validation across the codebase should import from here.
"""

# 🔥 SINGLE SOURCE OF TRUTH: Invalid name placeholders
# This list is used across the entire codebase for name validation
INVALID_NAME_PLACEHOLDERS = {
    # ─── Generic Placeholders ───
    # Common placeholder values that are not real names
    'none', 'null', 'unknown', 'test', '-', 'n/a', 'na', 'n.a.', 'undefined',
    
    # ─── Hebrew Placeholders ───
    # ללא שם = "no name", לא ידוע = "unknown", אין שם = "no name", לקוח = "customer"
    'לא ידוע', 'ללא שם', 'אין שם', 'לקוח', 
    
    # ─── English Customer References ───
    # Generic role names, not individual identities
    'customer', 'client', 'user', 'guest',
    
    # ─── File/Folder Names ───
    # בית = "house/home", תמונה = "picture", מסמך = "document", קובץ/תיקיה = "file/folder"
    # These appear in file uploads but are not customer names
    'בית', 'תמונה', 'מסמך', 'קובץ', 'תיקיה', 'folder', 'file',
    
    # ─── Generic Name-Related Words ───
    # שם = "name", משתמש = "user" - meta words about names, not actual names
    'שם', 'name', 'משתמש',
    
    # ─── Test/Example Values ───
    # טסט/בדיקה/דוגמה = "test/check/example", אורח = "guest"
    # Common in QA/testing but not real customer names
    'טסט', 'בדיקה', 'דוגמה', 'example', 'אורח'
}


def is_valid_customer_name(name: str) -> bool:
    """
    Validate that customer name is real data, not a placeholder.
    
    This is the ONLY validation function for customer names.
    All code should use this instead of implementing their own checks.
    
    Args:
        name: The customer name to validate
        
    Returns:
        True if name is valid (not a placeholder), False otherwise
        
    Examples:
        >>> is_valid_customer_name("דני")
        True
        >>> is_valid_customer_name("ללא שם")
        False
        >>> is_valid_customer_name("")
        False
        >>> is_valid_customer_name("test")
        False
    """
    if not name or not isinstance(name, str):
        return False
    
    name_lower = name.strip().lower()
    if not name_lower:
        return False
    
    # Check against invalid placeholders
    if name_lower in INVALID_NAME_PLACEHOLDERS:
        return False
    
    return True
