"""
Hebrew City Normalization Engine
BUILD 186: Native Hebrew Linguistics Upgrade

Features:
- 1000+ Israeli localities (cities, towns, moshavim, kibbutzim)
- RapidFuzz fuzzy matching with confidence thresholds
- Big-jump protection to prevent hallucinations (בית שמש → מצפה רמון)
- Handles common confusion pairs
- Returns both raw input and canonical city name
- Caches city data at startup for fast lookups
- Fallback to legacy data if extended file missing
"""
import json
import logging
import os
import threading
from typing import Optional, Tuple, List, Dict, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False
    logger.warning("⚠️ rapidfuzz not installed - using basic string matching")


@dataclass
class CityMatch:
    """Result of city normalization"""
    raw_input: str
    canonical: Optional[str]
    confidence: float
    needs_confirmation: bool
    suggestion_hint: Optional[str] = None
    big_jump_blocked: bool = False


class HebrewCityNormalizer:
    """
    Singleton city normalizer with fuzzy matching
    
    BUILD 186 Confidence thresholds:
    - >= 90: Auto-accept (high confidence)
    - 82-90: Confirm with user
    - < 82: Reject/Retry (too ambiguous)
    """
    
    _instance = None
    _lock = threading.Lock()
    _cities_data: Optional[Dict] = None
    _all_names: List[str] = []
    _name_to_canonical: Dict[str, str] = {}
    _confusing_pairs: List[Dict] = []
    _big_jump_pairs: Set[Tuple[str, str]] = set()
    _phonetic_rules: Optional[Dict] = None
    
    AUTO_ACCEPT_THRESHOLD = 90
    CONFIRM_THRESHOLD = 82
    BIG_JUMP_DISTANCE = 15
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._load_cities()
                    cls._instance._load_phonetic_rules()
        return cls._instance
    
    def _load_cities(self):
        """Load cities from JSON files at startup with deduplication"""
        try:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
            
            extended_path = os.path.join(data_dir, 'israeli_places.json')
            legacy_path = os.path.join(data_dir, 'israeli_cities.json')
            
            if os.path.exists(extended_path):
                json_path = extended_path
                logger.info("📍 Loading extended israeli_places.json")
            elif os.path.exists(legacy_path):
                json_path = legacy_path
                logger.info("📍 Falling back to israeli_cities.json")
            else:
                logger.error("❌ No city data file found")
                self._cities_data = {"cities": [], "confusing_pairs": []}
                return
            
            with open(json_path, 'r', encoding='utf-8') as f:
                self._cities_data = json.load(f)
            
            self._all_names = []
            self._name_to_canonical = {}
            seen_names: Set[str] = set()
            
            for city in self._cities_data.get('cities', []):
                canonical = city['canonical'].strip()
                
                if canonical not in seen_names:
                    self._all_names.append(canonical)
                    self._name_to_canonical[canonical] = canonical
                    seen_names.add(canonical)
                
                for alias in city.get('aliases', []):
                    if alias:
                        alias = alias.strip()
                        if alias not in seen_names:
                            self._all_names.append(alias)
                            self._name_to_canonical[alias] = canonical
                            seen_names.add(alias)
            
            self._confusing_pairs = self._cities_data.get('confusing_pairs', [])
            
            for pair in self._confusing_pairs:
                city1 = pair.get('city1', '')
                city2 = pair.get('city2', '')
                if city1 and city2:
                    self._big_jump_pairs.add((city1, city2))
                    self._big_jump_pairs.add((city2, city1))
            
            logger.info(f"✅ City normalizer loaded: {len(self._cities_data.get('cities', []))} cities, {len(self._all_names)} unique names")
            
        except Exception as e:
            logger.error(f"❌ Failed to load city data: {e}")
            import traceback
            traceback.print_exc()
            self._cities_data = {"cities": [], "confusing_pairs": []}
    
    def _load_phonetic_rules(self):
        """Load phonetic rules for big-jump detection"""
        try:
            rules_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'data',
                'hebrew_phonetic_rules.json'
            )
            
            if os.path.exists(rules_path):
                with open(rules_path, 'r', encoding='utf-8') as f:
                    self._phonetic_rules = json.load(f)
                
                for pair in self._phonetic_rules.get('big_jump_cities', {}).get('pairs', []):
                    if len(pair) == 2:
                        self._big_jump_pairs.add((pair[0], pair[1]))
                        self._big_jump_pairs.add((pair[1], pair[0]))
                
                logger.info(f"✅ Phonetic rules loaded: {len(self._big_jump_pairs)} big-jump pairs")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load phonetic rules: {e}")
            self._phonetic_rules = {}
    
    # 🔥 BUILD 195: Context-aware rejection words
    # These are NEVER valid city names - reject immediately
    REJECTED_NON_CITIES = {
        # Affirmations/negations
        "כן", "לא", "אוקיי", "בסדר", "אולי", "נכון", "טוב",
        # Common filler phrases that STT might capture
        "כן יפה", "כן כן", "לא לא", "אה", "אמ", "אממ", "מממ",
        "תודה", "בבקשה", "סליחה", "רגע", "שניה", "חכה",
        # Acknowledgments that aren't cities
        "סבבה", "יאללה", "אחלה", "מעולה", "טוב מאוד", "בטח"
    }
    
    def normalize(self, raw_city: str, previous_value: Optional[str] = None) -> CityMatch:
        """
        Normalize a city name using fuzzy matching
        
        Args:
            raw_city: Raw city name from STT/user input
            previous_value: Previously confirmed/locked value (for big-jump detection)
            
        Returns:
            CityMatch with canonical name and confidence
        """
        if not raw_city or not raw_city.strip():
            return CityMatch(
                raw_input=raw_city or "",
                canonical=None,
                confidence=0,
                needs_confirmation=False
            )
        
        raw_city = raw_city.strip()
        
        # 🔥 BUILD 195: CONTEXT-AWARE REJECTION
        # Reject words that are NEVER valid city names
        if raw_city in self.REJECTED_NON_CITIES:
            logger.warning(f"🚫 [BUILD 195] Rejected non-city word: '{raw_city}'")
            return CityMatch(
                raw_input=raw_city,
                canonical=None,
                confidence=0,
                needs_confirmation=False,
                suggestion_hint="זה לא שם של עיר. באיזה עיר את/ה גר/ה?"
            )
        
        if raw_city in self._name_to_canonical:
            canonical = self._name_to_canonical[raw_city]
            
            if previous_value and self._is_big_jump(previous_value, canonical):
                logger.warning(f"🚫 [BIG-JUMP] Blocked: '{previous_value}' → '{canonical}'")
                return CityMatch(
                    raw_input=raw_city,
                    canonical=previous_value,
                    confidence=100,
                    needs_confirmation=False,
                    big_jump_blocked=True
                )
            
            logger.info(f"✅ [CITY] Exact match: '{raw_city}' -> '{canonical}'")
            return CityMatch(
                raw_input=raw_city,
                canonical=canonical,
                confidence=100,
                needs_confirmation=False
            )
        
        if not RAPIDFUZZ_AVAILABLE:
            return self._basic_match(raw_city, previous_value)
        
        return self._fuzzy_match(raw_city, previous_value)
    
    def _is_big_jump(self, from_city: str, to_city: str) -> bool:
        """Check if changing from one city to another is a 'big jump' that should be blocked"""
        if not from_city or not to_city:
            return False
        
        if from_city == to_city:
            return False
        
        if (from_city, to_city) in self._big_jump_pairs:
            return True
        
        if RAPIDFUZZ_AVAILABLE:
            try:
                from rapidfuzz import fuzz as rf_fuzz
                similarity = rf_fuzz.ratio(from_city, to_city)
                if similarity < (100 - self.BIG_JUMP_DISTANCE):
                    return True
            except:
                pass
        
        return False
    
    def _fuzzy_match(self, raw_city: str, previous_value: Optional[str] = None) -> CityMatch:
        """Use RapidFuzz for fuzzy matching"""
        if not RAPIDFUZZ_AVAILABLE:
            return self._basic_match(raw_city, previous_value)
            
        try:
            from rapidfuzz import fuzz as rf_fuzz, process as rf_process
            result = rf_process.extractOne(
                raw_city,
                self._all_names,
                scorer=rf_fuzz.WRatio,
                score_cutoff=50
            )
            
            if not result:
                logger.warning(f"⚠️ [CITY] No match for '{raw_city}' (score < 50)")
                return CityMatch(
                    raw_input=raw_city,
                    canonical=None,
                    confidence=0,
                    needs_confirmation=False
                )
            
            matched_name, score, _ = result
            canonical = self._name_to_canonical.get(matched_name, matched_name)
            
            if previous_value and self._is_big_jump(previous_value, canonical):
                logger.warning(f"🚫 [BIG-JUMP] Blocked correction: '{previous_value}' → '{canonical}' (score={score:.1f})")
                return CityMatch(
                    raw_input=raw_city,
                    canonical=previous_value,
                    confidence=100,
                    needs_confirmation=True,
                    suggestion_hint=f"זיהינו '{canonical}', אבל כבר נרשם '{previous_value}'. נכון?",
                    big_jump_blocked=True
                )
            
            logger.info(f"🔍 [CITY] Fuzzy match: '{raw_city}' -> '{canonical}' (score={score:.1f})")
            
            if score >= self.AUTO_ACCEPT_THRESHOLD:
                logger.info(f"✅ [CITY] Auto-accept: '{canonical}' (score={score:.1f} >= {self.AUTO_ACCEPT_THRESHOLD})")
                return CityMatch(
                    raw_input=raw_city,
                    canonical=canonical,
                    confidence=score,
                    needs_confirmation=False
                )
            
            elif score >= self.CONFIRM_THRESHOLD:
                hint = self._get_confusion_hint(canonical)
                logger.info(f"⚠️ [CITY] Needs confirmation: '{canonical}' (score={score:.1f})")
                return CityMatch(
                    raw_input=raw_city,
                    canonical=canonical,
                    confidence=score,
                    needs_confirmation=True,
                    suggestion_hint=hint
                )
            
            else:
                logger.warning(f"❌ [CITY] Low confidence: '{raw_city}' -> '{canonical}' (score={score:.1f} < {self.CONFIRM_THRESHOLD})")
                return CityMatch(
                    raw_input=raw_city,
                    canonical=None,
                    confidence=score,
                    needs_confirmation=False
                )
                
        except Exception as e:
            logger.error(f"❌ [CITY] Fuzzy match error: {e}")
            return CityMatch(
                raw_input=raw_city,
                canonical=None,
                confidence=0,
                needs_confirmation=False
            )
    
    def _basic_match(self, raw_city: str, previous_value: Optional[str] = None) -> CityMatch:
        """Basic string matching fallback when RapidFuzz unavailable"""
        raw_lower = raw_city.lower().replace('-', ' ').replace('"', '')
        
        for name in self._all_names:
            name_lower = name.lower().replace('-', ' ').replace('"', '')
            if raw_lower == name_lower:
                canonical = self._name_to_canonical.get(name, name)
                
                if previous_value and self._is_big_jump(previous_value, canonical):
                    return CityMatch(
                        raw_input=raw_city,
                        canonical=previous_value,
                        confidence=100,
                        needs_confirmation=True,
                        big_jump_blocked=True
                    )
                
                return CityMatch(
                    raw_input=raw_city,
                    canonical=canonical,
                    confidence=100,
                    needs_confirmation=False
                )
        
        for name in self._all_names:
            name_lower = name.lower().replace('-', ' ').replace('"', '')
            if raw_lower in name_lower or name_lower in raw_lower:
                canonical = self._name_to_canonical.get(name, name)
                return CityMatch(
                    raw_input=raw_city,
                    canonical=canonical,
                    confidence=70,
                    needs_confirmation=True
                )
        
        return CityMatch(
            raw_input=raw_city,
            canonical=None,
            confidence=0,
            needs_confirmation=False
        )
    
    def _get_confusion_hint(self, city: str) -> Optional[str]:
        """Get hint for commonly confused cities"""
        for pair in self._confusing_pairs:
            if city == pair.get('city1') or city == pair.get('city2'):
                other = pair.get('city2') if city == pair.get('city1') else pair.get('city1')
                warning = pair.get('warning', 'similar')
                if warning == 'phonetically_similar':
                    return f"האם התכוונת ל{city} או ל{other}?"
        return None
    
    def get_similar_cities(self, raw_city: str, limit: int = 3) -> List[Tuple[str, float]]:
        """
        Get top N similar cities for disambiguation
        
        Returns:
            List of (canonical_name, score) tuples
        """
        if not RAPIDFUZZ_AVAILABLE:
            return []
        
        try:
            from rapidfuzz import fuzz as rf_fuzz, process as rf_process
            results = rf_process.extract(
                raw_city,
                self._all_names,
                scorer=rf_fuzz.WRatio,
                limit=limit * 2,
                score_cutoff=60
            )
            
            seen_canonical = set()
            unique_results = []
            
            for name, score, _ in results:
                canonical = self._name_to_canonical.get(name, name)
                if canonical not in seen_canonical:
                    seen_canonical.add(canonical)
                    unique_results.append((canonical, score))
                    if len(unique_results) >= limit:
                        break
            
            return unique_results
            
        except Exception as e:
            logger.error(f"❌ [CITY] Similar cities error: {e}")
            return []
    
    def reload(self):
        """Force reload of city data (thread-safe)"""
        with self._lock:
            self._load_cities()
            self._load_phonetic_rules()


_normalizer_instance = None
_normalizer_lock = threading.Lock()

def get_city_normalizer() -> HebrewCityNormalizer:
    """Get singleton city normalizer instance"""
    global _normalizer_instance
    if _normalizer_instance is None:
        with _normalizer_lock:
            if _normalizer_instance is None:
                _normalizer_instance = HebrewCityNormalizer()
    return _normalizer_instance


def normalize_city(raw_city: str, previous_value: Optional[str] = None) -> CityMatch:
    """
    Convenience function to normalize a city name
    
    Usage:
        result = normalize_city("בית שמש")
        if result.canonical:
            print(f"Matched: {result.canonical} (confidence: {result.confidence}%)")
        if result.needs_confirmation:
            print(f"Please confirm: {result.canonical}")
        if result.big_jump_blocked:
            print("Big jump correction was blocked")
    """
    return get_city_normalizer().normalize(raw_city, previous_value)


def get_similar_cities(raw_city: str, limit: int = 3) -> List[Tuple[str, float]]:
    """Get top N similar cities for disambiguation"""
    return get_city_normalizer().get_similar_cities(raw_city, limit)


def get_all_city_names() -> List[str]:
    """
    Get all city names (canonical + aliases) for phonetic validation
    
    Returns:
        List of all known city names
    """
    normalizer = get_city_normalizer()
    return list(normalizer._all_names)
