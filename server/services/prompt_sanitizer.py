"""
Prompt Sanitization Utility
Sanitizes all text that gets injected into OpenAI instructions to reduce moderation triggers.
"""
import re
import logging

logger = logging.getLogger(__name__)

def sanitize_prompt_text(text: str, max_length: int = 3000) -> dict:
    """
    Sanitize text for safe injection into OpenAI prompts.
    
    Removes:
    - URLs and domains
    - Repeated punctuation
    - ALL CAPS blocks
    - Control characters (RTL/LTR marks, unicode)
    - Long identifiers (UUIDs, IDs)
    
    Args:
        text: Raw text to sanitize
        max_length: Maximum length to keep (default 3000 chars)
        
    Returns:
        dict with:
            - sanitized_text: Cleaned text
            - flags: {has_url, has_email, has_phone} - boolean flags only (NO values logged)
    """
    if not text or not text.strip():
        return {
            "sanitized_text": "",
            "flags": {"has_url": False, "has_email": False, "has_phone": False}
        }
    
    original_text = text
    flags = {
        "has_url": False,
        "has_email": False,
        "has_phone": False
    }
    
    # Detect patterns (for flags only - don't log actual values)
    if re.search(r'https?://|www\.|\.com|\.co\.il', text, re.IGNORECASE):
        flags["has_url"] = True
    if re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text):
        flags["has_email"] = True
    # Israeli phone patterns
    if re.search(r'(\+?972[\s\-]?|0)5[0-9][\s\-]?[0-9]{3}[\s\-]?[0-9]{4}', text):
        flags["has_phone"] = True
    
    # 1. Remove URLs and domains
    text = re.sub(r'https?://[^\s]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'www\.[^\s]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b[a-zA-Z0-9.-]+\.(com|co\.il|org|net|edu|gov|io|info)\b', '', text, flags=re.IGNORECASE)
    
    # 2. Collapse repeated punctuation (!!! → !, ??? → ?, ... → .)
    text = re.sub(r'!{2,}', '!', text)
    text = re.sub(r'\?{2,}', '?', text)
    text = re.sub(r'\.{3,}', '.', text)
    text = re.sub(r',{2,}', ',', text)
    
    # 3. Normalize ALL CAPS blocks (more than 5 consecutive caps)
    # Keep first letter caps, lowercase the rest
    def normalize_caps(match):
        word = match.group(0)
        if len(word) > 5:
            return word[0] + word[1:].lower()
        return word
    
    text = re.sub(r'\b[A-Z]{6,}\b', normalize_caps, text)
    
    # 4. Remove control characters (RTL/LTR marks, zero-width characters)
    # Unicode categories: Cc (control), Cf (format), Cn (unassigned)
    text = re.sub(r'[\u200E\u200F\u202A-\u202E\u2066-\u2069\uFEFF\u00AD]', '', text)
    
    # 5. Remove long identifier patterns (UUIDs, long mixed alnum)
    # Match: 10+ chars with mixed letters and numbers (likely IDs)
    # CRITICAL: Don't match regular numbers like "2019" or "10"
    # Only match if there are BOTH letters AND numbers in sequence
    text = re.sub(r'\b(?=.*[a-zA-Z])(?=.*[0-9])[a-zA-Z0-9]{10,}\b', '', text)
    # UUID pattern specifically
    text = re.sub(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', '', text, flags=re.IGNORECASE)
    
    # 6. Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    # 7. Trim to max length (preserve sentence boundaries)
    if len(text) > max_length:
        # Try to cut at sentence boundary
        truncated = text[:max_length]
        last_period = truncated.rfind('.')
        last_question = truncated.rfind('?')
        last_exclamation = truncated.rfind('!')
        last_sentence = max(last_period, last_question, last_exclamation)
        
        if last_sentence > max_length * 0.8:  # If we found a sentence end in last 20%
            text = truncated[:last_sentence + 1]
        else:
            text = truncated + "..."
    
    return {
        "sanitized_text": text,
        "flags": flags
    }


def format_crm_context_safe(customer_name: str = None, 
                            email: str = None, 
                            phone: str = None,
                            notes: str = None,
                            include_contact_details: bool = False) -> str:
    """
    Format CRM context in natural language (non-technical, safe for moderation).
    
    Args:
        customer_name: Customer name
        email: Customer email (only included if include_contact_details=True)
        phone: Customer phone (only included if include_contact_details=True)
        notes: Additional notes
        include_contact_details: Whether to include email/phone (default False)
        
    Returns:
        Natural language CRM context string
    """
    parts = []
    
    # Always include name if available
    if customer_name and customer_name.strip():
        # Sanitize name
        clean_name = sanitize_prompt_text(customer_name, max_length=100)["sanitized_text"]
        if clean_name:
            parts.append(f"Customer name: {clean_name}.")
    
    # Contact details - only if explicitly requested
    if include_contact_details:
        if email and email.strip():
            parts.append("Customer email is available upon request.")
        if phone and phone.strip():
            parts.append("Customer phone is available upon request.")
    else:
        # Hint that details exist but don't include them
        if (email and email.strip()) or (phone and phone.strip()):
            parts.append("Contact details available if needed during the call.")
    
    # Notes - sanitize carefully
    if notes and notes.strip():
        clean_notes = sanitize_prompt_text(notes, max_length=200)["sanitized_text"]
        if clean_notes:
            parts.append(f"Notes: {clean_notes}")
    
    return " ".join(parts) if parts else ""
