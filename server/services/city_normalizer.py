"""
Hebrew City Normalization Engine
BUILD 184: Fuzzy matching for Israeli cities with RapidFuzz

Features:
- ~120+ Israeli cities with aliases
- RapidFuzz fuzzy matching with confidence thresholds
- Handles common confusion pairs (בית שמש/בית שאן/בת ים)
- Returns both raw input and canonical city name
- Caches city data at startup for fast lookups
"""
import json
import logging
import os
from typing import Optional, Tuple, List, Dict
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


class HebrewCityNormalizer:
    """
    Singleton city normalizer with fuzzy matching
    
    Confidence thresholds:
    - >= 92: Auto-accept (high confidence)
    - 85-92: Confirm with user
    - < 85: Retry (too ambiguous)
    """
    
    _instance = None
    _cities_data: Optional[Dict] = None
    _all_names: List[str] = []
    _name_to_canonical: Dict[str, str] = {}
    _confusing_pairs: List[Dict] = []
    
    AUTO_ACCEPT_THRESHOLD = 92
    CONFIRM_THRESHOLD = 85
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_cities()
        return cls._instance
    
    def _load_cities(self):
        """Load cities from JSON file at startup"""
        try:
            json_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'data',
                'israeli_cities.json'
            )
            
            if not os.path.exists(json_path):
                logger.error(f"❌ City data file not found: {json_path}")
                self._cities_data = {"cities": [], "confusing_pairs": []}
                return
            
            with open(json_path, 'r', encoding='utf-8') as f:
                self._cities_data = json.load(f)
            
            self._all_names = []
            self._name_to_canonical = {}
            
            for city in self._cities_data.get('cities', []):
                canonical = city['canonical']
                
                self._all_names.append(canonical)
                self._name_to_canonical[canonical] = canonical
                
                for alias in city.get('aliases', []):
                    if alias:
                        self._all_names.append(alias)
                        self._name_to_canonical[alias] = canonical
            
            self._confusing_pairs = self._cities_data.get('confusing_pairs', [])
            
            logger.info(f"✅ City normalizer loaded: {len(self._cities_data.get('cities', []))} cities, {len(self._all_names)} total names")
            
        except Exception as e:
            logger.error(f"❌ Failed to load city data: {e}")
            self._cities_data = {"cities": [], "confusing_pairs": []}
    
    def normalize(self, raw_city: str) -> CityMatch:
        """
        Normalize a city name using fuzzy matching
        
        Args:
            raw_city: Raw city name from STT/user input
            
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
        
        if raw_city in self._name_to_canonical:
            canonical = self._name_to_canonical[raw_city]
            logger.info(f"✅ [CITY] Exact match: '{raw_city}' -> '{canonical}'")
            return CityMatch(
                raw_input=raw_city,
                canonical=canonical,
                confidence=100,
                needs_confirmation=False
            )
        
        if not RAPIDFUZZ_AVAILABLE:
            return self._basic_match(raw_city)
        
        return self._fuzzy_match(raw_city)
    
    def _fuzzy_match(self, raw_city: str) -> CityMatch:
        """Use RapidFuzz for fuzzy matching"""
        if not RAPIDFUZZ_AVAILABLE:
            return self._basic_match(raw_city)
            
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
    
    def _basic_match(self, raw_city: str) -> CityMatch:
        """Basic string matching fallback when RapidFuzz unavailable"""
        raw_lower = raw_city.lower().replace('-', ' ').replace('"', '')
        
        for name in self._all_names:
            name_lower = name.lower().replace('-', ' ').replace('"', '')
            if raw_lower == name_lower:
                canonical = self._name_to_canonical.get(name, name)
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
            if city in pair.get('cities', []):
                return pair.get('hint')
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


_normalizer_instance = None

def get_city_normalizer() -> HebrewCityNormalizer:
    """Get singleton city normalizer instance"""
    global _normalizer_instance
    if _normalizer_instance is None:
        _normalizer_instance = HebrewCityNormalizer()
    return _normalizer_instance


def normalize_city(raw_city: str) -> CityMatch:
    """
    Convenience function to normalize a city name
    
    Usage:
        result = normalize_city("בית שמש")
        if result.canonical:
            print(f"Matched: {result.canonical} (confidence: {result.confidence}%)")
        if result.needs_confirmation:
            print(f"Please confirm: {result.canonical}")
    """
    return get_city_normalizer().normalize(raw_city)


def get_similar_cities(raw_city: str, limit: int = 3) -> List[Tuple[str, float]]:
    """Get top N similar cities for disambiguation"""
    return get_city_normalizer().get_similar_cities(raw_city, limit)
