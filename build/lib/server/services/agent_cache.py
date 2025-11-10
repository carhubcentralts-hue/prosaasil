"""
Agent Cache Service - Persistent Agent instances for better performance
Keeps Agent SDK instances alive across multiple conversation turns
"""
import logging
import threading
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AgentCache:
    """
    Thread-safe cache for Agent instances
    
    Key structure: "{business_id}:{channel}"
    - Reuses Agent across multiple turns for same business+channel
    - Automatically expires agents after 30 minutes of inactivity
    - Thread-safe for concurrent access
    """
    
    def __init__(self, ttl_minutes: int = 30):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self.ttl_seconds = ttl_minutes * 60
        logger.info(f"✅ AgentCache initialized (TTL: {ttl_minutes} minutes)")
    
    def _make_key(self, business_id: int, channel: str) -> str:
        """Generate cache key from business_id and channel"""
        return f"{business_id}:{channel}"
    
    def get(self, business_id: int, channel: str):
        """
        Get cached agent if available and not expired
        
        Returns:
            Agent instance or None if not cached/expired
        """
        key = self._make_key(business_id, channel)
        
        with self._lock:
            entry = self._cache.get(key)
            
            if not entry:
                logger.debug(f"❌ Cache MISS: {key}")
                return None
            
            # Check expiration
            age_seconds = time.time() - entry['timestamp']
            if age_seconds > self.ttl_seconds:
                # Expired - remove from cache
                logger.info(f"⏰ Cache EXPIRED: {key} (age: {age_seconds:.0f}s)")
                del self._cache[key]
                return None
            
            # Update last access time
            entry['last_access'] = time.time()
            entry['hits'] += 1
            
            logger.info(f"✅ Cache HIT: {key} (age: {age_seconds:.0f}s, hits: {entry['hits']})")
            return entry['agent']
    
    def set(self, business_id: int, channel: str, agent, business_name: str = ""):
        """
        Cache an agent instance
        
        Args:
            business_id: Business ID
            channel: Channel (calls/whatsapp)
            agent: Agent SDK instance to cache
            business_name: Optional business name for logging
        """
        key = self._make_key(business_id, channel)
        
        with self._lock:
            self._cache[key] = {
                'agent': agent,
                'business_id': business_id,
                'business_name': business_name,
                'channel': channel,
                'timestamp': time.time(),
                'last_access': time.time(),
                'hits': 0
            }
            logger.info(f"💾 Cache SET: {key} (business: {business_name}, total cached: {len(self._cache)})")
    
    def invalidate(self, business_id: int, channel: str = None):
        """
        Invalidate cached agent(s) for a business
        
        Args:
            business_id: Business ID
            channel: If provided, only invalidate specific channel. If None, invalidate all channels for this business.
        """
        with self._lock:
            if channel:
                # Invalidate specific channel
                key = self._make_key(business_id, channel)
                if key in self._cache:
                    del self._cache[key]
                    logger.info(f"🗑️  Cache INVALIDATED: {key}")
            else:
                # Invalidate all channels for this business
                keys_to_remove = [k for k in self._cache.keys() if k.startswith(f"{business_id}:")]
                for key in keys_to_remove:
                    del self._cache[key]
                    logger.info(f"🗑️  Cache INVALIDATED: {key}")
    
    def cleanup_expired(self):
        """Remove all expired entries from cache"""
        with self._lock:
            now = time.time()
            expired_keys = []
            
            for key, entry in self._cache.items():
                age = now - entry['timestamp']
                if age > self.ttl_seconds:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                logger.info(f"🧹 Cleaned up {len(expired_keys)} expired agents")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            return {
                'total_cached': len(self._cache),
                'entries': [
                    {
                        'business_id': entry['business_id'],
                        'business_name': entry['business_name'],
                        'channel': entry['channel'],
                        'age_seconds': int(time.time() - entry['timestamp']),
                        'last_access_seconds': int(time.time() - entry['last_access']),
                        'hits': entry['hits']
                    }
                    for entry in self._cache.values()
                ]
            }

# Global singleton instance
_agent_cache = None
_cache_lock = threading.Lock()

def get_agent_cache() -> AgentCache:
    """Get global AgentCache singleton"""
    global _agent_cache
    
    if _agent_cache is None:
        with _cache_lock:
            if _agent_cache is None:  # Double-check locking
                _agent_cache = AgentCache(ttl_minutes=30)
    
    return _agent_cache
