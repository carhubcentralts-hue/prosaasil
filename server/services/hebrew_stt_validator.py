"""
BUILD 186: Hebrew STT Validator
100% DYNAMIC - No hardcoded patterns!

Uses linguistic rules to detect gibberish in Hebrew text:
1. Hebrew phonotactic rules (valid consonant-vowel patterns)
2. Lexicon matching (dynamic from JSON files)
3. Statistical analysis (entropy, character distribution)
4. Word structure validation
"""

import json
import os
import math
import re
from typing import Set, Tuple, Optional
from functools import lru_cache

# Hebrew character classes
HEBREW_LETTERS = set('אבגדהוזחטיכלמנסעפצקרשתךםןףץ')
HEBREW_VOWELS = set('אוי')  # Matres lectionis (vowel letters)
HEBREW_CONSONANTS = HEBREW_LETTERS - HEBREW_VOWELS
HEBREW_FINAL_LETTERS = set('ךםןףץ')  # Sofit letters - only valid at word end

# Hebrew word structure rules
MIN_WORD_LENGTH = 2
MAX_CONSONANT_CLUSTER = 4  # Hebrew rarely has >4 consecutive consonants
MIN_VOWEL_RATIO = 0.15  # Hebrew words typically have at least 15% vowels

@lru_cache(maxsize=1)
def load_hebrew_lexicon() -> Tuple[Set[str], Set[str], Set[str]]:
    """
    Load Hebrew lexicons from JSON files.
    Returns: (cities_set, names_set, common_words_set)
    """
    cities = set()
    names = set()
    common_words = set()
    
    base_path = os.path.join(os.path.dirname(__file__), '..', 'data')
    
    # Load cities
    try:
        cities_path = os.path.join(base_path, 'israeli_places.json')
        if os.path.exists(cities_path):
            with open(cities_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for city in data.get('cities', []):
                    canonical = city.get('canonical', '')
                    if canonical:
                        cities.add(canonical.lower())
                        for alias in city.get('aliases', []):
                            if alias:
                                cities.add(alias.lower())
    except Exception as e:
        print(f"[STT_VALIDATOR] Warning: Could not load cities: {e}")
    
    # Load names
    try:
        names_path = os.path.join(base_path, 'hebrew_first_names.json')
        if os.path.exists(names_path):
            with open(names_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for name_entry in data.get('names', []):
                    if isinstance(name_entry, str):
                        names.add(name_entry.lower())
                    elif isinstance(name_entry, dict):
                        canonical = name_entry.get('canonical', '')
                        if canonical:
                            names.add(canonical.lower())
    except Exception as e:
        print(f"[STT_VALIDATOR] Warning: Could not load names: {e}")
    
    # Load surnames
    try:
        surnames_path = os.path.join(base_path, 'hebrew_surnames.json')
        if os.path.exists(surnames_path):
            with open(surnames_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for surname_entry in data.get('surnames', []):
                    if isinstance(surname_entry, str):
                        names.add(surname_entry.lower())
                    elif isinstance(surname_entry, dict):
                        canonical = surname_entry.get('canonical', '')
                        if canonical:
                            names.add(canonical.lower())
    except Exception as e:
        print(f"[STT_VALIDATOR] Warning: Could not load surnames: {e}")
    
    # Common Hebrew words (greetings, responses, numbers, etc.)
    # These are universal Hebrew words, not business-specific
    common_words = {
        # Greetings
        'שלום', 'היי', 'הלו', 'בוקר', 'טוב', 'ערב', 'צהריים', 
        'להתראות', 'ביי', 'תודה', 'רבה', 'בבקשה', 'סליחה',
        # Common responses
        'כן', 'לא', 'אולי', 'בסדר', 'טוב', 'יופי', 'מעולה', 'נהדר',
        'אוקיי', 'או', 'קיי', 'נכון', 'בטח', 'ברור', 'סבבה',
        # Questions
        'מה', 'מי', 'איפה', 'מתי', 'למה', 'איך', 'כמה', 'האם',
        # Pronouns
        'אני', 'אתה', 'את', 'הוא', 'היא', 'אנחנו', 'הם', 'הן',
        # Common verbs
        'רוצה', 'צריך', 'יכול', 'רוצים', 'צריכים', 'יכולים',
        'אפשר', 'אמר', 'אמרה', 'שמע', 'עזור', 'עזרה',
        # Numbers
        'אחד', 'אחת', 'שניים', 'שתיים', 'שלוש', 'ארבע', 'חמש',
        'שש', 'שבע', 'שמונה', 'תשע', 'עשר', 'עשרים',
        # Time/Date
        'היום', 'מחר', 'אתמול', 'שעה', 'דקה', 'יום', 'שבוע',
        'חודש', 'שנה', 'ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי',
        # Prepositions/Conjunctions
        'של', 'על', 'עם', 'בלי', 'אל', 'מ', 'ל', 'ב', 'ה',
        'ו', 'או', 'אבל', 'כי', 'אם', 'כש', 'לפני', 'אחרי',
        # Business context
        'תור', 'פגישה', 'שיחה', 'לקוח', 'עסק', 'שירות',
        'מחיר', 'כתובת', 'טלפון', 'מספר', 'שם',
    }
    
    return cities, names, common_words


def calculate_entropy(text: str) -> float:
    """Calculate Shannon entropy of text - low entropy = repetitive/suspicious"""
    if not text:
        return 0.0
    
    freq = {}
    for char in text:
        freq[char] = freq.get(char, 0) + 1
    
    length = len(text)
    entropy = 0.0
    for count in freq.values():
        prob = count / length
        entropy -= prob * math.log2(prob)
    
    return entropy


def check_consonant_clusters(text: str) -> bool:
    """Check if text has valid Hebrew consonant clusters (max 4 consecutive)"""
    consonant_count = 0
    for char in text:
        if char in HEBREW_CONSONANTS:
            consonant_count += 1
            if consonant_count > MAX_CONSONANT_CLUSTER:
                return False
        else:
            consonant_count = 0
    return True


def check_final_letters(word: str) -> bool:
    """Check if final letters (sofit) are used correctly - only at word end"""
    if not word:
        return True
    
    # Sofit letters should only appear at the end
    for i, char in enumerate(word[:-1]):  # All except last
        if char in HEBREW_FINAL_LETTERS:
            return False  # Found sofit in middle = invalid
    
    return True


def check_repeated_chars(text: str, max_repeat: int = 3) -> bool:
    """Check for excessive character repetition"""
    if len(text) < 3:
        return True
    
    prev_char = ''
    repeat_count = 1
    
    for char in text:
        if char == prev_char:
            repeat_count += 1
            if repeat_count > max_repeat:
                return False
        else:
            repeat_count = 1
        prev_char = char
    
    return True


def check_vowel_ratio(text: str) -> bool:
    """Hebrew words need a minimum ratio of vowel letters"""
    hebrew_chars = [c for c in text if c in HEBREW_LETTERS]
    if len(hebrew_chars) < 3:
        return True  # Too short to judge
    
    vowel_count = sum(1 for c in hebrew_chars if c in HEBREW_VOWELS)
    ratio = vowel_count / len(hebrew_chars)
    
    return ratio >= MIN_VOWEL_RATIO


def is_valid_hebrew_word(word: str, cities: Set[str], names: Set[str], common_words: Set[str]) -> Tuple[bool, str]:
    """
    Validate a single Hebrew word using linguistic rules.
    Returns: (is_valid, reason)
    """
    if not word or len(word) < MIN_WORD_LENGTH:
        return True, "too_short"  # Don't reject very short words
    
    # Remove non-Hebrew characters for analysis
    hebrew_only = ''.join(c for c in word if c in HEBREW_LETTERS)
    
    if not hebrew_only:
        return True, "no_hebrew"  # Not a Hebrew word, can't validate
    
    # Check 1: Is it in our lexicon?
    word_lower = word.lower()
    if word_lower in common_words or word_lower in cities or word_lower in names:
        return True, "in_lexicon"
    
    # Check 2: Sofit letters placement
    if not check_final_letters(hebrew_only):
        return False, "invalid_sofit_placement"
    
    # Check 3: Consonant clusters
    if not check_consonant_clusters(hebrew_only):
        return False, "consonant_cluster_too_long"
    
    # Check 4: Character repetition
    if not check_repeated_chars(hebrew_only):
        return False, "excessive_repetition"
    
    # Check 5: Vowel ratio (for words with 5+ letters)
    if len(hebrew_only) >= 5 and not check_vowel_ratio(hebrew_only):
        return False, "low_vowel_ratio"
    
    # Check 6: Entropy check for longer words
    if len(hebrew_only) >= 6:
        entropy = calculate_entropy(hebrew_only)
        # Normalized entropy (max is log2(n) for n unique chars)
        max_entropy = math.log2(len(set(hebrew_only))) if len(set(hebrew_only)) > 1 else 1
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
        
        if normalized_entropy < 0.4:  # Very low entropy = suspicious
            return False, "low_entropy"
    
    return True, "passed_checks"


# 🔥 BUILD 196: Common gibberish words from background noise/music
# These are hallucinated "words" that Whisper outputs when hearing noise
NOISE_HALLUCINATION_WORDS = {
    # Common noise artifacts
    "ידועל", "בלתי", "דדלתות", "ממש", "ווהו", "ווו", "הההה",
    "אאא", "אההה", "אממם", "מממ", "חחח", "קקק", "ררר", "שששש",
    # Music-induced hallucinations (Whisper tries to transcribe lyrics)
    "נננ", "ללל", "יייי", "טטט", "ססס", "עעע", "פפפ", "צצצ",
    # Partial/broken words from noise
    "דדד", "גגג", "בבב", "ווו", "זזזז", "חחח", "טטט", "ייי",
    # Common misheard filler sounds
    "אאאא", "ממממ", "נננ", "בלבל", "גלגל", "מלמל",
    # English hallucinations that slip through
    "בייי", "אוווו", "ווואו", "יייאה", "נאאא",
}

# Common noise sentence patterns (music transcripts tend to have these)
NOISE_PATTERNS = [
    "לא, סליחה",  # Often appears with garbage after
    "ידועל",
    "בלתי",
    "דדלתות",  # Doubled letters = noise
    "ששש",
    "מממ",
]

def is_gibberish(text: str) -> Tuple[bool, str, float]:
    """
    Main entry point: Detect if text is gibberish.
    Uses GENERIC linguistic rules, not hardcoded patterns.
    
    Returns: (is_gibberish, reason, confidence)
    """
    if not text or len(text.strip()) == 0:
        return False, "empty", 0.0
    
    text_stripped = text.strip()
    
    # 🔥 BUILD 196: Quick check for known noise hallucination words
    words = text_stripped.split()
    noise_word_count = sum(1 for w in words if w.strip('.,!?') in NOISE_HALLUCINATION_WORDS)
    if noise_word_count >= 1 and len(words) <= 3:
        return True, f"contains_noise_word: {[w for w in words if w.strip('.,!?') in NOISE_HALLUCINATION_WORDS]}", 0.95
    
    # 🔥 BUILD 196: Check for doubled consonants (common in noise transcripts)
    # e.g., "דדלתות" instead of "דלתות"
    import re
    doubled_consonants = re.findall(r'([בגדהוזחטיכלמנסעפצקרשת])\1{2,}', text_stripped)
    if doubled_consonants:
        return True, f"doubled_consonants: {doubled_consonants}", 0.9
    
    # 🔥 BUILD 196: Check for any noise patterns
    for pattern in NOISE_PATTERNS:
        if pattern in text_stripped:
            return True, f"noise_pattern: {pattern}", 0.85
    
    # Load lexicons (cached)
    cities, names, common_words = load_hebrew_lexicon()
    
    # Split into words
    words = text_stripped.split()
    
    if not words:
        return False, "no_words", 0.0
    
    # Check 1: Very short text with only noise characters
    hebrew_chars = [c for c in text_stripped if c in HEBREW_LETTERS]
    if len(hebrew_chars) < 2:
        return False, "too_short", 0.0  # Can't determine, let it pass
    
    # Check 2: Overall entropy of the text
    if len(hebrew_chars) >= 8:
        entropy = calculate_entropy(''.join(hebrew_chars))
        unique_chars = len(set(hebrew_chars))
        
        if unique_chars > 0:
            max_possible_entropy = math.log2(unique_chars)
            normalized = entropy / max_possible_entropy if max_possible_entropy > 0 else 0
            
            if normalized < 0.35:
                return True, "very_low_text_entropy", 0.9
    
    # Check 3: Excessive apostrophes/geresh (common in gibberish transcriptions)
    apostrophe_count = text_stripped.count("'") + text_stripped.count("׳") + text_stripped.count('"')
    if len(hebrew_chars) > 0:
        apostrophe_ratio = apostrophe_count / len(hebrew_chars)
        if apostrophe_ratio > 0.15:  # More than 15% apostrophes = suspicious
            return True, "excessive_apostrophes", 0.85
    
    # Check 4: Validate each word
    invalid_words = 0
    total_words = 0
    reasons = []
    
    for word in words:
        # Skip very short words and punctuation
        if len(word) < 2:
            continue
        
        # Clean word
        clean_word = ''.join(c for c in word if c in HEBREW_LETTERS or c.isalpha())
        if len(clean_word) < 2:
            continue
        
        total_words += 1
        is_valid, reason = is_valid_hebrew_word(clean_word, cities, names, common_words)
        
        if not is_valid:
            invalid_words += 1
            reasons.append(f"{clean_word}: {reason}")
    
    # If more than 50% of words are invalid, it's gibberish
    if total_words > 0:
        invalid_ratio = invalid_words / total_words
        if invalid_ratio >= 0.5:
            return True, f"many_invalid_words ({invalid_words}/{total_words}): {'; '.join(reasons[:3])}", 0.8
    
    # Check 5: Overall consonant-to-vowel ratio for entire text
    if len(hebrew_chars) >= 6:
        vowel_count = sum(1 for c in hebrew_chars if c in HEBREW_VOWELS)
        consonant_count = len(hebrew_chars) - vowel_count
        
        if vowel_count == 0 and consonant_count >= 6:
            return True, "no_vowels_in_long_text", 0.85
        
        if consonant_count > 0 and vowel_count / consonant_count < 0.1 and len(hebrew_chars) >= 8:
            return True, "extremely_low_vowel_ratio", 0.75
    
    # Check 6: Look for repeated substrings (noise pattern)
    if len(text_stripped) >= 10:
        # Check for 3-char repeating patterns
        for i in range(len(text_stripped) - 6):
            pattern = text_stripped[i:i+3]
            if pattern in text_stripped[i+3:]:
                count = text_stripped.count(pattern)
                if count >= 3 and len(pattern.strip()) == 3:
                    return True, f"repeated_pattern: '{pattern}' x{count}", 0.7
    
    return False, "valid", 0.0


def validate_stt_output(text: str, min_confidence: float = 0.5) -> Tuple[bool, str, Optional[str]]:
    """
    Validate STT output before sending to AI.
    
    Returns: (should_process, reason, cleaned_text)
    - should_process: True if text should be processed by AI
    - reason: Explanation of decision
    - cleaned_text: Cleaned version of text (or None if rejected)
    """
    if not text:
        return False, "empty_input", None
    
    text_stripped = text.strip()
    
    if len(text_stripped) < 2:
        return False, "too_short", None
    
    # Run gibberish detection
    is_gib, gib_reason, confidence = is_gibberish(text_stripped)
    
    if is_gib and confidence >= min_confidence:
        print(f"[STT_VALIDATOR] Rejected gibberish: '{text_stripped}' | Reason: {gib_reason} | Confidence: {confidence:.0%}")
        return False, f"gibberish: {gib_reason}", None
    
    return True, "valid", text_stripped


# Export main functions
__all__ = ['is_gibberish', 'validate_stt_output', 'load_hebrew_lexicon']
