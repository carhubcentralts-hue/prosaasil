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
    direction: str  # 'inbound' or 'outbound'
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
    
    Key: f"{business_id}:{direction}" (e.g., "123:inbound" or "123:outbound")
    Value: CachedPrompt with {system_prompt, greeting_text, language_config}
    TTL: 10 minutes
    """
    
    def __init__(self):
        self._cache: Dict[str, CachedPrompt] = {}
        self._lock = threading.RLock()
        logger.info("📦 [PROMPT_CACHE] Initialized")
    
    def _make_cache_key(self, business_id: int, direction: str = "inbound") -> str:
        """Create cache key from business_id and direction"""
        return f"{business_id}:{direction}"
    
    def get(self, business_id: int, direction: str = "inbound") -> Optional[CachedPrompt]:
        """
        Get cached prompt for a business and direction
        
        Args:
            business_id: Business ID
            direction: Call direction ('inbound' or 'outbound')
        
        Returns:
            CachedPrompt if found and not expired, None otherwise
        """
        cache_key = self._make_cache_key(business_id, direction)
        with self._lock:
            entry = self._cache.get(cache_key)
            if entry:
                if entry.is_expired():
                    # Expired - remove from cache
                    del self._cache[cache_key]
                    logger.info(f"🗑️ [PROMPT_CACHE] Expired entry removed for {cache_key}")
                    return None
                else:
                    # Valid cache hit
                    age = time.time() - entry.cached_at
                    logger.info(f"✅ [PROMPT_CACHE] HIT for {cache_key} (age: {int(age)}s)")
                    return entry
            else:
                logger.info(f"❌ [PROMPT_CACHE] MISS for {cache_key}")
                return None
    
    def set(self, business_id: int, system_prompt: str, greeting_text: str, 
            direction: str = "inbound", language_config: Optional[Dict[str, Any]] = None):
        """
        Cache prompt data for a business and direction
        
        Args:
            business_id: Business ID
            system_prompt: Full system prompt for Realtime API
            greeting_text: Greeting text to use
            direction: Call direction ('inbound' or 'outbound')
            language_config: Optional language configuration
        """
        cache_key = self._make_cache_key(business_id, direction)
        with self._lock:
            entry = CachedPrompt(
                business_id=business_id,
                direction=direction,
                system_prompt=system_prompt,
                greeting_text=greeting_text,
                language_config=language_config or {},
                cached_at=time.time()
            )
            self._cache[cache_key] = entry
            logger.info(f"💾 [PROMPT_CACHE] SET for {cache_key} (prompt: {len(system_prompt)} chars, greeting: {len(greeting_text)} chars)")
    
    def invalidate(self, business_id: int, direction: Optional[str] = None):
        """
        Invalidate cache entry for a business
        
        Args:
            business_id: Business ID
            direction: Optional direction to invalidate specific entry. 
                      If None, invalidates both inbound and outbound.
        
        Call this when business settings change
        """
        with self._lock:
            if direction:
                # Invalidate specific direction
                cache_key = self._make_cache_key(business_id, direction)
                if cache_key in self._cache:
                    del self._cache[cache_key]
                    logger.info(f"🗑️ [PROMPT_CACHE] Invalidated cache for {cache_key}")
            else:
                # Invalidate both directions
                for dir_name in ["inbound", "outbound"]:
                    cache_key = self._make_cache_key(business_id, dir_name)
                    if cache_key in self._cache:
                        del self._cache[cache_key]
                        logger.info(f"🗑️ [PROMPT_CACHE] Invalidated cache for {cache_key}")
    
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
