"""
Topic Classifier Service

Semantic topic classification using OpenAI embeddings with 2-layer matching:
1. Fast keyword/synonym match (free, instant)
2. Embedding-based semantic matching (if no exact match)

Features:
- Per-business topic management (~200 topics)
- Keyword/synonym pre-filtering for common cases
- Embedding-based semantic matching (cosine similarity)
- In-memory caching with TTL (30 minutes default)
- Automatic embedding generation for new topics
- Post-call classification (not real-time)
- Idempotency protection
"""
import os
import time
import threading
import numpy as np
import json
from typing import Dict, List, Optional, Tuple
from openai import OpenAI
from server.models_sql import BusinessTopic, BusinessAISettings, db

# Configuration
TOPIC_CACHE_TTL_SECONDS = int(os.getenv("TOPIC_CACHE_TTL_SEC", "1800"))  # 30 minutes default
EMBEDDING_MODEL = "text-embedding-3-small"  # Fixed model, not configurable
DEFAULT_THRESHOLD = 0.78
DEFAULT_TOP_K = 3


class TopicCacheEntry:
    """Single business topic cache entry"""
    def __init__(self, business_id: int, topics: List[Dict], embeddings: np.ndarray):
        self.business_id = business_id
        self.topics = topics  # List of {id, name, synonyms, keywords}
        self.embeddings = embeddings  # 2D numpy array [n_topics, embedding_dim]
        self.timestamp = time.time()
    
    def is_expired(self) -> bool:
        """Check if cache entry is older than TTL"""
        return (time.time() - self.timestamp) > TOPIC_CACHE_TTL_SECONDS


class TopicClassifier:
    """Thread-safe topic classifier with 2-layer matching and embeddings cache"""
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
        print(f"🔢 Generated {len(texts)} topic embeddings in {elapsed:.0f}ms")
        return embeddings
    
    def _extract_keywords(self, text: str) -> set:
        """Extract keywords from text (lowercase, split by whitespace)"""
        # Remove common stop words
        stop_words = {"של", "את", "עם", "על", "אל", "מה", "איך", "למה", "איפה", "מתי", "אני", "אתה", "הוא", "היא", "אנחנו", "אתם", "הם"}
        words = text.lower().split()
        return set(w for w in words if w not in stop_words and len(w) > 1)
    
    def _keyword_match(self, text: str, topics: List[Dict]) -> Optional[Dict]:
        """
        LAYER 1: Fast keyword/synonym matching (free, instant)
        Returns topic with high confidence if exact match found
        """
        text_lower = text.lower()
        text_keywords = self._extract_keywords(text)
        
        for topic in topics:
            # Check exact name match
            topic_name_lower = topic['name'].lower()
            if topic_name_lower in text_lower:
                print(f"🎯 KEYWORD MATCH (name): '{topic['name']}' found in text")
                return {
                    "topic_id": topic['id'],
                    "topic_name": topic['name'],
                    "score": 0.95,  # High confidence for exact match
                    "method": "keyword",
                    "top_matches": [{
                        "topic_id": topic['id'],
                        "topic_name": topic['name'],
                        "score": 0.95
                    }]
                }
            
            # Check synonyms match
            if topic.get('synonyms'):
                for synonym in topic['synonyms']:
                    synonym_lower = synonym.lower().strip()
                    if synonym_lower and synonym_lower in text_lower:
                        print(f"🎯 SYNONYM MATCH: '{synonym}' (topic: {topic['name']})")
                        return {
                            "topic_id": topic['id'],
                            "topic_name": topic['name'],
                            "score": 0.93,  # Slightly lower than exact name match
                            "method": "synonym",
                            "top_matches": [{
                                "topic_id": topic['id'],
                                "topic_name": topic['name'],
                                "score": 0.93
                            }]
                        }
            
            # Check multi-keyword match (at least 2 keywords must match)
            topic_keywords = self._extract_keywords(topic['name'])
            if topic.get('synonyms'):
                for syn in topic['synonyms']:
                    topic_keywords.update(self._extract_keywords(syn))
            
            matching_keywords = text_keywords & topic_keywords
            if len(matching_keywords) >= 2 and len(topic_keywords) > 0:
                match_ratio = len(matching_keywords) / len(topic_keywords)
                if match_ratio >= 0.5:  # At least 50% of topic keywords must appear
                    print(f"🎯 MULTI-KEYWORD MATCH: {matching_keywords} (topic: {topic['name']}, ratio: {match_ratio:.2f})")
                    return {
                        "topic_id": topic['id'],
                        "topic_name": topic['name'],
                        "score": 0.85 + (match_ratio * 0.05),  # 0.85-0.90 based on match ratio
                        "method": "multi_keyword",
                        "top_matches": [{
                            "topic_id": topic['id'],
                            "topic_name": topic['name'],
                            "score": 0.85 + (match_ratio * 0.05)
                        }]
                    }
        
        return None
    
    def _load_business_topics(self, business_id: int) -> Tuple[List[Dict], np.ndarray, BusinessAISettings]:
        """Load topics from DB and generate embeddings if needed"""
        # Load AI settings
        ai_settings = BusinessAISettings.query.filter_by(business_id=business_id).first()
        
        if not ai_settings or not ai_settings.embedding_enabled:
            print(f"📭 Topic classification disabled for business {business_id}")
            return [], np.array([]), ai_settings
        
        # Load active topics
        topics = BusinessTopic.query.filter_by(
            business_id=business_id, 
            is_active=True
        ).all()
        
        if not topics:
            print(f"📭 No topics found for business {business_id}")
            return [], np.array([]), ai_settings
        
        topic_data = []
        embeddings_list = []
        needs_update = []
        
        for topic in topics:
            # Parse existing embedding if available (stored as JSONB array)
            existing_embedding = None
            if topic.embedding:
                try:
                    if isinstance(topic.embedding, str):
                        existing_embedding = json.loads(topic.embedding)
                    elif isinstance(topic.embedding, list):
                        existing_embedding = topic.embedding
                    
                    if existing_embedding and len(existing_embedding) == 1536:  # text-embedding-3-small dimension
                        embeddings_list.append(existing_embedding)
                    else:
                        needs_update.append(topic.id)
                        existing_embedding = None
                except (json.JSONDecodeError, TypeError) as e:
                    print(f"⚠️ Failed to parse embedding for topic {topic.id}: {e}")
                    needs_update.append(topic.id)
            else:
                needs_update.append(topic.id)
            
            topic_data.append({
                "id": topic.id,
                "name": topic.name,
                "synonyms": topic.synonyms if isinstance(topic.synonyms, list) else [],
                "has_embedding": existing_embedding is not None
            })
        
        # If some embeddings are missing, generate for ALL topics (more efficient)
        if needs_update or len(embeddings_list) != len(topic_data):
            print(f"💾 Generating embeddings for {len(topic_data)} topics...")
            texts_to_embed = []
            for topic in topic_data:
                # Combine name with synonyms for richer embedding
                text = topic["name"]
                if topic["synonyms"]:
                    text += " " + " ".join(topic["synonyms"])
                texts_to_embed.append(text)
            
            embeddings = self._generate_embeddings(texts_to_embed)
            
            # Save ALL embeddings back to DB in one transaction
            if embeddings.size > 0:
                for i, topic_dict in enumerate(topic_data):
                    db_topic = BusinessTopic.query.get(topic_dict["id"])
                    if db_topic:
                        db_topic.embedding = embeddings[i].tolist()  # Store as JSONB array
                
                db.session.commit()
                print(f"✅ Saved {len(topic_data)} embeddings for business {business_id}")
        else:
            embeddings = np.array(embeddings_list)
            print(f"✅ Loaded {len(topic_data)} topics with cached embeddings for business {business_id}")
        
        return topic_data, embeddings, ai_settings
    
    def get_or_build_topics_index(self, business_id: int) -> Optional[TopicCacheEntry]:
        """Get topics from cache or load from DB"""
        with self._cache_lock:
            entry = self._cache.get(business_id)
            
            if entry and not entry.is_expired():
                print(f"♻️  TOPIC CACHE HIT for business {business_id}")
                return entry
            
            if entry:
                print(f"⏰ Topic cache EXPIRED for business {business_id}, reloading...")
            else:
                print(f"🆕 Topic cache MISS for business {business_id}, loading...")
        
        topics, embeddings, ai_settings = self._load_business_topics(business_id)
        
        if not topics or embeddings.size == 0:
            return None
        
        entry = TopicCacheEntry(business_id, topics, embeddings)
        
        with self._cache_lock:
            self._cache[business_id] = entry
        
        return entry
    
    def invalidate_cache(self, business_id: int):
        """Invalidate cache for a business (call after topic CRUD operations)"""
        with self._cache_lock:
            if business_id in self._cache:
                del self._cache[business_id]
                print(f"🗑️  Topic cache INVALIDATED for business {business_id}")
            else:
                print(f"ℹ️  No topic cache to invalidate for business {business_id}")
    
    def classify_text(self, business_id: int, text: str) -> Optional[Dict]:
        """
        Classify text into a topic using 2-layer approach:
        1. Fast keyword/synonym matching (free, instant)
        2. Semantic similarity with embeddings (if no keyword match)
        
        Args:
            business_id: Business ID
            text: Text to classify (e.g., final transcript)
        
        Returns:
            Dict with {topic_id, topic_name, score, method, top_matches} if match found, None otherwise
        """
        if not text or not text.strip():
            print(f"⚠️ Empty text provided for classification")
            return None
        
        start = time.time()
        
        entry = self.get_or_build_topics_index(business_id)
        if not entry or len(entry.topics) == 0:
            print(f"⚠️ No topics available for business {business_id}")
            return None
        
        # Get AI settings for threshold
        ai_settings = BusinessAISettings.query.filter_by(business_id=business_id).first()
        if not ai_settings:
            print(f"⚠️ No AI settings found for business {business_id}")
            return None
        
        threshold = ai_settings.embedding_threshold
        top_k = ai_settings.embedding_top_k
        
        # LAYER 1: Try keyword/synonym matching first (FREE & INSTANT)
        keyword_result = self._keyword_match(text, entry.topics)
        if keyword_result:
            elapsed = (time.time() - start) * 1000
            print(f"✅ LAYER 1 (keyword) matched in {elapsed:.0f}ms")
            return keyword_result
        
        # LAYER 2: No keyword match - use embeddings (SEMANTIC MATCHING)
        print(f"📭 No keyword match, trying embeddings (Layer 2)...")
        
        # Generate embedding for input text
        query_embedding = self._generate_embeddings([text])
        
        if query_embedding.size == 0:
            print("⚠️ Failed to generate query embedding")
            return None
        
        # Calculate cosine similarity
        similarities = np.dot(entry.embeddings, query_embedding[0])
        similarities = similarities / (np.linalg.norm(entry.embeddings, axis=1) * np.linalg.norm(query_embedding[0]))
        
        # Get top K matches
        top_indices = np.argsort(similarities)[::-1][:top_k]
        top_matches = [
            {
                "topic_id": entry.topics[idx]["id"],
                "topic_name": entry.topics[idx]["name"],
                "score": float(similarities[idx])
            }
            for idx in top_indices
        ]
        
        best_match = top_matches[0]
        best_score = best_match["score"]
        
        elapsed = (time.time() - start) * 1000
        print(f"🔍 Topic classification took {elapsed:.0f}ms (Layer 2 - embeddings)")
        print(f"   Best match: score={best_score:.3f}, topic='{best_match['topic_name']}'")
        
        if best_score < threshold:
            print(f"❌ Best score {best_score:.3f} below threshold {threshold}")
            return None
        
        return {
            "topic_id": best_match["topic_id"],
            "topic_name": best_match["topic_name"],
            "score": best_score,
            "method": "embedding",
            "top_matches": top_matches
        }
        """
        Classify text into a topic using semantic similarity
    
    def rebuild_all_embeddings(self, business_id: int) -> Dict:
        """
        Rebuild embeddings for all topics of a business
        
        Returns:
            Dict with {success, topics_updated, message}
        """
        print(f"🔨 Rebuilding embeddings for business {business_id}...")
        
        try:
            # Invalidate cache first
            self.invalidate_cache(business_id)
            
            # Load topics and regenerate embeddings
            topics, embeddings, ai_settings = self._load_business_topics(business_id)
            
            if not topics:
                return {
                    "success": False,
                    "topics_updated": 0,
                    "message": "No active topics found"
                }
            
            # Save to cache
            if embeddings.size > 0:
                entry = TopicCacheEntry(business_id, topics, embeddings)
                with self._cache_lock:
                    self._cache[business_id] = entry
            
            return {
                "success": True,
                "topics_updated": len(topics),
                "message": f"Successfully rebuilt embeddings for {len(topics)} topics"
            }
        
        except Exception as e:
            print(f"❌ Error rebuilding embeddings: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "topics_updated": 0,
                "message": f"Error: {str(e)}"
            }


# Singleton instance
topic_classifier = TopicClassifier()
