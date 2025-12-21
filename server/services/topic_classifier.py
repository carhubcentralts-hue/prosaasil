"""
Topic Classifier Service

Semantic topic classification using OpenAI embeddings.
Classifies transcripts into business-specific topics (e.g., "locksmith", "plumber", etc.)

Features:
- Per-business topic management (~200 topics)
- Embedding-based semantic matching (cosine similarity)
- In-memory caching with TTL (10-30 minutes)
- Automatic embedding generation for new topics
- Post-call classification (not real-time)
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
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_THRESHOLD = 0.78
DEFAULT_TOP_K = 3


class TopicCacheEntry:
    """Single business topic cache entry"""
    def __init__(self, business_id: int, topics: List[Dict], embeddings: np.ndarray):
        self.business_id = business_id
        self.topics = topics  # List of {id, name, synonyms}
        self.embeddings = embeddings  # 2D numpy array [n_topics, embedding_dim]
        self.timestamp = time.time()
    
    def is_expired(self) -> bool:
        """Check if cache entry is older than TTL"""
        return (time.time() - self.timestamp) > TOPIC_CACHE_TTL_SECONDS


class TopicClassifier:
    """Thread-safe topic classifier with embeddings cache"""
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
    
    def _generate_embeddings(self, texts: List[str], model: str = DEFAULT_EMBEDDING_MODEL) -> np.ndarray:
        """Generate embeddings for list of texts using OpenAI API"""
        if not texts:
            return np.array([])
        
        start = time.time()
        response = self._client.embeddings.create(
            model=model,
            input=texts
        )
        embeddings = np.array([item.embedding for item in response.data])
        elapsed = (time.time() - start) * 1000
        print(f"🔢 Generated {len(texts)} topic embeddings in {elapsed:.0f}ms")
        return embeddings
    
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
        needs_embedding_update = False
        
        for topic in topics:
            # Parse existing embedding if available
            existing_embedding = None
            if topic.embedding:
                try:
                    existing_embedding = json.loads(topic.embedding)
                except (json.JSONDecodeError, TypeError):
                    print(f"⚠️ Failed to parse embedding for topic {topic.id}")
                    needs_embedding_update = True
            else:
                needs_embedding_update = True
            
            topic_data.append({
                "id": topic.id,
                "name": topic.name,
                "synonyms": topic.synonyms or [],
                "existing_embedding": existing_embedding
            })
        
        # Generate embeddings for all topics (including synonyms)
        texts_to_embed = []
        for topic in topic_data:
            # Combine name with synonyms for richer embedding
            text = topic["name"]
            if topic["synonyms"]:
                text += " " + " ".join(topic["synonyms"])
            texts_to_embed.append(text)
        
        embeddings = self._generate_embeddings(texts_to_embed, ai_settings.embedding_model)
        
        # Save embeddings back to DB if they were missing
        if needs_embedding_update and embeddings.size > 0:
            print(f"💾 Saving embeddings for {len(topic_data)} topics...")
            for i, topic in enumerate(topic_data):
                db_topic = BusinessTopic.query.get(topic["id"])
                if db_topic:
                    db_topic.embedding = json.dumps(embeddings[i].tolist())
            db.session.commit()
            print(f"✅ Embeddings saved for business {business_id}")
        
        print(f"✅ Loaded {len(topic_data)} topics with embeddings for business {business_id}")
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
        Classify text into a topic using semantic similarity
        
        Args:
            business_id: Business ID
            text: Text to classify (e.g., final transcript)
        
        Returns:
            Dict with {topic_id, topic_name, score, top_matches} if match found, None otherwise
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
        
        # Generate embedding for input text
        query_embedding = self._generate_embeddings([text], ai_settings.embedding_model)
        
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
        print(f"🔍 Topic classification took {elapsed:.0f}ms")
        print(f"   Best match: score={best_score:.3f}, topic='{best_match['topic_name']}'")
        
        if best_score < threshold:
            print(f"❌ Best score {best_score:.3f} below threshold {threshold}")
            return None
        
        return {
            "topic_id": best_match["topic_id"],
            "topic_name": best_match["topic_name"],
            "score": best_score,
            "top_matches": top_matches
        }
    
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
