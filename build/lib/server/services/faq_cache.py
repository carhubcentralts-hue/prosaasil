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
from typing import Dict, List, Optional, Tuple
from openai import OpenAI
from server.models_sql import FAQ, db

# ENV-based configuration
FAQ_CACHE_TTL_SECONDS = int(os.getenv("FAQ_CACHE_TTL_SEC", "120"))
EMBEDDING_MODEL = "text-embedding-3-small"
SIMILARITY_THRESHOLD = float(os.getenv("FAQ_MIN_SCORE", "0.78"))
AMBIGUITY_MARGIN = 0.05
FAQ_EMBEDDINGS_ENABLED = os.getenv("FAQ_EMBEDDINGS_ENABLED", "1") == "1"

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
        """Load FAQs from DB and generate embeddings"""
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
                "patterns_json": faq.patterns_json,
                "channels": faq.channels,
                "priority": faq.priority,
                "lang": faq.lang
            }
            for faq in faqs
        ]
        
        questions = [faq.question for faq in faqs]
        embeddings = self._generate_embeddings(questions)
        
        print(f"✅ Loaded {len(faq_data)} FAQs for business {business_id}")
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
        Find best matching FAQ using semantic similarity.
        
        Returns:
            Dict with {question, answer, score} if match found above threshold, None otherwise
        """
        start = time.time()
        
        entry = self.get_or_load(business_id)
        if not entry or len(entry.faqs) == 0:
            print(f"⚠️ No FAQs available for business {business_id}")
            return None
        
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
