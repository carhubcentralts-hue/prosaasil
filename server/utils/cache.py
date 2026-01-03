"""
Simple in-memory TTL cache for AI settings to prevent bottlenecks
Reduces database queries for frequently accessed business settings
"""
import time
import threading
from typing import Any, Optional, Dict, Tuple

class TTLCache:
    """
    Thread-safe Time-To-Live cache implementation
    Stores values with expiration timestamps
    """
    def __init__(self, ttl_seconds: int = 120, max_size: int = 2000):
        """
        Initialize TTL cache
        
        Args:
            ttl_seconds: Time-to-live in seconds (default: 120s = 2 minutes)
            max_size: Maximum number of entries (default: 2000)
        """
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._cache: Dict[Any, Tuple[Any, float]] = {}
        self._lock = threading.Lock()
    
    def get(self, key: Any) -> Optional[Any]:
        """
        Get value from cache if not expired
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                return None
            
            value, expiry = self._cache[key]
            
            # Check if expired
            if time.time() > expiry:
                del self._cache[key]
                return None
            
            return value
    
    def set(self, key: Any, value: Any) -> None:
        """
        Set value in cache with TTL
        
        Args:
            key: Cache key
            value: Value to cache
        """
        with self._lock:
            # Enforce max size with simple eviction
            # Note: This removes the first inserted item (FIFO), not true LRU
            # For production workload with high hit rate, FIFO is acceptable
            if len(self._cache) >= self.max_size and key not in self._cache:
                # Remove first (oldest) entry
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            
            expiry = time.time() + self.ttl_seconds
            self._cache[key] = (value, expiry)
    
    def delete(self, key: Any) -> None:
        """
        Remove key from cache (for invalidation)
        
        Args:
            key: Cache key to remove
        """
        with self._lock:
            self._cache.pop(key, None)
    
    def clear(self) -> None:
        """Clear all cached entries"""
        with self._lock:
            self._cache.clear()
    
    def __contains__(self, key: Any) -> bool:
        """Check if key exists and is not expired"""
        return self.get(key) is not None
    
    def size(self) -> int:
        """Get current cache size"""
        with self._lock:
            return len(self._cache)
