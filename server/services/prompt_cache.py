"""
Prompt Cache - In-memory cache for business prompts and greetings
🔥 GREETING OPTIMIZATION: Pre-compute and cache prompts to eliminate DB/prompt building latency
"""
import time
import logging
import threading
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Cache TTL in seconds (5-10 minutes)
CACHE_TTL_SECONDS = 600  # 10 minutes


@dataclass
class CachedPrompt:
    """Cached prompt data for a business"""
    business_id: int
    system_prompt: str
    greeting_text: str
    language_config: Dict[str, Any]
    cached_at: float
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        age = time.time() - self.cached_at
        return age > CACHE_TTL_SECONDS


class PromptCache:
    """
    Thread-safe in-memory cache for business prompts
    
    Key: business_id
    Value: CachedPrompt with {system_prompt, greeting_text, language_config}
    TTL: 10 minutes
    """
    
    def __init__(self):
        self._cache: Dict[int, CachedPrompt] = {}
        self._lock = threading.RLock()
        logger.info("📦 [PROMPT_CACHE] Initialized")
    
    def get(self, business_id: int) -> Optional[CachedPrompt]:
        """
        Get cached prompt for a business
        
        Returns:
            CachedPrompt if found and not expired, None otherwise
        """
        with self._lock:
            entry = self._cache.get(business_id)
            if entry:
                if entry.is_expired():
                    # Expired - remove from cache
                    del self._cache[business_id]
                    logger.info(f"🗑️ [PROMPT_CACHE] Expired entry removed for business {business_id}")
                    return None
                else:
                    # Valid cache hit
                    age = time.time() - entry.cached_at
                    logger.info(f"✅ [PROMPT_CACHE] HIT for business {business_id} (age: {int(age)}s)")
                    return entry
            else:
                logger.info(f"❌ [PROMPT_CACHE] MISS for business {business_id}")
                return None
    
    def set(self, business_id: int, system_prompt: str, greeting_text: str, 
            language_config: Optional[Dict[str, Any]] = None):
        """
        Cache prompt data for a business
        
        Args:
            business_id: Business ID
            system_prompt: Full system prompt for Realtime API
            greeting_text: Greeting text to use
            language_config: Optional language configuration
        """
        with self._lock:
            entry = CachedPrompt(
                business_id=business_id,
                system_prompt=system_prompt,
                greeting_text=greeting_text,
                language_config=language_config or {},
                cached_at=time.time()
            )
            self._cache[business_id] = entry
            logger.info(f"💾 [PROMPT_CACHE] SET for business {business_id} (prompt: {len(system_prompt)} chars, greeting: {len(greeting_text)} chars)")
    
    def invalidate(self, business_id: int):
        """
        Invalidate cache entry for a business
        
        Call this when business settings change
        """
        with self._lock:
            if business_id in self._cache:
                del self._cache[business_id]
                logger.info(f"🗑️ [PROMPT_CACHE] Invalidated cache for business {business_id}")
    
    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"🗑️ [PROMPT_CACHE] Cleared {count} entries")
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total = len(self._cache)
            expired = sum(1 for e in self._cache.values() if e.is_expired())
            return {
                "total_entries": total,
                "expired_entries": expired,
                "valid_entries": total - expired
            }


# Global singleton cache instance
_global_cache: Optional[PromptCache] = None
_cache_lock = threading.Lock()


def get_prompt_cache() -> PromptCache:
    """
    Get global prompt cache singleton
    
    Returns:
        Global PromptCache instance
    """
    global _global_cache
    
    if _global_cache is None:
        with _cache_lock:
            if _global_cache is None:
                _global_cache = PromptCache()
    
    return _global_cache
