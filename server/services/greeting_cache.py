# -*- coding: utf-8 -*-
"""
⚡ BUILD 117 - Greeting Cache Service
Thread-safe in-memory cache for pre-built greeting audio frames
Stores greetings as lists of μ-law 20ms frames (base64 encoded)
"""
import base64
import hashlib
import threading
import time
from typing import Dict, Tuple, List, Optional

# Constants
MU_FRAME_MS = 20    # 20ms per frame
SAMPLE_RATE = 8000  # 8kHz
BYTES_PER_FR = 160  # μ-law 8kHz -> 160B for 20ms

# Cache key: (business_id, locale, voice_id, text_hash)
Key = Tuple[str, str, str, str]


class GreetingCache:
    """
    Thread-safe in-memory cache for greeting audio frames.
    
    Features:
    - LRU eviction when cache is full
    - Thread-safe operations with RLock
    - Fast lookup by business/voice/text hash
    """
    
    def __init__(self, max_businesses: int = 256):
        """
        Initialize the greeting cache.
        
        Args:
            max_businesses: Maximum number of greeting variations to cache
        """
        self._lock = threading.RLock()
        self._data: Dict[Key, List[str]] = {}  # Key -> List of base64 frames
        self._meta: Dict[Key, float] = {}      # Key -> last_access_time for LRU
        self._max = max_businesses
        print(f"✅ GreetingCache initialized (max_businesses={max_businesses})")
    
    @staticmethod
    def make_key(business_id: str, locale: str, voice_id: str, text: str) -> Key:
        """
        Create a cache key from greeting parameters.
        
        Args:
            business_id: Business identifier
            locale: Language/locale (e.g., "he-IL")
            voice_id: TTS voice identifier
            text: Greeting text
            
        Returns:
            Tuple key for cache lookup
        """
        # Hash the text to keep key size small
        text_hash = hashlib.sha256(text.strip().encode('utf-8')).hexdigest()[:16]
        return (str(business_id), locale, voice_id, text_hash)
    
    def get(self, key: Key) -> Optional[List[str]]:
        """
        Retrieve cached greeting frames.
        
        Args:
            key: Cache key
            
        Returns:
            List of base64-encoded audio frames, or None if not in cache
        """
        with self._lock:
            frames = self._data.get(key)
            if frames:
                # Update access time for LRU
                self._meta[key] = time.time()
                print(f"✅ CACHE HIT for business={key[0]}, frames={len(frames)}")
            return frames
    
    def put(self, key: Key, frames: List[str]) -> None:
        """
        Store greeting frames in cache.
        
        Args:
            key: Cache key
            frames: List of base64-encoded audio frames
        """
        with self._lock:
            # LRU cleanup if cache is full and this is a new key
            if key not in self._data and len(self._data) >= self._max:
                # Find and remove oldest entry
                oldest_key = min(self._meta, key=lambda k: self._meta.get(k, 0.0))
                self._data.pop(oldest_key, None)
                self._meta.pop(oldest_key, None)
                print(f"⚠️ LRU eviction: removed key for business={oldest_key[0]}")
            
            # Store new/updated data
            self._data[key] = frames
            self._meta[key] = time.time()
            print(f"✅ CACHED greeting for business={key[0]}, frames={len(frames)}")
    
    def invalidate_business(self, business_id: str) -> int:
        """
        Remove all cached greetings for a specific business.
        
        Args:
            business_id: Business identifier
            
        Returns:
            Number of cache entries removed
        """
        with self._lock:
            # Find all keys for this business
            keys_to_del = [k for k in self._data if k[0] == str(business_id)]
            
            # Remove them
            for k in keys_to_del:
                self._data.pop(k, None)
                self._meta.pop(k, None)
            
            if keys_to_del:
                print(f"✅ Invalidated {len(keys_to_del)} cache entries for business={business_id}")
            
            return len(keys_to_del)
    
    def get_stats(self) -> Dict:
        """Get cache statistics for monitoring."""
        with self._lock:
            return {
                'total_entries': len(self._data),
                'max_entries': self._max,
                'utilization_pct': (len(self._data) / self._max * 100) if self._max > 0 else 0
            }
