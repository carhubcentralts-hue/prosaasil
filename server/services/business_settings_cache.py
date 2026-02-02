"""
Business Settings Cache - In-memory cache for business settings
🔥 PERFORMANCE OPTIMIZATION: Cache Business and BusinessSettings to reduce DB round trips
Follows the same pattern as prompt_cache.py for consistency
"""
import time
import logging
import threading
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Cache TTL in seconds (10 minutes - same as prompt cache)
CACHE_TTL_SECONDS = 600  # 10 minutes

# Maximum cache size to prevent memory leaks (bounded cache)
MAX_CACHE_SIZE = 1000


@dataclass
class CachedBusinessSettings:
    """Cached business and settings data"""
    business_id: int
    business_data: Dict[str, Any]  # Business model data (serialized)
    settings_data: Optional[Dict[str, Any]]  # BusinessSettings model data (serialized)
    cached_at: float
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        age = time.time() - self.cached_at
        return age > CACHE_TTL_SECONDS


class BusinessSettingsCache:
    """
    Thread-safe in-memory cache for Business and BusinessSettings
    
    Key: business_id (int)
    Value: CachedBusinessSettings with {business_data, settings_data}
    TTL: 10 minutes
    Eviction: LRU with bounded size (max 1000 entries)
    """
    
    def __init__(self):
        self._cache: Dict[int, CachedBusinessSettings] = {}
        self._access_order: Dict[int, float] = {}  # For LRU tracking
        self._lock = threading.RLock()
        logger.info("📦 [BUSINESS_SETTINGS_CACHE] Initialized")
    
    def get(self, business_id: int) -> Optional[Tuple[Dict[str, Any], Optional[Dict[str, Any]]]]:
        """
        Get cached business and settings data
        
        Args:
            business_id: Business ID
        
        Returns:
            Tuple of (business_data, settings_data) if found and not expired, None otherwise
        """
        with self._lock:
            entry = self._cache.get(business_id)
            if entry:
                if entry.is_expired():
                    # Expired - remove from cache
                    del self._cache[business_id]
                    if business_id in self._access_order:
                        del self._access_order[business_id]
                    logger.info(f"🗑️ [BUSINESS_SETTINGS_CACHE] Expired entry removed for business_id={business_id}")
                    return None
                else:
                    # Valid cache hit - update access time for LRU
                    self._access_order[business_id] = time.time()
                    age = time.time() - entry.cached_at
                    logger.info(f"✅ [BUSINESS_SETTINGS_CACHE] HIT for business_id={business_id} (age: {int(age)}s)")
                    return (entry.business_data, entry.settings_data)
            else:
                logger.info(f"❌ [BUSINESS_SETTINGS_CACHE] MISS for business_id={business_id}")
                return None
    
    def set(self, business_id: int, business_data: Dict[str, Any], 
            settings_data: Optional[Dict[str, Any]] = None):
        """
        Cache business and settings data
        
        Args:
            business_id: Business ID
            business_data: Serialized Business model data
            settings_data: Optional serialized BusinessSettings model data
        """
        with self._lock:
            # Check cache size and evict oldest if at limit (LRU)
            if len(self._cache) >= MAX_CACHE_SIZE and business_id not in self._cache:
                self._evict_oldest()
            
            entry = CachedBusinessSettings(
                business_id=business_id,
                business_data=business_data,
                settings_data=settings_data,
                cached_at=time.time()
            )
            self._cache[business_id] = entry
            self._access_order[business_id] = time.time()
            
            has_settings = "with settings" if settings_data else "without settings"
            logger.info(f"💾 [BUSINESS_SETTINGS_CACHE] SET for business_id={business_id} ({has_settings})")
    
    def invalidate(self, business_id: int):
        """
        Invalidate cache entry for a business
        
        Args:
            business_id: Business ID to invalidate
        
        Call this when business or settings are updated
        """
        with self._lock:
            if business_id in self._cache:
                del self._cache[business_id]
                if business_id in self._access_order:
                    del self._access_order[business_id]
                logger.info(f"🗑️ [BUSINESS_SETTINGS_CACHE] Invalidated cache for business_id={business_id}")
    
    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._access_order.clear()
            logger.info(f"🗑️ [BUSINESS_SETTINGS_CACHE] Cleared {count} entries")
    
    def _evict_oldest(self):
        """Evict the least recently used entry (LRU)"""
        if not self._access_order:
            return
        
        # Find the entry with the oldest access time
        oldest_id = min(self._access_order.items(), key=lambda x: x[1])[0]
        
        if oldest_id in self._cache:
            del self._cache[oldest_id]
        if oldest_id in self._access_order:
            del self._access_order[oldest_id]
        
        logger.info(f"🗑️ [BUSINESS_SETTINGS_CACHE] Evicted oldest entry: business_id={oldest_id}")
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total = len(self._cache)
            expired = sum(1 for e in self._cache.values() if e.is_expired())
            return {
                "total_entries": total,
                "expired_entries": expired,
                "valid_entries": total - expired,
                "max_size": MAX_CACHE_SIZE
            }


# Global singleton cache instance
_global_cache: Optional[BusinessSettingsCache] = None
_cache_lock = threading.Lock()


def get_business_settings_cache() -> BusinessSettingsCache:
    """
    Get global business settings cache singleton
    
    Returns:
        Global BusinessSettingsCache instance
    """
    global _global_cache
    
    if _global_cache is None:
        with _cache_lock:
            if _global_cache is None:
                _global_cache = BusinessSettingsCache()
    
    return _global_cache
