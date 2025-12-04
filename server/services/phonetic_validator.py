"""
Hebrew Phonetic Validator Service (BUILD 185)

3-layer STT accuracy improvement:
1. Hebrew Soundex encoding
2. Hebrew DoubleMetaphone encoding  
3. RapidFuzz fuzzy matching with phonetic boosting

Fixes critical issues like:
- "בית שמש" being transcribed as "מצפה רמון"
- "צוריאל" being transcribed as "צוריה"
- Short Hebrew names with אל endings being corrupted

Thresholds:
- ≥93% → auto-accept
- 85-92% → needs confirmation
- <85% → reject and ask to repeat
"""

from typing import Optional, List, Dict, NamedTuple
import re

RAPIDFUZZ_AVAILABLE = False
fuzz = None

try:
    from rapidfuzz import fuzz as rapidfuzz_fuzz, process
    fuzz = rapidfuzz_fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    print("⚠️ RapidFuzz not available - phonetic validation will use basic matching")


class PhoneticResult(NamedTuple):
    """Result of phonetic validation"""
    raw_input: str
    best_match: Optional[str]
    confidence: float
    needs_confirmation: bool
    should_reject: bool
    phonetic_score: float
    fuzzy_score: float


# Hebrew phonetic confusion pairs
HEBREW_CONFUSIONS = {
    'ש': ['ס', 'צ'],
    'ס': ['ש', 'צ'],
    'צ': ['ס', 'ש'],
    'מ': ['נ'],
    'נ': ['מ'],
    'ב': ['פ', 'ו'],
    'פ': ['ב'],
    'כ': ['ח', 'ק'],
    'ח': ['כ', 'ה'],
    'ק': ['כ'],
    'ת': ['ט'],
    'ט': ['ת'],
    'ד': ['ת'],
    'ג': ['כ'],
    'ע': ['א'],
    'א': ['ע', 'ה'],
    'ה': ['א', 'ח'],
    'ו': ['ב'],
}

# Common Hebrew prefixes that may be added/removed
HEBREW_PREFIXES = ['ה', 'ב', 'ל', 'מ', 'ו', 'כ', 'ש']

# Special patterns for city names
CITY_PREFIXES = ['בית', 'בת', 'בן', 'כפר', 'נהר', 'גבעת', 'רמת', 'קרית', 'נווה', 'מעלה', 'מצפה', 'תל', 'ראש']

# Special patterns for names ending with אל
AL_ENDINGS = ['אל', 'יאל', 'אלי', 'אלה']


def hebrew_soundex(word: str) -> str:
    """
    Hebrew Soundex encoding - maps similar-sounding Hebrew letters to same codes.
    
    Groups:
    - A: א, ע, ה (gutturals/silent)
    - B: ב, פ, ו (labials)
    - G: ג, כ, ק (velars)
    - D: ד, ת, ט (dentals)
    - Z: ז, ס, ש, צ (sibilants)
    - L: ל
    - M: מ, נ (nasals)
    - R: ר
    - Y: י
    """
    if not word:
        return ""
    
    # Mapping of Hebrew letters to Soundex codes
    soundex_map = {
        'א': 'A', 'ע': 'A', 'ה': 'A',
        'ב': 'B', 'פ': 'B', 'ו': 'B',
        'ג': 'G', 'כ': 'G', 'ק': 'G', 'ח': 'G',
        'ד': 'D', 'ת': 'D', 'ט': 'D',
        'ז': 'Z', 'ס': 'Z', 'ש': 'Z', 'צ': 'Z',
        'ל': 'L',
        'מ': 'M', 'נ': 'M',
        'ר': 'R',
        'י': 'Y',
    }
    
    # Remove non-Hebrew characters and spaces
    cleaned = re.sub(r'[^א-ת]', '', word)
    if not cleaned:
        return ""
    
    # Build Soundex code
    result = []
    prev_code = ""
    for char in cleaned:
        code = soundex_map.get(char, '')
        if code and code != prev_code:
            result.append(code)
            prev_code = code
    
    return ''.join(result)


def hebrew_double_metaphone(word: str) -> tuple:
    """
    Hebrew DoubleMetaphone - produces primary and alternate encodings.
    
    Handles:
    - בית/בת/בן prefixes
    - אל/יאל/אלי endings
    - ש/ס confusion
    - מ/נ confusion
    """
    if not word:
        return ("", "")
    
    cleaned = re.sub(r'[^א-ת\s]', '', word).strip()
    if not cleaned:
        return ("", "")
    
    # Primary encoding
    primary = hebrew_soundex(cleaned)
    
    # Generate alternate encoding with common confusions
    alternate_word = cleaned
    for original, confusions in HEBREW_CONFUSIONS.items():
        if original in alternate_word and confusions:
            alternate_word = alternate_word.replace(original, confusions[0], 1)
    
    alternate = hebrew_soundex(alternate_word)
    
    return (primary, alternate)


def normalize_for_comparison(text: str) -> str:
    """Normalize Hebrew text for comparison - remove niqqud, standardize spaces"""
    if not text:
        return ""
    
    # Remove Hebrew niqqud (vowel marks)
    text = re.sub(r'[\u0591-\u05C7]', '', text)
    
    # Normalize quotes and hyphens
    text = text.replace('"', '').replace("'", '').replace('-', ' ').replace('־', ' ')
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    return text.strip()


def extract_prefix_root(word: str) -> tuple:
    """
    Extract city prefix (בית, כפר, etc.) and root.
    Returns (prefix, root) tuple.
    """
    word = normalize_for_comparison(word)
    
    for prefix in CITY_PREFIXES:
        if word.startswith(prefix):
            root = word[len(prefix):].strip()
            if root:
                return (prefix, root)
    
    return ("", word)


def phonetic_similarity(word1: str, word2: str) -> float:
    """
    Calculate phonetic similarity between two Hebrew words.
    Combines Soundex, DoubleMetaphone, and structural analysis.
    
    Returns score 0-100.
    """
    if not word1 or not word2:
        return 0.0
    
    word1 = normalize_for_comparison(word1)
    word2 = normalize_for_comparison(word2)
    
    if word1 == word2:
        return 100.0
    
    # Get Soundex codes
    sx1 = hebrew_soundex(word1)
    sx2 = hebrew_soundex(word2)
    
    # Get DoubleMetaphone codes
    dm1_pri, dm1_alt = hebrew_double_metaphone(word1)
    dm2_pri, dm2_alt = hebrew_double_metaphone(word2)
    
    scores = []
    
    # Soundex match score
    if sx1 and sx2:
        if sx1 == sx2:
            scores.append(90)
        else:
            # Calculate how many codes match
            common = sum(1 for a, b in zip(sx1, sx2) if a == b)
            max_len = max(len(sx1), len(sx2))
            if max_len > 0:
                scores.append(60 * (common / max_len))
    
    # DoubleMetaphone match score
    metaphone_matches = [
        dm1_pri == dm2_pri,
        dm1_pri == dm2_alt,
        dm1_alt == dm2_pri,
        dm1_alt == dm2_alt,
    ]
    if any(metaphone_matches):
        scores.append(85)
    
    # Prefix-root analysis for city names
    prefix1, root1 = extract_prefix_root(word1)
    prefix2, root2 = extract_prefix_root(word2)
    
    if prefix1 and prefix2:
        if prefix1 == prefix2:
            # Same prefix - compare roots
            if root1 == root2:
                scores.append(100)
            else:
                root_sx1 = hebrew_soundex(root1)
                root_sx2 = hebrew_soundex(root2)
                if root_sx1 == root_sx2:
                    scores.append(88)
        else:
            # Different prefix - these are likely different cities
            scores.append(30)
    
    # Check אל endings
    al_match1 = any(word1.endswith(ending) for ending in AL_ENDINGS)
    al_match2 = any(word2.endswith(ending) for ending in AL_ENDINGS)
    if al_match1 and al_match2:
        # Both end with אל - compare without ending
        base1 = word1
        base2 = word2
        for ending in sorted(AL_ENDINGS, key=len, reverse=True):
            if base1.endswith(ending):
                base1 = base1[:-len(ending)]
            if base2.endswith(ending):
                base2 = base2[:-len(ending)]
        if hebrew_soundex(base1) == hebrew_soundex(base2):
            scores.append(92)
    
    if not scores:
        return 0.0
    
    return max(scores)


def validate_hebrew_word(
    raw_text: str,
    candidates: List[str],
    auto_accept_threshold: float = 93.0,
    confirm_threshold: float = 85.0,
    reject_threshold: float = 85.0
) -> PhoneticResult:
    """
    Validate Hebrew word against a list of known candidates.
    
    Args:
        raw_text: The raw STT output to validate
        candidates: List of known valid values (cities, names)
        auto_accept_threshold: Score >= this auto-accepts (default 93)
        confirm_threshold: Score >= this needs confirmation (default 85)
        reject_threshold: Score < this should reject (default 85)
    
    Returns:
        PhoneticResult with best_match, confidence, needs_confirmation, should_reject
    """
    if not raw_text or not candidates:
        return PhoneticResult(
            raw_input=raw_text or "",
            best_match=None,
            confidence=0.0,
            needs_confirmation=False,
            should_reject=True,
            phonetic_score=0.0,
            fuzzy_score=0.0
        )
    
    raw_normalized = normalize_for_comparison(raw_text)
    
    best_match = None
    best_phonetic = 0.0
    best_fuzzy = 0.0
    best_combined = 0.0
    
    for candidate in candidates:
        candidate_normalized = normalize_for_comparison(candidate)
        
        # Calculate phonetic similarity
        phonetic_score = phonetic_similarity(raw_normalized, candidate_normalized)
        
        # Calculate fuzzy similarity
        if RAPIDFUZZ_AVAILABLE and fuzz is not None:
            fuzzy_score = fuzz.WRatio(raw_normalized, candidate_normalized)
        else:
            # Basic Levenshtein-like ratio
            fuzzy_score = 100.0 if raw_normalized == candidate_normalized else 0.0
        
        # Combined score - weighted average (phonetic is more important)
        combined = (phonetic_score * 0.6) + (fuzzy_score * 0.4)
        
        if combined > best_combined:
            best_combined = combined
            best_match = candidate
            best_phonetic = phonetic_score
            best_fuzzy = fuzzy_score
    
    # Determine action based on thresholds
    should_reject = best_combined < reject_threshold
    needs_confirmation = reject_threshold <= best_combined < auto_accept_threshold
    
    return PhoneticResult(
        raw_input=raw_text,
        best_match=best_match if not should_reject else None,
        confidence=best_combined,
        needs_confirmation=needs_confirmation,
        should_reject=should_reject,
        phonetic_score=best_phonetic,
        fuzzy_score=best_fuzzy
    )


class ConsistencyFilter:
    """
    Contextual Consistency Filter (Layer 3)
    
    Tracks last N attempts and uses majority voting to prevent STT hallucinations.
    If 2 out of 3 attempts match, that value is locked in.
    """
    
    def __init__(self, max_attempts: int = 3):
        self.max_attempts = max_attempts
        self.city_attempts: List[str] = []
        self.name_attempts: List[str] = []
        self.locked_city: Optional[str] = None
        self.locked_name: Optional[str] = None
    
    def add_city_attempt(self, raw_city: str) -> Optional[str]:
        """
        Add a city attempt and check for majority.
        Returns the locked city if majority achieved, None otherwise.
        """
        if self.locked_city:
            # Already locked - ignore new attempts
            return self.locked_city
        
        normalized = normalize_for_comparison(raw_city)
        if not normalized:
            return None
        
        self.city_attempts.append(normalized)
        
        # Keep only last N attempts
        if len(self.city_attempts) > self.max_attempts:
            self.city_attempts = self.city_attempts[-self.max_attempts:]
        
        # Check for majority (2 out of 3)
        if len(self.city_attempts) >= 2:
            # Count occurrences using phonetic matching
            for attempt in self.city_attempts:
                matches = sum(1 for a in self.city_attempts if phonetic_similarity(a, attempt) >= 85)
                if matches >= 2:
                    self.locked_city = attempt
                    print(f"🔒 [CONSISTENCY] City locked to '{attempt}' (majority {matches}/{len(self.city_attempts)})")
                    return self.locked_city
        
        return None
    
    def add_name_attempt(self, raw_name: str) -> Optional[str]:
        """
        Add a name attempt and check for majority.
        Returns the locked name if majority achieved, None otherwise.
        """
        if self.locked_name:
            return self.locked_name
        
        normalized = normalize_for_comparison(raw_name)
        if not normalized:
            return None
        
        self.name_attempts.append(normalized)
        
        if len(self.name_attempts) > self.max_attempts:
            self.name_attempts = self.name_attempts[-self.max_attempts:]
        
        if len(self.name_attempts) >= 2:
            for attempt in self.name_attempts:
                matches = sum(1 for a in self.name_attempts if phonetic_similarity(a, attempt) >= 85)
                if matches >= 2:
                    self.locked_name = attempt
                    print(f"🔒 [CONSISTENCY] Name locked to '{attempt}' (majority {matches}/{len(self.name_attempts)})")
                    return self.locked_name
        
        return None
    
    def is_city_locked(self) -> bool:
        return self.locked_city is not None
    
    def is_name_locked(self) -> bool:
        return self.locked_name is not None
    
    def get_city_attempts(self) -> List[str]:
        return list(self.city_attempts)
    
    def get_name_attempts(self) -> List[str]:
        return list(self.name_attempts)
    
    def reset(self):
        """Reset all tracking"""
        self.city_attempts = []
        self.name_attempts = []
        self.locked_city = None
        self.locked_name = None


# Singleton instance for convenience
_default_filter = None

def get_consistency_filter() -> ConsistencyFilter:
    """Get or create default consistency filter"""
    global _default_filter
    if _default_filter is None:
        _default_filter = ConsistencyFilter()
    return _default_filter


def validate_city_with_consistency(
    raw_city: str,
    candidates: List[str],
    filter_instance: Optional[ConsistencyFilter] = None
) -> PhoneticResult:
    """
    Validate city with consistency filtering.
    Combines phonetic validation with majority voting.
    """
    if filter_instance is None:
        filter_instance = get_consistency_filter()
    
    # Check if already locked
    if filter_instance.is_city_locked():
        locked = filter_instance.locked_city
        return PhoneticResult(
            raw_input=raw_city,
            best_match=locked,
            confidence=100.0,
            needs_confirmation=False,
            should_reject=False,
            phonetic_score=100.0,
            fuzzy_score=100.0
        )
    
    # Add attempt and check majority
    locked = filter_instance.add_city_attempt(raw_city)
    
    if locked:
        # Majority achieved - validate the locked value against candidates
        result = validate_hebrew_word(locked, candidates)
        if result.best_match:
            return PhoneticResult(
                raw_input=raw_city,
                best_match=result.best_match,
                confidence=result.confidence,
                needs_confirmation=False,  # Majority overrides confirmation
                should_reject=False,
                phonetic_score=result.phonetic_score,
                fuzzy_score=result.fuzzy_score
            )
    
    # No majority yet - validate current input
    return validate_hebrew_word(raw_city, candidates)


def validate_name_with_consistency(
    raw_name: str,
    candidates: List[str],
    filter_instance: Optional[ConsistencyFilter] = None
) -> PhoneticResult:
    """
    Validate name with consistency filtering.
    Combines phonetic validation with majority voting.
    """
    if filter_instance is None:
        filter_instance = get_consistency_filter()
    
    if filter_instance.is_name_locked():
        locked = filter_instance.locked_name
        return PhoneticResult(
            raw_input=raw_name,
            best_match=locked,
            confidence=100.0,
            needs_confirmation=False,
            should_reject=False,
            phonetic_score=100.0,
            fuzzy_score=100.0
        )
    
    locked = filter_instance.add_name_attempt(raw_name)
    
    if locked:
        result = validate_hebrew_word(locked, candidates)
        if result.best_match:
            return PhoneticResult(
                raw_input=raw_name,
                best_match=result.best_match,
                confidence=result.confidence,
                needs_confirmation=False,
                should_reject=False,
                phonetic_score=result.phonetic_score,
                fuzzy_score=result.fuzzy_score
            )
    
    return validate_hebrew_word(raw_name, candidates)
