"""
Prompt Hashing - Single Source of Truth
========================================

Centralized hashing for prompt de-duplication.
Ensures consistent normalization and hash calculation across all injection points.
"""

import hashlib
import re


def hash_prompt(text: str, normalize: bool = True) -> str:
    """
    Calculate consistent hash fingerprint for prompt de-duplication.
    
    This is the ONLY function for hashing prompts in the system.
    All injection guards should use this to prevent duplicates.
    
    Args:
        text: The prompt text to hash
        normalize: Whether to normalize text before hashing (default: True)
                  Normalization removes whitespace variations, line ending differences,
                  and dynamic content like dates that shouldn't affect deduplication.
    
    Returns:
        8-character MD5 hash (short form)
        
    Examples:
        >>> hash_prompt("Hello World")
        'b10a8db1'
        >>> hash_prompt("Hello World  ")  # Same hash (normalized)
        'b10a8db1'
        >>> hash_prompt("Hello\\nWorld")  # Same hash (normalized)
        'b10a8db1'
    """
    if not text:
        return "00000000"
    
    if normalize:
        text = _normalize_for_hash(text)
    
    try:
        return hashlib.md5(text.encode('utf-8')).hexdigest()[:8]
    except Exception:
        # Fallback for encoding errors
        return hashlib.md5(str(text).encode('utf-8', errors='ignore')).hexdigest()[:8]


def _normalize_for_hash(text: str) -> str:
    """
    Normalize text for consistent hash calculation.
    
    Removes:
    - Leading/trailing whitespace
    - Line ending variations (\r\n → \n)
    - Dynamic content (TODAY_ISO, TODAY_WEEKDAY_HE, TIMEZONE)
    - Excessive whitespace
    
    This ensures that cosmetic changes don't trigger false duplicates.
    """
    if not text:
        return ""
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    # Normalize line endings (\r\n → \n)
    text = text.replace('\r\n', '\n')
    
    # Remove dynamic elements that change per call
    # These are runtime facts, not structural content
    text = re.sub(r'Context:\s*TODAY_ISO=[^\s]+\.?\s*', '', text)
    text = re.sub(r'TODAY_WEEKDAY_HE=[^\s]+\.?\s*', '', text)
    text = re.sub(r'TIMEZONE=[^\s\.]+\.?\s*', '', text)
    
    # Remove any remaining "Context: " prefix if empty
    text = re.sub(r'\s*Context:\s*\.?\s*', '', text)
    
    # Collapse multiple spaces to single space
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()
