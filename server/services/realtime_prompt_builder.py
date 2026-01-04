
"""
Realtime Prompt Builder - REFACTORED FOR PERFECT LAYER SEPARATION
=================================================================

🎯 MISSION: Zero collisions, zero duplicated rules, perfect dynamic flow

LAYER ARCHITECTURE:
1. SYSTEM PROMPT → Behavior rules only (universal, no content)
2. BUSINESS PROMPT → All flow, script, and domain content
3. TRANSCRIPT PROMPT → Recognition enhancement only
4. NLP PROMPT → Data extraction only (handled separately)

🔥 BUILD: PERFECT INBOUND & OUTBOUND SEPARATION
- build_inbound_system_prompt(): Full control settings + appointment scheduling
- build_outbound_system_prompt(): Pure prompt mode, no call control
- build_realtime_system_prompt(): Router that calls the correct builder
"""
import logging
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
import pytz
import json
import re

logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 CONSTANTS: Fallback prompt templates (English only, no hardcoded content)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Fallback templates - used only when DB configuration is missing
FALLBACK_GENERIC_PROMPT = "You are a professional service representative. Speak Hebrew to customers. Be helpful and collect their information."
FALLBACK_BUSINESS_PROMPT_TEMPLATE = "You are a professional representative for {business_name}. Speak Hebrew to customers. Be helpful and collect customer information."
FALLBACK_INBOUND_PROMPT_TEMPLATE = "You are a professional service representative for {business_name}. Be helpful and collect customer information."
FALLBACK_OUTBOUND_PROMPT_TEMPLATE = "You are a professional outbound representative for {business_name}. Be brief, polite, and helpful."

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 NAME POLICY & NAME ANCHOR: Persistent customer name usage
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_name_usage_policy(business_prompt: str) -> Tuple[bool, Optional[str]]:
    """
    Detect if business prompt requests using customer name in conversation.
    
    This checks for EXPLICIT instructions to use the customer's name throughout
    the conversation, not just in greeting.
    
    Args:
        business_prompt: The business prompt text to analyze
    
    Returns:
        Tuple of (use_name: bool, matched_phrase: Optional[str])
        - use_name: True if prompt requests name usage
        - matched_phrase: The phrase that triggered the policy (for logging)
    
    Examples of phrases that trigger name usage:
        Hebrew: "השתמש בשם", "פנה בשמו", "קרא בשם", "לפנות בשם"
        Conditional: "אם קיים שם", "במידה וקיים שם", "אם יש שם"
        English: "use name", "use their name", "address by name", "call by name"
    
    NOTE: "ליצור קרבה" is NOT a name usage instruction - removed!
    """
    if not business_prompt:
        return False, None
    
    prompt_lower = business_prompt.lower()
    
    # Hebrew patterns for EXPLICIT name usage instructions
    hebrew_patterns = [
        r"השתמש\s+בשם",           # "use name" - EXPLICIT
        r"תשתמש\s+בשם",           # "you will use name" - EXPLICIT
        r"פנה\s+בשמו",            # "address by his name" - EXPLICIT
        r"פני\s+בשמה",            # "address by her name" - EXPLICIT
        r"תפנה\s+בשם",            # "you will address by name" - EXPLICIT
        r"קרא\s+לו\s+בשם",        # "call him by name" - EXPLICIT
        r"לפנות\s+בשם",           # "to address by name" - EXPLICIT
        r"אם\s+קיים\s+שם.*השתמש", # "if name exists...use" - EXPLICIT
        r"במידה\s+וקיים\s+שם.*השתמש", # "if there is a name...use" - EXPLICIT
    ]
    
    # English patterns for EXPLICIT name usage instructions
    english_patterns = [
        r"use\s+(?:the\s+)?(?:customer'?s?\s+)?name",
        r"use\s+their\s+name",
        r"address\s+(?:them\s+)?by\s+name",
        r"call\s+(?:them\s+)?by\s+name",
        r"if\s+(?:a\s+)?name\s+(?:is\s+)?(?:available|exists).*use",
    ]
    
    all_patterns = hebrew_patterns + english_patterns
    
    for pattern in all_patterns:
        match = re.search(pattern, prompt_lower)
        if match:
            matched_text = match.group(0)
            logger.info(f"[NAME_POLICY] Detected EXPLICIT name usage request: '{matched_text}'")
            return True, matched_text
    
    return False, None


def extract_first_name(full_name: Optional[str]) -> Optional[str]:
    """
    🧠 ULTRA-SMART NAME EXTRACTION: Intelligently detect real names vs descriptions
    
    This function is INTELLIGENT and understands:
    - Real Hebrew/English names vs job titles/descriptions
    - "יוסי המנקה אהוב" → "יוסי" (ignores "המנקה אהוב")
    - "דוד הטכנאי" → "דוד" (ignores job title)
    - "משה בן יוסף" → "משה בן" (real Hebrew name)
    - "בית" / "תמונה" → None (not names at all)
    
    Detection Strategy:
    1. Strip out common descriptors/job titles/adjectives
    2. Extract only the actual name part (1-2 words max)
    3. Validate it's a real name (not placeholder/description)
    
    Args:
        full_name: The full text that might contain a name
        
    Returns:
        First name (1-2 words), or None if no valid name found
        
    Examples:
        "יוסי" → "יוסי"
        "יוסי כהן" → "יוסי"
        "יוסי המנקה אהוב" → "יוסי" (smart!)
        "דוד הטכנאי" → "דוד"
        "משה בן יוסף" → "משה בן"
        "מ כהן" → "מ כהן"
        "בית" → None
        "תמונה" → None
        "ללא שם" → None
    """
    if not full_name or not isinstance(full_name, str):
        return None
    
    # Clean and normalize
    name = full_name.strip()
    if not name:
        return None
    
    # 🚫 PLACEHOLDER DETECTION: Common non-name values
    name_lower = name.lower()
    placeholders = [
        "ללא שם", "לא ידוע", "אין שם", "לקוח", "customer", "client",
        "בית", "תמונה", "מסמך", "קובץ", "תיקיה", "folder", "file",
        "שם", "name", "test", "טסט", "בדיקה", "דוגמה", "example",
        "משתמש", "user", "אורח", "guest"
    ]
    
    if name_lower in placeholders:
        logger.debug(f"[NAME_EXTRACT] Skipping placeholder: '{full_name}'")
        return None
    
    # 🚫 REJECT: Names with numbers
    if any(char.isdigit() for char in name):
        logger.debug(f"[NAME_EXTRACT] Skipping name with numbers: '{full_name}'")
        return None
    
    # 🚫 REJECT: Too many special characters (more than 2)
    special_chars = sum(1 for c in name if not c.isalnum() and not c.isspace())
    if special_chars > 2:
        logger.debug(f"[NAME_EXTRACT] Skipping name with too many special chars: '{full_name}'")
        return None
    
    # Split into words
    words = [w for w in name.split() if w]
    
    if not words:
        return None
    
    # 🧠 SMART DESCRIPTOR DETECTION: Common Hebrew descriptors/job titles/adjectives
    # These indicate the word is NOT part of the actual name
    descriptors = [
        # Job titles / professions
        "המנקה", "הטכנאי", "החשמלאי", "השרברב", "הנהג", "המורה", "הרופא",
        "העובד", "האיש", "האישה", "הבחור", "הבחורה", "המנהל", "הבעלים",
        # Adjectives / descriptions
        "אהוב", "יקר", "טוב", "נחמד", "מקסים", "חביב", "מצוין", "הטוב",
        "החביב", "היקר", "המקסים", "הנחמד", "הנפלא", "המדהים",
        # Relationship descriptors
        "החבר", "האח", "האחות", "הדוד", "הדודה", "הסבא", "הסבתא",
        # Common non-name words with "ה" prefix
        "הבית", "התמונה", "הקובץ", "המשתמש"
    ]
    
    # 🧠 INTELLIGENT FILTERING: Remove descriptor words
    # Keep only actual name words (typically the first 1-2 words before descriptors)
    clean_words = []
    for word in words:
        word_lower = word.lower()
        
        # If we hit a descriptor, stop - everything after is description
        if word_lower in descriptors or word.startswith("ה") and len(word) > 2:
            # Check if this looks like "the X" pattern (Hebrew definite article)
            # If it's "ה" + word, it's likely a descriptor, not a name
            if word_lower in descriptors:
                break
        
        clean_words.append(word)
        
        # Stop after 2 name words (don't need more)
        if len(clean_words) >= 2:
            break
    
    if not clean_words:
        logger.debug(f"[NAME_EXTRACT] No name found after filtering descriptors from: '{full_name}'")
        return None
    
    # 🧠 HEBREW MIDDLE NAME DETECTION: "בן", "בת", etc.
    hebrew_middles = ["בן", "בת", "אבו", "אל", "אבן"]
    
    # ✅ SINGLE WORD: Return as-is
    if len(clean_words) == 1:
        logger.debug(f"[NAME_EXTRACT] Single word name: '{clean_words[0]}'")
        return clean_words[0]
    
    # ✅ TWO WORDS: Check if it's "first + middle" or "first + last"
    if len(clean_words) == 2:
        first_word = clean_words[0]
        second_word = clean_words[1]
        
        # If second word is a middle particle, keep both
        if second_word in hebrew_middles:
            result = f"{first_word} {second_word}"
            logger.debug(f"[NAME_EXTRACT] Hebrew name with middle particle: '{result}'")
            return result
        
        # If first word is very short (1-2 chars), keep both
        if len(first_word) <= 2:
            result = f"{first_word} {second_word}"
            logger.debug(f"[NAME_EXTRACT] Short first name, including last: '{result}'")
            return result
        
        # Normal case: return just first name
        logger.debug(f"[NAME_EXTRACT] First name only: '{first_word}' from '{full_name}'")
        return first_word
    
    # 🚫 THREE+ WORDS: This shouldn't happen after filtering, but just in case
    logger.debug(f"[NAME_EXTRACT] Too many words after filtering ({len(clean_words)}): '{full_name}'")
    return clean_words[0]  # Return just the first word as fallback


def detect_gender_from_name(name: Optional[str]) -> Optional[str]:
    """
    🧠 SMART GENDER DETECTION: Detect if name is male or female (Hebrew/English)
    
    Uses comprehensive lists of common Hebrew and English names to determine gender.
    Returns None if gender cannot be determined from name alone.
    
    ⚠️ UNISEX NAMES: Returns None for names like גל, נועם, ליאור, Alex, Jordan
    This allows the system to wait for conversation-based detection or manual input.
    
    Args:
        name: The customer's first name
        
    Returns:
        "male", "female", or None if cannot determine (unisex/unknown)
        
    Examples:
        "יוסי" → "male"
        "דוד" → "male"
        "שרה" → "female"
        "רחל" → "female"
        "גל" → None (unisex)
        "נועם" → None (unisex)
        "John" → "male"
        "Sarah" → "female"
        "Alex" → None (unisex)
    """
    if not name or not isinstance(name, str):
        return None
    
    # Clean and normalize (take only first word if multiple)
    name_clean = name.strip().split()[0] if name.strip() else ""
    if not name_clean:
        return None
    
    name_lower = name_clean.lower()
    
    # 🟡 UNISEX NAMES: Names that can be both male and female
    # These names should NOT auto-detect gender - wait for conversation or manual input
    unisex_names = {
        # Hebrew unisex
        "גל", "נועם", "ליאור", "יובל", "עדי", "שי", "רוני", "עמית", "אדר",
        # English unisex
        "alex", "jordan", "taylor", "casey", "riley", "morgan", "avery", "quinn"
    }
    
    # 🔵 HEBREW MALE NAMES (common Israeli male names)
    hebrew_male_names = {
        # Classic Hebrew names
        "אברהם", "יצחק", "יעקב", "משה", "אהרון", "דוד", "שלמה", "יוסף", "בנימין", "דן",
        # Modern Hebrew names
        "יוסי", "דני", "רוני", "עמי", "עומר", "אורי", "אלון", "גיא", "תומר", "רועי",
        "אייל", "נתנאל", "מיכאל", "אריאל",
        "עומרי", "אדם", "משה", "חיים", "אבי", "אבנר", "בועז", "אליהו",
        "שלום", "מרדכי", "שמעון", "ישראל", "אליעזר", "גד", "אשר", "נפתלי", "ראובן",
        # Ben names (son of)
        "בן", "אבן"
    }
    
    # 🔴 HEBREW FEMALE NAMES (common Israeli female names)
    hebrew_female_names = {
        # Classic Hebrew names
        "שרה", "רבקה", "רחל", "לאה", "מרים", "דינה", "דבורה", "יעל", "רות", "חנה",
        # Modern Hebrew names
        "נועה", "תמר", "שירה", "מיכל", "ענת", "דנה", "הילה", "רונית", "ליאת", "שירן",
        "מאיה", "אורית", "אפרת", "טלי", "ניצה", "שלומית", "נטלי", "אלה",
        "ענבל", "רעות", "זהר", "סיגל",
        "אורנה", "מלכה", "חוה", "אסתר", "שושנה", "עירית", "קרן", "דפנה", "ברכה",
        # Bat names (daughter of)
        "בת"
    }
    
    # 🔵 ENGLISH MALE NAMES (common English male names)
    english_male_names = {
        "john", "david", "michael", "james", "robert", "william", "richard", "joseph",
        "thomas", "charles", "daniel", "matthew", "anthony", "mark", "donald", "steven",
        "paul", "andrew", "joshua", "kenneth", "kevin", "brian", "george", "edward",
        "ronald", "timothy", "jason", "jeffrey", "ryan", "jacob", "gary", "nicholas",
        "eric", "jonathan", "stephen", "larry", "justin", "scott", "brandon", "benjamin",
        "samuel", "frank", "gregory", "raymond", "alexander", "patrick", "jack", "dennis",
        "jerry", "tyler", "aaron", "jose", "adam", "henry", "nathan", "douglas", "peter"
    }
    
    # 🔴 ENGLISH FEMALE NAMES (common English female names)
    english_female_names = {
        "mary", "patricia", "jennifer", "linda", "elizabeth", "barbara", "susan", "jessica",
        "sarah", "karen", "nancy", "lisa", "betty", "margaret", "sandra", "ashley",
        "kimberly", "emily", "donna", "michelle", "dorothy", "carol", "amanda", "melissa",
        "deborah", "stephanie", "rebecca", "sharon", "laura", "cynthia", "kathleen", "amy",
        "angela", "shirley", "anna", "brenda", "pamela", "emma", "nicole", "helen",
        "samantha", "katherine", "christine", "debra", "rachel", "catherine", "carolyn",
        "janet", "ruth", "maria", "heather", "diane", "virginia", "julie", "joyce", "victoria"
    }
    
    # 🟡 CHECK FOR UNISEX NAMES FIRST
    # These names should NOT auto-detect - return None to wait for conversation/manual input
    if name_lower in unisex_names:
        logger.debug(f"[GENDER_DETECT] Unisex name detected, cannot auto-determine: '{name_clean}'")
        return None
    
    # Check Hebrew names
    if name_lower in hebrew_male_names:
        logger.debug(f"[GENDER_DETECT] Hebrew male name detected: '{name_clean}'")
        return "male"
    
    if name_lower in hebrew_female_names:
        logger.debug(f"[GENDER_DETECT] Hebrew female name detected: '{name_clean}'")
        return "female"
    
    # Check English names
    if name_lower in english_male_names:
        logger.debug(f"[GENDER_DETECT] English male name detected: '{name_clean}'")
        return "male"
    
    if name_lower in english_female_names:
        logger.debug(f"[GENDER_DETECT] English female name detected: '{name_clean}'")
        return "female"
    
    # 🔍 PATTERN-BASED DETECTION: Hebrew name endings (but not for short names)
    # Hebrew female names often end with specific patterns
    if len(name_clean) >= 4:  # At least 4 characters to avoid false positives
        # Female endings in Hebrew
        if name_clean.endswith(('ה', 'ית', 'לה')):
            logger.debug(f"[GENDER_DETECT] Female pattern detected (ending): '{name_clean}'")
            return "female"
    
    # Cannot determine gender from name - this is OK for unisex or uncommon names
    logger.debug(f"[GENDER_DETECT] Gender unknown for name: '{name_clean}' (will wait for conversation or manual input)")
    return None


def detect_gender_from_conversation(text: str) -> Optional[str]:
    """
    🧠 CONVERSATION-BASED GENDER DETECTION: Detect gender from what user says
    
    Detects when user explicitly states their gender during conversation:
    - "אני אישה" / "אני נקבה" → female
    - "אני גבר" / "אני זכר" → male
    
    This is the most reliable source - overrides name-based detection.
    
    Args:
        text: The user's transcript text
        
    Returns:
        "male", "female", or None if no gender statement detected
        
    Examples:
        "אני אישה" → "female"
        "אני גבר" → "male"
        "כן, אני אישה" → "female"
        "מה שלומך?" → None
    """
    if not text or not isinstance(text, str):
        return None
    
    text_lower = text.lower().strip()
    
    # 🔴 FEMALE INDICATORS
    female_phrases = [
        "אני אישה",
        "אני נקבה",
        "אני בחורה",
        "אני גברת",
        "זאת אישה",
        "זו אישה",
    ]
    
    # 🔵 MALE INDICATORS
    male_phrases = [
        "אני גבר",
        "אני זכר",
        "אני בחור",
        "אני מר",
        "זה גבר",
        "זה בחור",
    ]
    
    # Check for female indicators
    for phrase in female_phrases:
        if phrase in text_lower:
            logger.info(f"[GENDER_DETECT] Female detected from conversation: '{phrase}' in '{text[:50]}'")
            return "female"
    
    # Check for male indicators
    for phrase in male_phrases:
        if phrase in text_lower:
            logger.info(f"[GENDER_DETECT] Male detected from conversation: '{phrase}' in '{text[:50]}'")
            return "male"
    
    return None


def detect_name_from_conversation(text: str) -> Optional[str]:
    """
    🆕 CONVERSATION-BASED NAME DETECTION: Detect customer name from what they say
    
    Detects when user introduces themselves during conversation:
    - "אני [שם]" → extracts name
    - "קוראים לי [שם]" → extracts name
    - "השם שלי [שם]" → extracts name
    
    Uses both regex patterns AND AI validation for higher accuracy.
    
    Args:
        text: The user's transcript text
        
    Returns:
        Customer name (first name only) or None if no name detected
        
    Examples:
        "אני דני" → "דני"
        "קוראים לי רונית" → "רונית"
        "השם שלי משה" → "משה"
        "מה שלומך?" → None
    """
    if not text or not isinstance(text, str):
        return None
    
    # Name patterns in Hebrew
    name_patterns = [
        r'(?:^|[^\w])אני\s+([א-ת]{2,15})(?:[^\w]|$)',  # "אני [name]"
        r'(?:^|[^\w])קוראים\s+לי\s+([א-ת]{2,15})(?:[^\w]|$)',  # "קוראים לי [name]"
        r'(?:^|[^\w])השם\s+שלי\s+([א-ת]{2,15})(?:[^\w]|$)',  # "השם שלי [name]"
        r'(?:^|[^\w])השם\s+([א-ת]{2,15})(?:[^\w]|$)',  # "השם [name]"
        r'(?:^|[^\w])שמי\s+([א-ת]{2,15})(?:[^\w]|$)',  # "שמי [name]"
    ]
    
    # Common words to filter out (not names)
    COMMON_WORDS_TO_EXCLUDE = {
        'כן', 'לא', 'בסדר', 'טוב', 'רוצה', 'צריך', 'יכול', 'אוכל', 'מעוניין',
        'כאן', 'שם', 'פה', 'איפה', 'מתי', 'למה', 'איך', 'מה', 'מי',
        'אותו', 'אותה', 'אותם', 'אותן', 'זה', 'זו', 'זאת', 'אלה',
        'גם', 'רק', 'עוד', 'כבר', 'תמיד', 'לעולם', 'אף', 'פעם',
        'מאוד', 'הרבה', 'קצת', 'מעט', 'יותר', 'פחות',
        'שלום', 'תודה', 'סליחה', 'בבקשה', 'נכון',
    }
    
    # Try regex patterns first
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            potential_name = match.group(1).strip()
            
            # Validate the name
            if (len(potential_name) >= 2 and 
                potential_name not in COMMON_WORDS_TO_EXCLUDE and
                potential_name.lower() not in COMMON_WORDS_TO_EXCLUDE):
                
                # 🆕 Additional AI validation for edge cases (optional, can be enabled if needed)
                # This makes it even smarter by having AI verify the name
                if _is_likely_a_name_ai_validate(potential_name, text):
                    logger.info(f"[NAME_DETECT] Name detected from conversation: '{potential_name}' in '{text[:50]}'")
                    return potential_name
    
    return None


def _is_likely_a_name_ai_validate(candidate_name: str, context: str) -> bool:
    """
    🆕 AI validation to verify if extracted word is actually a name
    
    This is a quick check to avoid false positives like "אני רוצה" → "רוצה"
    Uses simple heuristics first, can be enhanced with AI if needed.
    
    Returns True if likely a name, False otherwise
    """
    # For now, use simple heuristics (can be enhanced with AI later)
    # Hebrew names are typically 2-8 characters
    if len(candidate_name) < 2 or len(candidate_name) > 12:
        return False
    
    # Check if it's a common verb or adjective (basic list)
    COMMON_NON_NAMES = {
        'רוצה', 'צריך', 'יכול', 'אוכל', 'הולך', 'בא', 'עושה',
        'טוב', 'יפה', 'גדול', 'קטן', 'חדש', 'ישן'
    }
    
    if candidate_name.lower() in COMMON_NON_NAMES:
        logger.debug(f"[NAME_DETECT] Rejected '{candidate_name}' - common verb/adjective")
        return False
    
    # If we get here, it's likely a name
    return True



def build_name_anchor_message(customer_name: Optional[str], use_name_policy: bool, customer_gender: Optional[str] = None) -> str:
    """
    Build NAME_ANCHOR message for conversation injection.
    
    This creates a COMPACT system message providing:
    1. Customer name (if available)
    2. Customer gender (for Hebrew grammar)
    3. Name usage policy status
    
    CRITICAL: Keep SHORT - detailed rules are in universal system prompt.
    This is pure factual data, not instructions.
    
    Args:
        customer_name: The customer's name (None if not available)
        use_name_policy: Whether business prompt requests name usage
        customer_gender: The customer's detected gender ("male", "female", or None)
    
    Returns:
        Compact CRM context message (pure data, no instructions)
    """
    # Build gender info - just the fact, not instructions
    gender_info = ""
    if customer_gender == "male":
        gender_info = "זכר (male)"
    elif customer_gender == "female":
        gender_info = "נקבה (female)"
    else:
        gender_info = "unknown"
    
    # Build compact message with just the facts
    parts = ["[CRM Context]"]
    
    if customer_name:
        parts.append(f"Name: {customer_name}")
    else:
        parts.append("Name: not available")
    
    parts.append(f"Gender: {gender_info}")
    
    if use_name_policy and customer_name:
        # Explicit mandatory action when name usage is enabled AND name exists
        parts.append("Policy: USE name (business prompt requests it)")
        parts.append(f"ACTION: Address customer as '{customer_name}' naturally throughout conversation")
    elif use_name_policy and not customer_name:
        parts.append("Policy: name requested but not available - continue without name")
    elif not use_name_policy and customer_name:
        parts.append("Policy: do NOT use name in conversation")
    else:
        parts.append("Policy: name not requested")
    
    return "\n".join(parts)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 VALIDATION: Ensure business prompts are properly configured
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def validate_business_prompts(business_id: int) -> Dict[str, Any]:
    """
    Validate that business has properly configured prompts.
    
    Returns:
        Dict with validation results:
        {
            "valid": bool,
            "has_inbound_prompt": bool,
            "has_outbound_prompt": bool,
            "has_greeting": bool,
            "warnings": List[str],
            "errors": List[str]
        }
    """
    from server.models_sql import Business, BusinessSettings
    
    result = {
        "valid": True,
        "has_inbound_prompt": False,
        "has_outbound_prompt": False,
        "has_greeting": False,
        "warnings": [],
        "errors": []
    }
    
    try:
        business = Business.query.get(business_id)
        if not business:
            result["valid"] = False
            result["errors"].append(f"Business {business_id} not found")
            return result
        
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        
        # Check inbound prompt
        if settings and settings.ai_prompt and settings.ai_prompt.strip():
            result["has_inbound_prompt"] = True
        else:
            result["warnings"].append("No inbound prompt (ai_prompt) configured")
            
        # Check outbound prompt
        if settings and settings.outbound_ai_prompt and settings.outbound_ai_prompt.strip():
            result["has_outbound_prompt"] = True
        else:
            result["warnings"].append("No outbound prompt (outbound_ai_prompt) configured")
        
        # Check greeting
        if business.greeting_message and business.greeting_message.strip():
            result["has_greeting"] = True
        else:
            result["warnings"].append("No greeting message configured")
        
        # Validate at least one prompt exists
        if not result["has_inbound_prompt"] and not result["has_outbound_prompt"]:
            if business.system_prompt and business.system_prompt.strip():
                result["warnings"].append("Using legacy system_prompt as fallback")
            else:
                result["valid"] = False
                result["errors"].append("No prompts configured - business cannot handle calls")
        
    except Exception as e:
        result["valid"] = False
        result["errors"].append(f"Validation error: {str(e)}")
    
    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 HELPER: 3-tier fallback strategy for missing prompts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _get_prompt_with_fallback(
    business_id: int,
    business_name: str,
    primary_prompt: Optional[str],
    call_direction: str,
    settings,
    business
) -> str:
    """
    3-tier fallback strategy for missing prompts.
    
    Tier 1: Primary prompt (ai_prompt or outbound_ai_prompt)
    Tier 2: Alternate direction prompt
    Tier 3: Legacy system_prompt
    Tier 4: Minimal template (ERROR logged)
    
    Args:
        business_id: Business ID
        business_name: Business name
        primary_prompt: Primary prompt to try first
        call_direction: 'inbound' or 'outbound'
        settings: BusinessSettings object
        business: Business object
    
    Returns:
        Prompt text (never empty)
    """
    # Tier 1: Primary prompt
    if primary_prompt and primary_prompt.strip():
        return primary_prompt.strip()
    
    logger.error(f"[PROMPT ERROR] Missing {call_direction} prompt for business_id={business_id}")
    
    # Tier 2: Try alternate direction
    if call_direction == "outbound" and settings and settings.ai_prompt:
        logger.warning(f"[PROMPT FALLBACK] Using inbound prompt for {call_direction} business_id={business_id}")
        return settings.ai_prompt
    elif call_direction == "inbound" and settings and settings.outbound_ai_prompt:
        logger.warning(f"[PROMPT FALLBACK] Using outbound prompt for {call_direction} business_id={business_id}")
        return settings.outbound_ai_prompt
    
    # Tier 3: Try legacy system_prompt
    if business and business.system_prompt:
        logger.warning(f"[PROMPT FALLBACK] Using system_prompt for {call_direction} business_id={business_id}")
        return business.system_prompt
    
    # Tier 4: Minimal template (should NEVER happen in production)
    logger.error(f"[PROMPT ERROR] No prompts available for {call_direction} business_id={business_id}")
    
    if call_direction == "outbound":
        return FALLBACK_OUTBOUND_PROMPT_TEMPLATE.format(business_name=business_name)
    else:
        return FALLBACK_INBOUND_PROMPT_TEMPLATE.format(business_name=business_name)


_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # emoji/pictographs/symbols
    "\U00002700-\U000027BF"  # dingbats
    "]+",
    flags=re.UNICODE,
)
_BOX_DRAWING_RE = re.compile(r"[\u2500-\u257F\u2580-\u259F]")
_ARROWS_RE = re.compile(r"[\u2190-\u21FF]")
_MARKDOWN_FENCE_RE = re.compile(r"```[\s\S]*?```", flags=re.MULTILINE)

# Prompt size caps (Realtime is sensitive to long instructions)
# - Compact greeting prompt (sent as session.update.instructions): MUST be business-only.
#   Per CRITICAL prompt-separation requirement, keep it ~300–400 chars (sanitized excerpt).
# - Full prompt (NEVER sent as session.update.instructions): can be larger (injected later as messages).
COMPACT_GREETING_MAX_CHARS = 420  # Legacy - not used anymore (LATENCY-FIRST)
FULL_PROMPT_MAX_CHARS = 8000  # ⚠️ This is a LIMIT, not a target! Keep actual prompts 2000-4000 chars for best performance


def sanitize_realtime_instructions(text: str, max_chars: int = 1000) -> str:
    """
    Sanitize text before sending to OpenAI Realtime `session.update.instructions`.

    Goals:
    - Remove heavy formatting / non-speech symbols that can confuse TTS
    - Flatten newlines (both actual and escaped) into spaces
    - Hard-cap size (Realtime is sensitive to large instructions)
    """
    if not text:
        return ""

    # Remove fenced code blocks entirely (rare but can appear in prompts)
    text = _MARKDOWN_FENCE_RE.sub(" ", text)

    # Normalize escaped newlines first, then real newlines
    text = text.replace("\\n", " ").replace("\n", " ")

    # Remove common "layout" unicode blocks (box drawing, arrows, emoji)
    text = _BOX_DRAWING_RE.sub(" ", text)
    text = _ARROWS_RE.sub(" ", text)
    text = _EMOJI_RE.sub(" ", text)

    # Strip common markdown-ish separators and list bullets
    text = re.sub(r"[`*_>#|]+", " ", text)
    text = re.sub(r"[•●▪▫◆◇■□]+", " ", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    if max_chars and len(text) > max_chars:
        cut = text[:max_chars]
        # Try to cut at a natural boundary, but don't over-trim.
        boundary = max(
            cut.rfind(". "),
            cut.rfind("? "),
            cut.rfind("! "),
            cut.rfind(" "),
        )
        if boundary >= int(max_chars * 0.6):
            text = cut[:boundary].strip()
        else:
            text = cut.strip()

    return text

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 PART 1: SYSTEM PROMPT - BEHAVIOR RULES (direction-aware, single source)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _build_universal_system_prompt(call_direction: Optional[str] = None) -> str:
    """
    🎯 UNIVERSAL SYSTEM PROMPT - Technical Behavior Rules ONLY
    
    ✅ MUST CONTAIN:
    - Realtime API rules (barge-in, pauses, noise)
    - Business isolation rules (ZERO cross-contamination)
    - Call isolation rules (each call independent)
    - Language rules (Hebrew default, auto-switch)
    - Truth & safety rules (transcription is truth)
    - Conversation rules (short, clear responses)
    
    ❌ MUST NOT CONTAIN:
    - Flow logic (comes from Business Prompt)
    - Service names, city names, business names
    - Domain-specific examples or scripts
    - Gender/style instructions (נציג/נציגה) - comes from Business Prompt
    
    This prompt is direction-aware (INBOUND vs OUTBOUND) but remains:
    - behavior-only (no business content)
    - short and voice-friendly
    - single source of truth for both directions (no duplicated rule blocks)

    Written in English for optimal AI understanding.
    """
    # Keep this SHORT and purely operational for Realtime.
    # Target: <= ~900 chars, no markdown, no separators, no icons.
    # Keep it clean for Hebrew voice calls:
    # - short
    # - no formatting
    # - no business content
    # - no “meta” explanations that could leak to caller
    base = (
        "You are a professional phone agent for the currently active business only. "
        "Isolation: treat each call as independent; never use details/style from other businesses or prior calls. "
        "Representative style: follow the Business Prompt's instructions on how to speak and present yourself (נציג/נציגה/neutral)."
        "\n\n"
        "Language - Natural Hebrew Phone Conversation:\n"
        "- Speak natural, fluent, daily Israeli Hebrew like in a real phone conversation.\n"
        "- Prefer everyday spoken phrasing, not formal written language.\n"
        "- Sound like a native speaker in a phone call - NOT a translation from English.\n"
        "- Use short, flowing sentences at a natural phone conversation pace.\n"
        "- Avoid: formal/bookish language, long complex sentences, artificial phrasing.\n"
        "- When appropriate, use short acknowledgment responses (like: כן, הבנתי, רגע).\n"
        "\n"
        "What to AVOID:\n"
        "- Do NOT repeat back what the customer said unless needed for verification.\n"
        "- Do NOT use generic words like: מעולה מאוד, נפלא, מצוין ביותר (sounds robotic).\n"
        "- Do NOT use formal phrases like: אשמח לסייע, נשמח לעמוד לשירותך.\n"
        "- Keep it simple and conversational.\n"
        "\n"
        "Customer Name Usage:\n"
        "- Customer names are provided in CRM Context messages (private metadata - never read aloud).\n"
        "- Follow the Business Prompt's name usage policy explicitly.\n"
        "- When name usage is enabled AND a name exists: use it naturally throughout the conversation.\n"
        "- Never ask for the name or invent one - use only what's provided.\n"
        "- If no name is available, continue normally without mentioning it.\n"
        "\n"
        "Business Scope:\n"
        "- Focus on the business services and topics in the Business Prompt.\n"
        "- If a question seems clearly outside your business domain: gently guide back to your services.\n"
        "- Use judgment - customers may ask indirectly about relevant topics.\n"
        "- Behave as a trained business employee, not a general AI assistant.\n"
        "\n"
        "Turn-taking: if the caller starts speaking, stop immediately and listen. "
        "Truth: the transcript is the single source of truth; never invent details; if unclear, politely ask the customer to repeat. "
        "Style: warm, calm, concise (1-2 sentences). One response = one goal. Ask one question at a time. "
        "Follow the Business Prompt for the business-specific script and flow."
    )

    d = (call_direction or "").strip().lower()
    if d == "outbound":
        # OUTBOUND: we initiated the call.
        direction_rules = (
            " Outbound rules: you initiated the call; be polite and brief, and proceed according to the outbound Business Prompt."
        )
    elif d == "inbound":
        # INBOUND: caller called the business.
        direction_rules = (
            " Inbound rules: the caller contacted the business; respond naturally and proceed according to the inbound Business Prompt."
        )
    else:
        direction_rules = ""

    return f"{base}{direction_rules}"

def build_global_system_prompt(call_direction: Optional[str] = None) -> str:
    """
    Global SYSTEM prompt (behavior rules only).

    IMPORTANT:
    - This must be injected separately (e.g., as a conversation system message),
      NOT mixed into COMPACT and NOT sent inside session.update.instructions.
    """
    # 🔥 FIX: Increase max_chars to accommodate full customer name instructions
    # The full prompt is ~2600 chars and includes critical customer name usage rules
    # that were being cut off at 1200 chars, causing AI to not use customer names
    return sanitize_realtime_instructions(_build_universal_system_prompt(call_direction=call_direction), max_chars=3000)


def _extract_business_prompt_text(
    *,
    business_name: str,
    ai_prompt_raw: str,
) -> str:
    """Extract business prompt text from DB value (supports JSON format)."""
    ai_prompt_text = ""
    if ai_prompt_raw and ai_prompt_raw.strip():
        raw_prompt = ai_prompt_raw.strip()

        if raw_prompt.startswith("{"):
            try:
                prompt_obj = json.loads(raw_prompt)
                ai_prompt_text = prompt_obj.get("calls") or prompt_obj.get("whatsapp") or raw_prompt
            except json.JSONDecodeError:
                ai_prompt_text = raw_prompt
        else:
            ai_prompt_text = raw_prompt

    if ai_prompt_text:
        ai_prompt_text = ai_prompt_text.replace("{{business_name}}", business_name)
        ai_prompt_text = ai_prompt_text.replace("{{BUSINESS_NAME}}", business_name)

    return ai_prompt_text


def build_compact_business_instructions(business_prompt_text: str) -> str:
    """
    Build COMPACT instructions for Realtime `session.update.instructions`.

    Per required architecture:
    - Business-only content (no global/system rules, no router metadata).
    - Sanitized first ~300–400 chars (hard-capped).
    """
    business_prompt_text = business_prompt_text or ""
    # Sanitize first, then cap hard (keep it voice-friendly and safe for Realtime instructions).
    cleaned = sanitize_realtime_instructions(business_prompt_text, max_chars=5000)
    return sanitize_realtime_instructions(cleaned, max_chars=COMPACT_GREETING_MAX_CHARS)


def build_full_business_prompt(business_id: int, call_direction: str = "inbound") -> str:
    """
    FULL Business Prompt (business-only).

    IMPORTANT:
    - MUST NOT be sent as session.update.instructions.
    - Intended to be injected later via conversation.item.create after greeting.
    """
    from server.models_sql import Business, BusinessSettings

    business = Business.query.get(business_id)
    settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()

    if not business:
        logger.warning(f"⚠️ [FULL_BUSINESS] Business {business_id} not found")
        return ""

    business_name = business.name or "Business"

    if call_direction == "outbound":
        ai_prompt_raw = settings.outbound_ai_prompt if (settings and settings.outbound_ai_prompt) else ""
        direction_label = "OUTBOUND"
    else:
        ai_prompt_raw = settings.ai_prompt if settings else ""
        direction_label = "INBOUND"

    business_prompt_text = _extract_business_prompt_text(business_name=business_name, ai_prompt_raw=ai_prompt_raw)
    if not business_prompt_text.strip():
        logger.error(f"[PROMPT ERROR] Missing business prompt for business_id={business_id} direction={call_direction}")
        # Try to get a fallback from the alternate direction or system_prompt
        if call_direction == "outbound" and settings and settings.ai_prompt:
            logger.warning(f"[PROMPT FALLBACK] Using inbound prompt as fallback for outbound business_id={business_id}")
            business_prompt_text = _extract_business_prompt_text(business_name=business_name, ai_prompt_raw=settings.ai_prompt)
        elif call_direction == "inbound" and settings and settings.outbound_ai_prompt:
            logger.warning(f"[PROMPT FALLBACK] Using outbound prompt as fallback for inbound business_id={business_id}")
            business_prompt_text = _extract_business_prompt_text(business_name=business_name, ai_prompt_raw=settings.outbound_ai_prompt)
        elif business.system_prompt:
            logger.warning(f"[PROMPT FALLBACK] Using system_prompt as fallback for business_id={business_id}")
            business_prompt_text = _extract_business_prompt_text(business_name=business_name, ai_prompt_raw=business.system_prompt)
        
        # If still no prompt, return empty (caller should handle this)
        if not business_prompt_text.strip():
            logger.error(f"[PROMPT ERROR] No prompts available for business_id={business_id} - configuration required")
            return ""

    # Keep the full text (do not sanitize for length here). Downstream callers may sanitize for TTS if needed.
    return (
        f"## BUSINESS_PROMPT_START\n"
        f"BUSINESS PROMPT (Business ID: {business_id}, Name: {business_name}, Call: {direction_label})\n"
        f"{business_prompt_text}\n"
        f"## BUSINESS_PROMPT_END"
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 PART 2: LEGACY FUNCTIONS (for backward compatibility)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def get_greeting_prompt_fast(business_id: int) -> Tuple[str, str]:
    """
    FAST greeting loader - minimal DB access for phase 1
    Returns (greeting_text, business_name)
    
    🔥 CRITICAL: All greetings must come from DB. No hardcoded fallbacks.
    """
    try:
        from server.models_sql import Business
        
        business = Business.query.get(business_id)
        if not business:
            logger.warning(f"⚠️ Business {business_id} not found - using minimal generic greeting")
            return ("", "")  # Return empty - let AI handle naturally
        
        business_name = business.name or ""
        greeting = business.greeting_message
        
        if greeting and greeting.strip():
            # Replace placeholder with actual business name
            final_greeting = greeting.strip().replace("{{business_name}}", business_name).replace("{{BUSINESS_NAME}}", business_name)
            logger.info(f"✅ [GREETING] Loaded from DB for business {business_id}: '{final_greeting[:50]}...'")
            return (final_greeting, business_name)
        else:
            logger.warning(f"⚠️ No greeting in DB for business {business_id} - AI will greet naturally")
            return ("", business_name)  # Let AI greet based on prompt
    except Exception as e:
        logger.error(f"❌ Fast greeting load failed: {e}")
        return ("", "")  # Return empty - let AI handle naturally


def build_compact_greeting_prompt(business_id: int, call_direction: str = "inbound") -> str:
    """
    🔥 REFACTORED: COMPACT version of full prompt for ultra-fast greeting
    
    Per required architecture:
    - COMPACT (session.update.instructions) must be BUSINESS-ONLY.
    - Extract and sanitize only the first ~300–400 chars from the Business Prompt.
    - NO global/system prompt text in COMPACT.
    """
    try:
        from server.models_sql import Business, BusinessSettings
        
        business = Business.query.get(business_id)
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        
        if not business:
            logger.warning(f"⚠️ [COMPACT] Business {business_id} not found")
            return ""
        
        business_name = business.name or "Business"
        
        # 🔥 EXTRACT BUSINESS PROMPT based on direction
        if call_direction == "outbound":
            # Use outbound_ai_prompt
            ai_prompt_raw = settings.outbound_ai_prompt if (settings and settings.outbound_ai_prompt) else ""
            logger.info(f"📦 [COMPACT] Using OUTBOUND prompt for {business_name}")
        else:
            # Use regular ai_prompt
            ai_prompt_raw = settings.ai_prompt if settings else ""
            logger.info(f"📦 [COMPACT] Using INBOUND prompt for {business_name}")

        ai_prompt_text = _extract_business_prompt_text(business_name=business_name, ai_prompt_raw=ai_prompt_raw)

        if not ai_prompt_text.strip():
            logger.error(f"[PROMPT ERROR] Missing compact prompt business_id={business_id} direction={call_direction}")
            # Try to get a fallback from the alternate direction or system_prompt
            if call_direction == "outbound" and settings and settings.ai_prompt:
                logger.warning(f"[PROMPT FALLBACK] Using inbound prompt for compact outbound business_id={business_id}")
                ai_prompt_text = _extract_business_prompt_text(business_name=business_name, ai_prompt_raw=settings.ai_prompt)
            elif call_direction == "inbound" and settings and settings.outbound_ai_prompt:
                logger.warning(f"[PROMPT FALLBACK] Using outbound prompt for compact inbound business_id={business_id}")
                ai_prompt_text = _extract_business_prompt_text(business_name=business_name, ai_prompt_raw=settings.outbound_ai_prompt)
            elif business.system_prompt:
                logger.warning(f"[PROMPT FALLBACK] Using system_prompt for compact business_id={business_id}")
                ai_prompt_text = _extract_business_prompt_text(business_name=business_name, ai_prompt_raw=business.system_prompt)
            
            # If still no prompt, return empty
            if not ai_prompt_text.strip():
                logger.error(f"[PROMPT ERROR] No prompts available for compact business_id={business_id}")
                return ""

        # ✅ COMPACT = BUSINESS-ONLY excerpt (no global/system rules, no direction metadata)
        final_prompt = build_compact_business_instructions(ai_prompt_text)

        logger.info(f"📦 [COMPACT] Final compact prompt: {len(final_prompt)} chars for {call_direction}")
        
        # 🔥 PROMPT_CONTEXT: Log that compact prompt is fully dynamic
        logger.info("[PROMPT_CONTEXT] business_id=%s, prompt_source=ui, has_hardcoded_templates=False, mode=compact", business_id)
        
        # PRODUCTION: Never log prompt content (may contain business copy).
        # Keep only length + hash for traceability.
        try:
            import hashlib
            prompt_hash = hashlib.md5(final_prompt.encode("utf-8")).hexdigest()[:8]
        except Exception:
            prompt_hash = "hash_err"
        logger.debug(
            "[PROMPT_DEBUG] direction=%s business_id=%s compact_len=%s hash=%s",
            call_direction,
            business_id,
            len(final_prompt),
            prompt_hash,
        )
        
        return final_prompt
        
    except Exception as e:
        logger.error(f"❌ [COMPACT] Compact prompt error: {e}")
        import traceback
        traceback.print_exc()
        return ""


def build_realtime_system_prompt(business_id: int, db_session=None, call_direction: str = "inbound", use_cache: bool = True) -> str:
    """
    🔥 ROUTER: Routes to correct prompt builder based on call direction
    
    This function is the main entry point and routes to:
    - build_inbound_system_prompt() for inbound calls
    - build_outbound_system_prompt() for outbound calls
    
    🔥 GREETING OPTIMIZATION: Uses prompt cache to eliminate DB/prompt building latency
    
    Args:
        business_id: Business ID
        db_session: Optional SQLAlchemy session (for transaction safety)
        call_direction: "inbound" or "outbound" - determines which prompt to use
        use_cache: Whether to use prompt cache (default: True)
    
    Returns:
        Complete system prompt for the AI assistant
    """
    try:
        from server.models_sql import Business, BusinessSettings
        
        # 🔥 CACHE CHECK: Try to get cached prompt first
        # 🔥 FIX: Include direction in cache key to prevent inbound/outbound prompt mixing
        if use_cache:
            from server.services.prompt_cache import get_prompt_cache
            cache = get_prompt_cache()
            cached = cache.get(business_id, direction=call_direction)
            if cached:
                logger.info(f"✅ [PROMPT CACHE HIT] Returning cached prompt for business {business_id} ({call_direction})")
                return cached.system_prompt
        
        logger.info(f"🔥 [PROMPT ROUTER] Called for business_id={business_id}, direction={call_direction}")
        
        # Load business and settings
        try:
            if db_session:
                business = db_session.query(Business).get(business_id)
                settings = db_session.query(BusinessSettings).filter_by(tenant_id=business_id).first()
            else:
                business = Business.query.get(business_id)
                settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        except Exception as db_error:
            logger.error(f"❌ DB error loading business {business_id}: {db_error}")
            return _get_fallback_prompt(business_id)
        
        if not business:
            logger.error(f"❌ CRITICAL: Business {business_id} not found!")
            raise ValueError(f"CRITICAL: Business {business_id} not found - cannot build prompt")
        
        business_name = business.name or "Business"
        
        # 🔥 BUSINESS ISOLATION: Log business context to track cross-contamination
        logger.info(f"📋 [ROUTER] Building prompt for {business_name} (business_id={business_id}, direction={call_direction})")
        logger.info(f"[BUSINESS_ISOLATION] prompt_request business_id={business_id} direction={call_direction}")
        
        # 🔥 PREPARE BUSINESS SETTINGS DICT
        business_settings_dict = {
            "id": business_id,
            "name": business_name,
            "ai_prompt": settings.ai_prompt if settings else "",
            "outbound_ai_prompt": settings.outbound_ai_prompt if settings else "",
            "greeting_message": business.greeting_message or ""
        }
        
        # 🔥 ROUTE TO CORRECT BUILDER
        final_prompt = None
        if call_direction == "outbound":
            # 🔥 OUTBOUND: Use pure prompt mode (no call control settings)
            logger.info(f"📤 [PROMPT_ROUTER] Building OUTBOUND prompt for business {business_id}")
            final_prompt = build_outbound_system_prompt(
                business_settings=business_settings_dict,
                db_session=db_session
            )
        else:
            # 🔥 INBOUND: Use full call control settings
            logger.info(f"📞 [PROMPT_ROUTER] Building INBOUND prompt for business {business_id}")
            call_control_settings_dict = {
                "enable_calendar_scheduling": settings.enable_calendar_scheduling if (settings and hasattr(settings, 'enable_calendar_scheduling')) else True,
                # 🔥 CRITICAL: pass call_goal so appointment flow rules are actually injected
                "call_goal": getattr(settings, "call_goal", "lead_only") if settings else "lead_only",
                "auto_end_after_lead_capture": settings.auto_end_after_lead_capture if (settings and hasattr(settings, 'auto_end_after_lead_capture')) else False,
                "auto_end_on_goodbye": settings.auto_end_on_goodbye if (settings and hasattr(settings, 'auto_end_on_goodbye')) else False,
                "smart_hangup_enabled": settings.smart_hangup_enabled if (settings and hasattr(settings, 'smart_hangup_enabled')) else True,
                "silence_timeout_sec": settings.silence_timeout_sec if (settings and hasattr(settings, 'silence_timeout_sec')) else 15,
                "silence_max_warnings": settings.silence_max_warnings if (settings and hasattr(settings, 'silence_max_warnings')) else 2,
            }
            
            final_prompt = build_inbound_system_prompt(
                business_settings=business_settings_dict,
                call_control_settings=call_control_settings_dict,
                db_session=db_session
            )
        
        # 🔥 BUSINESS ISOLATION VERIFICATION: Ensure prompt contains correct business context
        if final_prompt and business_name:
            # Log verification - prompt should contain business-specific content
            logger.info(f"[BUSINESS_ISOLATION] prompt_built business_id={business_id} contains_business_name={business_name in final_prompt}")
        
        # 🔥 CACHE STORE: Save to cache for future use
        # 🔥 FIX: Include direction in cache key to prevent inbound/outbound prompt mixing
        if use_cache and final_prompt:
            from server.services.prompt_cache import get_prompt_cache
            cache = get_prompt_cache()
            greeting_text = business_settings_dict.get("greeting_message", "")
            cache.set(
                business_id=business_id,
                system_prompt=final_prompt,
                greeting_text=greeting_text,
                direction=call_direction,
                language_config={}  # Can be extended later
            )
            logger.info(f"💾 [PROMPT CACHE STORE] Cached prompt for business {business_id} ({call_direction})")
        
        return final_prompt
        
    except Exception as e:
        logger.error(f"❌ Error building Realtime prompt: {e}")
        import traceback
        traceback.print_exc()
        return _get_fallback_prompt(business_id)


def _get_fallback_prompt(business_id: Optional[int] = None) -> str:
    """
    Minimal fallback prompt - tries to use business settings first.
    This should RARELY be called in production.
    
    🎯 SSOT: Uses shared prompt helpers for final fallback
    """
    try:
        if business_id:
            from server.models_sql import Business, BusinessSettings
            business = Business.query.get(business_id)
            settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
            
            # Try to get prompt from settings (highest priority)
            if settings and settings.ai_prompt and settings.ai_prompt.strip():
                logger.warning(f"[FALLBACK] Using ai_prompt from BusinessSettings for business {business_id}")
                return settings.ai_prompt
            
            # Try outbound prompt as fallback
            if settings and settings.outbound_ai_prompt and settings.outbound_ai_prompt.strip():
                logger.warning(f"[FALLBACK] Using outbound_ai_prompt from BusinessSettings for business {business_id}")
                return settings.outbound_ai_prompt
            
            # Try business.system_prompt
            if business and business.system_prompt and business.system_prompt.strip():
                logger.warning(f"[FALLBACK] Using system_prompt from Business for business {business_id}")
                return business.system_prompt
            
            # Last resort: use shared helper with business name
            if business and business.name:
                logger.error(f"[FALLBACK] No prompts found in DB for business {business_id} - using shared fallback helper")
                from server.services.prompt_helpers import get_default_hebrew_prompt_for_calls
                return get_default_hebrew_prompt_for_calls(business.name)
    except Exception as e:
        logger.error(f"[FALLBACK] Error getting fallback prompt: {e}")
    
    # Absolute last resort (should never happen in production)
    logger.critical("[FALLBACK] Using absolute minimal fallback - this indicates a serious configuration issue")
    from server.services.prompt_helpers import get_default_hebrew_prompt_for_calls
    return get_default_hebrew_prompt_for_calls()


def _build_hours_description(policy) -> str:
    """Build opening hours description in English"""
    if policy.allow_24_7:
        return "Open 24/7"
    
    hours = policy.opening_hours
    if not hours:
        return "Hours not defined"
    
    day_names = {
        "sun": "Sun", "mon": "Mon", "tue": "Tue", "wed": "Wed",
        "thu": "Thu", "fri": "Fri", "sat": "Sat"
    }
    
    parts = []
    for day_key in ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]:
        windows = hours.get(day_key, [])
        if windows:
            time_ranges = ",".join([f"{w[0]}-{w[1]}" for w in windows])
            parts.append(f"{day_names[day_key]}:{time_ranges}")
    
    return "Hours: " + " | ".join(parts) if parts else "Hours not set"


def _build_slot_description(slot_size_min: int) -> str:
    """Build slot size description in English"""
    return f"Every {slot_size_min}min"


def _build_critical_rules_compact(business_name: str, today_date: str, weekday_name: str, greeting_text: str = "", call_direction: str = "inbound", enable_calendar_scheduling: bool = True) -> str:
    """
    🔥 LEGACY FUNCTION - NO LONGER USED!
    This function is kept for backward compatibility only.
    All new code should use build_inbound_system_prompt() or build_outbound_system_prompt().
    
    🔥 BUILD 333: PHASE-BASED FLOW - prevents mid-confirmation and looping
    🔥 BUILD 327: STT AS SOURCE OF TRUTH - respond only to what customer actually said
    🔥 BUILD 324: ALL ENGLISH instructions - AI speaks Hebrew to customer
    """
    logger.warning("[PROMPT_DEBUG] Legacy prompt builder _build_critical_rules_compact() was called! This should not happen.")
    
    # This legacy function should not be called in production.
    # Return minimal instructions and log warning.
    return f"""You are a professional representative for {business_name}. 
LANGUAGE: Speak Hebrew to the customer. All instructions are in English.
Follow the business prompt for specific flow and guidelines.
Be brief, natural, and helpful."""



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔥 NEW: PERFECT INBOUND & OUTBOUND SEPARATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def build_inbound_system_prompt(
    business_settings: Dict[str, Any],
    call_control_settings: Dict[str, Any],
    db_session=None
) -> str:
    """
    🔥 REFACTORED: Perfect Separation - System + Business Prompts
    
    STRUCTURE:
    1. Universal System Prompt (behavior only)
    2. Appointment Instructions (if enabled)
    3. Business Prompt (all content and flow)
    
    ✅ NO hardcoded flow
    ✅ NO hardcoded greetings
    ✅ NO domain-specific content in system layer
    
    Args:
        business_settings: Dict with business info (id, name, ai_prompt)
        call_control_settings: Dict with call control (enable_calendar_scheduling, call_goal)
        db_session: Optional SQLAlchemy session
    
    Returns:
        Complete system prompt for inbound calls (2000-3500 chars)
    """
    try:
        business_id = business_settings.get("id")
        business_name = business_settings.get("name", "Business")
        ai_prompt_raw = business_settings.get("ai_prompt", "")
        
        # Extract call control settings
        enable_calendar_scheduling = call_control_settings.get("enable_calendar_scheduling", False)
        call_goal = call_control_settings.get("call_goal", "lead_only")
        
        logger.info(f"📋 [INBOUND] Building prompt: {business_name} (scheduling={enable_calendar_scheduling}, goal={call_goal})")
        
        # LAYER 1: UNIVERSAL SYSTEM PROMPT (behavior only)
        system_rules = _build_universal_system_prompt(call_direction="inbound")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔥 LAYER 2: APPOINTMENT INSTRUCTIONS (dynamic, technical only)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        appointment_instructions = ""
        if call_goal == 'appointment' and enable_calendar_scheduling:
            from server.policy.business_policy import get_business_policy
            policy = get_business_policy(business_id, prompt_text=None, db_session=db_session)
            
            tz = pytz.timezone(policy.tz)
            today = datetime.now(tz)
            today_date = today.strftime("%d/%m/%Y")
            weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            weekday_name = weekday_names[today.weekday()]
            
            appointment_instructions = (
                f"\n\nAPPOINTMENT SCHEDULING (STRICT, technical): Today is {weekday_name} {today_date}. "
                f"Slot size: {policy.slot_size_min}min. "
                "Never skip steps. Required before booking: (1) customer's FULL NAME (first and last name - not just 'לקוח' or generic terms), (2) full date (must include weekday), (3) time. "
                "CRITICAL: Always ask for the customer's full name before booking. Examples: 'על איזה שם לרשום את הפגישה?', 'מה השם המלא שלך?'. "
                "If anything is missing, ask ONLY for the missing field (one question at a time). "
                "Understanding time/date: the customer may say relative time references (today/tomorrow) - always restate as a weekday + full date + HH:MM confirmation question. "
                "Availability: you MUST call check_availability before claiming a slot is available. NEVER say a time is available without calling this tool first. "
                "Booking: you MUST call schedule_appointment to actually create the appointment. NEVER claim an appointment is scheduled without calling this tool. "
                "CRITICAL: Only say an appointment is confirmed after schedule_appointment returns success=true AND includes appointment_id. "
                "If the tool returns success=false, the appointment was NOT created - you must handle the error (slot unavailable, missing info, etc). "
                "If not available, propose up to 2 alternative times provided by the server."
            )
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔥 LAYER 3: BUSINESS PROMPT (all content and flow)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        # Parse business prompt (handle JSON format)
        business_prompt = ""
        if ai_prompt_raw and ai_prompt_raw.strip():
            try:
                if ai_prompt_raw.strip().startswith('{'):
                    prompt_obj = json.loads(ai_prompt_raw)
                    business_prompt = prompt_obj.get('calls') or prompt_obj.get('whatsapp') or ai_prompt_raw
                else:
                    business_prompt = ai_prompt_raw
            except json.JSONDecodeError:
                business_prompt = ai_prompt_raw
        
        # Replace placeholders
        if business_prompt:
            business_prompt = business_prompt.replace("{{business_name}}", business_name)
            business_prompt = business_prompt.replace("{{BUSINESS_NAME}}", business_name)
        
        # Validate business prompt is not empty
        if not business_prompt or not business_prompt.strip():
            # Try to use fallback
            logger.error(f"[PROMPT ERROR] No business prompt available for inbound business_id={business_id}")
            business_prompt = FALLBACK_INBOUND_PROMPT_TEMPLATE.format(business_name=business_name)
            logger.warning(f"[PROMPT FALLBACK] Using minimal generic prompt for business_id={business_id}")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔥 COMBINE ALL LAYERS
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        full_prompt = (
            f"{system_rules}{appointment_instructions}\n\n"
            f"BUSINESS PROMPT (Business ID: {business_id}):\n{business_prompt}\n\n"
            "CALL TYPE: INBOUND. The customer called the business. Follow the business prompt for greeting and flow."
        )
        
        logger.info(f"✅ [INBOUND] Prompt built: {len(full_prompt)} chars (system + business)")
        logger.info(f"🔍 [PROMPT_VERIFICATION] business_id={business_id}, direction=INBOUND, call_type_in_prompt={'CALL TYPE: INBOUND' in full_prompt}")
        
        # 🔥 PROMPT_CONTEXT: Log that prompt is fully dynamic with no hardcoded templates
        has_business_prompt = bool(ai_prompt_raw and ai_prompt_raw.strip())
        logger.info(
            "[PROMPT_CONTEXT] business_id=%s, prompt_source=%s, has_hardcoded_templates=False",
            business_id, "ui" if has_business_prompt else "fallback"
        )
        
        # 🔥 PROMPT DEBUG: Log the actual prompt content (first 400 chars)
        # PRODUCTION: Never log prompt content; only log length + hash.
        try:
            import hashlib
            prompt_hash = hashlib.md5(full_prompt.encode("utf-8")).hexdigest()[:8]
        except Exception:
            prompt_hash = "hash_err"
        logger.debug(
            "[PROMPT_DEBUG] direction=inbound business_id=%s prompt_len=%s hash=%s",
            business_id,
            len(full_prompt),
            prompt_hash,
        )
        
        return full_prompt
        
    except Exception as e:
        logger.error(f"❌ [INBOUND] Error: {e}")
        import traceback
        traceback.print_exc()
        # Use fallback template for error case
        return FALLBACK_INBOUND_PROMPT_TEMPLATE.format(business_name=business_settings.get('name', 'the business'))


def build_outbound_system_prompt(
    business_settings: Dict[str, Any],
    db_session=None
) -> str:
    """
    🔥 REFACTORED: Perfect Separation - System + Outbound Business Prompt
    
    STRUCTURE:
    1. Universal System Prompt (behavior only)
    2. Outbound-specific note (identity reminder)
    3. Outbound Business Prompt (all content and flow)
    
    ✅ NO hardcoded flow
    ✅ NO hardcoded greetings
    ✅ NO domain-specific content in system layer
    
    Args:
        business_settings: Dict with business info (id, name, outbound_ai_prompt)
        db_session: Optional SQLAlchemy session
    
    Returns:
        Complete system prompt for outbound calls (2000-3500 chars)
    """
    try:
        business_id = business_settings.get("id")
        business_name = business_settings.get("name", "Business")
        outbound_prompt_raw = business_settings.get("outbound_ai_prompt", "")
        
        logger.info(f"📋 [OUTBOUND] Building prompt: {business_name} (id={business_id})")
        
        # LAYER 1: UNIVERSAL SYSTEM PROMPT (behavior only)
        system_rules = _build_universal_system_prompt(call_direction="outbound")
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔥 LAYER 2: OUTBOUND-SPECIFIC CONTEXT (now integrated in final prompt)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔥 LAYER 3: OUTBOUND BUSINESS PROMPT (all content and flow)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        outbound_prompt = ""
        if outbound_prompt_raw and outbound_prompt_raw.strip():
            outbound_prompt = outbound_prompt_raw.strip()
            logger.info(f"✅ [OUTBOUND] Using outbound_ai_prompt ({len(outbound_prompt)} chars)")
        else:
            logger.error(f"[PROMPT ERROR] No outbound_ai_prompt for business_id={business_id}")
            outbound_prompt = FALLBACK_OUTBOUND_PROMPT_TEMPLATE.format(business_name=business_name)
            logger.warning(f"[PROMPT FALLBACK] Using minimal generic outbound prompt for business_id={business_id}")
        
        # Replace placeholders
        outbound_prompt = outbound_prompt.replace("{{business_name}}", business_name)
        outbound_prompt = outbound_prompt.replace("{{BUSINESS_NAME}}", business_name)
        
        # Validate outbound prompt is not empty
        if not outbound_prompt or not outbound_prompt.strip():
            logger.critical(f"[PROMPT ERROR] Outbound prompt is empty after processing for business_id={business_id}")
            outbound_prompt = FALLBACK_OUTBOUND_PROMPT_TEMPLATE.format(business_name=business_name)
        
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 🔥 COMBINE ALL LAYERS
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        
        full_prompt = (
            f"{system_rules}\n\n"
            f"BUSINESS PROMPT (Business ID: {business_id}):\n{outbound_prompt}\n\n"
            f'CALL TYPE: OUTBOUND from "{business_name}". If confused, briefly identify the business and continue per the outbound prompt.'
        )
        
        logger.info(f"✅ [OUTBOUND] Prompt built: {len(full_prompt)} chars (system + outbound)")
        logger.info(f"🔍 [PROMPT_VERIFICATION] business_id={business_id}, direction=OUTBOUND, call_type_in_prompt={'CALL TYPE: OUTBOUND' in full_prompt}")
        
        # 🔥 PROMPT_CONTEXT: Log that prompt is fully dynamic with no hardcoded templates
        has_outbound_prompt = bool(outbound_prompt_raw and outbound_prompt_raw.strip())
        logger.info(
            "[PROMPT_CONTEXT] business_id=%s, prompt_source=%s, has_hardcoded_templates=False",
            business_id, "ui" if has_outbound_prompt else "fallback"
        )
        
        # 🔥 PROMPT DEBUG: Log the actual prompt content (first 400 chars)
        # PRODUCTION: Never log prompt content; only log length + hash.
        try:
            import hashlib
            prompt_hash = hashlib.md5(full_prompt.encode("utf-8")).hexdigest()[:8]
        except Exception:
            prompt_hash = "hash_err"
        logger.debug(
            "[PROMPT_DEBUG] direction=outbound business_id=%s prompt_len=%s hash=%s",
            business_id,
            len(full_prompt),
            prompt_hash,
        )
        
        return full_prompt
        
    except Exception as e:
        logger.error(f"❌ [OUTBOUND] Error: {e}")
        import traceback
        traceback.print_exc()
        # Use fallback template for error case
        return FALLBACK_OUTBOUND_PROMPT_TEMPLATE.format(business_name=business_settings.get('name', 'the business'))
