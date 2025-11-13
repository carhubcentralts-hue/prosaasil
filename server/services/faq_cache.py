"""
FAQ Cache Service with OpenAI Embeddings

Caches business FAQs + their embeddings for fast semantic search.
Invalidates on FAQ CRUD operations.

Thread-safe singleton cache for multi-tenant FAQ fast-path.
"""
import os
import time
import threading
import numpy as np
import json
from typing import Dict, List, Optional, Tuple
from openai import OpenAI
from server.models_sql import FAQ, db

# ENV-based configuration
FAQ_CACHE_TTL_SECONDS = int(os.getenv("FAQ_CACHE_TTL_SEC", "120"))
EMBEDDING_MODEL = "text-embedding-3-small"
SIMILARITY_THRESHOLD = float(os.getenv("FAQ_MIN_SCORE", "0.65"))  # ✅ BUILD 96: Lowered from 0.78 to 0.65 for better Hebrew matching
AMBIGUITY_MARGIN = 0.05
FAQ_EMBEDDINGS_ENABLED = os.getenv("FAQ_EMBEDDINGS_ENABLED", "1") == "1"

def _normalize_patterns_defensive(payload):
    """
    Defensive normalization for patterns_json read from DB
    
    Handles malformed data gracefully:
    - None/null → []
    - String (JSON or plain) → attempt parse, fallback to []
    - List → clean and return
    - Anything else → []
    
    Never raises - returns empty list on any error
    """
    if payload is None or payload == "":
        return []
    
    if isinstance(payload, list):
        try:
            return [str(p).strip() for p in payload if p and str(p).strip()]
        except Exception:
            return []
    
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload.strip())
            if isinstance(parsed, list):
                return [str(p).strip() for p in parsed if p and str(p).strip()]
        except (json.JSONDecodeError, ValueError):
            pass
    
    return []

class FAQCacheEntry:
    """Single business FAQ cache entry"""
    def __init__(self, business_id: int, faqs: List[Dict], embeddings: np.ndarray):
        self.business_id = business_id
        self.faqs = faqs  # List of {id, question, answer, intent_key, patterns_json, channels, priority, lang}
        self.embeddings = embeddings  # 2D numpy array [n_faqs, embedding_dim]
        self.timestamp = time.time()
    
    def is_expired(self) -> bool:
        """Check if cache entry is older than TTL"""
        return (time.time() - self.timestamp) > FAQ_CACHE_TTL_SECONDS

class FAQCache:
    """Thread-safe FAQ cache with embeddings"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._cache = {}
                    cls._instance._cache_lock = threading.Lock()
                    cls._instance._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return cls._instance
    
    def _generate_embeddings(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for list of texts using OpenAI API"""
        if not texts:
            return np.array([])
        
        start = time.time()
        response = self._client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts
        )
        embeddings = np.array([item.embedding for item in response.data])
        elapsed = (time.time() - start) * 1000
        print(f"🔢 Generated {len(texts)} embeddings in {elapsed:.0f}ms")
        return embeddings
    
    def _load_business_faqs(self, business_id: int) -> Tuple[List[Dict], np.ndarray]:
        """Load FAQs from DB and generate embeddings (graceful degradation)"""
        faqs = FAQ.query.filter_by(business_id=business_id, is_active=True).order_by(FAQ.order_index.asc().nullsfirst()).all()
        
        if not faqs:
            print(f"📭 No FAQs found for business {business_id}")
            return [], np.array([])
        
        faq_data = [
            {
                "id": faq.id,
                "question": faq.question,
                "answer": faq.answer,
                "intent_key": faq.intent_key,
                "patterns_json": _normalize_patterns_defensive(faq.patterns_json),
                "channels": faq.channels,
                "priority": faq.priority,
                "lang": faq.lang
            }
            for faq in faqs
        ]
        
        # 🔥 CRITICAL FIX: Embeddings are optional - graceful degradation!
        embeddings = np.array([])
        if FAQ_EMBEDDINGS_ENABLED:
            try:
                questions = [faq.question for faq in faqs]
                embeddings = self._generate_embeddings(questions)
                print(f"✅ Loaded {len(faq_data)} FAQs with embeddings for business {business_id}")
            except Exception as e:
                print(f"⚠️ Embeddings failed for business {business_id}: {e}")
                print(f"✅ Loaded {len(faq_data)} FAQs (patterns-only mode) for business {business_id}")
        else:
            print(f"✅ Loaded {len(faq_data)} FAQs (patterns-only mode) for business {business_id}")
        
        return faq_data, embeddings
    
    def get_or_load(self, business_id: int) -> Optional[FAQCacheEntry]:
        """Get FAQs from cache or load from DB"""
        with self._cache_lock:
            entry = self._cache.get(business_id)
            
            if entry and not entry.is_expired():
                print(f"♻️  FAQ CACHE HIT for business {business_id}")
                return entry
            
            if entry:
                print(f"⏰ FAQ cache EXPIRED for business {business_id}, reloading...")
            else:
                print(f"🆕 FAQ cache MISS for business {business_id}, loading...")
        
        faqs, embeddings = self._load_business_faqs(business_id)
        
        if not faqs:
            return None
        
        entry = FAQCacheEntry(business_id, faqs, embeddings)
        
        with self._cache_lock:
            self._cache[business_id] = entry
        
        return entry
    
    def invalidate(self, business_id: int):
        """Invalidate cache for a business (call after FAQ CRUD operations)"""
        with self._cache_lock:
            if business_id in self._cache:
                del self._cache[business_id]
                print(f"🗑️  FAQ cache INVALIDATED for business {business_id}")
            else:
                print(f"ℹ️  No FAQ cache to invalidate for business {business_id}")
    
    def find_best_match(self, business_id: int, query: str) -> Optional[Dict]:
        """
        Find best matching FAQ using hybrid approach:
        1. Check patterns_json (keywords/regex) first - instant match!
        2. If no pattern match, use semantic similarity (embeddings)
        
        Returns:
            Dict with {question, answer, score} if match found above threshold, None otherwise
        """
        start = time.time()
        
        entry = self.get_or_load(business_id)
        if not entry or len(entry.faqs) == 0:
            print(f"⚠️ No FAQs available for business {business_id}")
            return None
        
        # 🔥 STEP 1: Check patterns_json (keywords/regex) - PRIORITY!
        query_lower = query.lower().strip()
        query_words = set(query_lower.split())  # Split into words for smart matching
        
        print(f"🔍 [FAQ DEBUG] Query words: {query_words}")
        
        for idx, faq in enumerate(entry.faqs):
            patterns = faq.get("patterns_json")
            if patterns and isinstance(patterns, list):
                print(f"  FAQ #{idx} '{faq['question'][:40]}...' has {len(patterns)} patterns")
                for pattern in patterns:
                    pattern_lower = str(pattern).lower().strip()
                    
                    # Method 1: Exact substring match (fast)
                    if pattern_lower in query_lower or query_lower in pattern_lower:
                        elapsed = (time.time() - start) * 1000
                        print(f"🎯 SUBSTRING MATCH! Pattern '{pattern}' (took {elapsed:.0f}ms)")
                        return {
                            "question": faq["question"],
                            "answer": faq["answer"],
                            "intent_key": faq.get("intent_key"),
                            "patterns_json": faq.get("patterns_json"),
                            "channels": faq.get("channels", "voice"),
                            "priority": faq.get("priority", 0),
                            "lang": faq.get("lang", "he-IL"),
                            "score": 1.0
                        }
                    
                    # Method 2: Smart keyword matching (if pattern has multiple words)
                    pattern_words = set(pattern_lower.split())
                    if len(pattern_words) >= 2:  # Only for multi-word patterns
                        # Remove common Hebrew stop words
                        stop_words = {"של", "את", "עם", "על", "אל", "מה", "איך", "למה", "איפה", "מתי"}
                        pattern_keywords = pattern_words - stop_words
                        
                        # Check how many keywords appear in query
                        matching_keywords = pattern_keywords & query_words
                        if len(matching_keywords) >= 2:  # At least 2 keywords must match
                            elapsed = (time.time() - start) * 1000
                            print(f"🎯 KEYWORD MATCH! Pattern '{pattern}' matched {len(matching_keywords)}/{len(pattern_keywords)} keywords: {matching_keywords} (took {elapsed:.0f}ms)")
                            return {
                                "question": faq["question"],
                                "answer": faq["answer"],
                                "intent_key": faq.get("intent_key"),
                                "patterns_json": faq.get("patterns_json"),
                                "channels": faq.get("channels", "voice"),
                                "priority": faq.get("priority", 0),
                                "lang": faq.get("lang", "he-IL"),
                                "score": 0.95  # Slightly lower than exact match
                            }
        
        print(f"📭 No keyword match found, trying embeddings...")
        
        # 🔥 STEP 2: Semantic similarity (embeddings) - FALLBACK
        query_embedding = self._generate_embeddings([query])
        
        if query_embedding.size == 0:
            print("⚠️ Failed to generate query embedding")
            return None
        
        similarities = np.dot(entry.embeddings, query_embedding[0])
        similarities = similarities / (np.linalg.norm(entry.embeddings, axis=1) * np.linalg.norm(query_embedding[0]))
        
        best_idx = np.argmax(similarities)
        best_score = similarities[best_idx]
        
        sorted_scores = np.sort(similarities)[::-1]
        second_best_score = sorted_scores[1] if len(sorted_scores) > 1 else 0.0
        
        elapsed = (time.time() - start) * 1000
        print(f"🔍 FAQ matching took {elapsed:.0f}ms")
        print(f"   Best match: score={best_score:.3f}, question='{entry.faqs[best_idx]['question']}'")
        
        if best_score < SIMILARITY_THRESHOLD:
            print(f"❌ Best score {best_score:.3f} below threshold {SIMILARITY_THRESHOLD}")
            return None
        
        if (best_score - second_best_score) < AMBIGUITY_MARGIN:
            print(f"⚠️ Ambiguous match: best={best_score:.3f}, second={second_best_score:.3f}, margin={best_score - second_best_score:.3f} < {AMBIGUITY_MARGIN}")
            return None
        
        matched_faq = entry.faqs[best_idx]
        return {
            "question": matched_faq["question"],
            "answer": matched_faq["answer"],
            "intent_key": matched_faq.get("intent_key"),
            "patterns_json": matched_faq.get("patterns_json"),
            "channels": matched_faq.get("channels", "voice"),
            "priority": matched_faq.get("priority", 0),
            "lang": matched_faq.get("lang", "he-IL"),
            "score": float(best_score)
        }

faq_cache = FAQCache()
