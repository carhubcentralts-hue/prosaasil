"""
Lightweight Playback Deduplication
===================================

Simple, UX-friendly deduplication for media playback operations.

Unlike BulkGate which is for heavy bulk operations, this is designed for
user-facing playback actions where we want to prevent duplicate requests
but NOT block legitimate user retries.

Key Differences from BulkGate:
- Very short TTL (15 seconds default)
- Per-resource deduplication (e.g., per call_sid)
- No rate limiting (users can play different recordings)
- No 429 errors - just returns existing operation status
- Logs at DEBUG level to avoid noise

Usage:
    from server.services.playback_dedup import get_playback_dedup
    
    dedup = get_playback_dedup(redis_client)
    
    # Check if already in progress
    in_progress, ttl = dedup.is_in_progress(
        resource_type='recording',
        resource_id=call_sid,
        business_id=business_id
    )
    
    if in_progress:
        # Return 202 with "processing" status
        return jsonify({"status": "processing"}), 202
    
    # Mark as in progress
    dedup.mark_in_progress(
        resource_type='recording',
        resource_id=call_sid,
        business_id=business_id,
        ttl=15  # 15 seconds
    )
"""
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class PlaybackDedup:
    """
    Lightweight deduplication for playback operations
    
    Prevents duplicate downloads/processing of the same resource
    within a short time window (10-30 seconds).
    
    This is UX-friendly - allows user retries after short wait,
    doesn't count against rate limits, and focuses only on
    preventing actual duplicate work.
    """
    
    # Default TTL for in-progress markers
    DEFAULT_TTL = 15  # 15 seconds - short enough for UX
    
    def __init__(self, redis_client):
        """
        Initialize PlaybackDedup
        
        Args:
            redis_client: Redis connection instance
        """
        self.redis = redis_client
    
    def is_in_progress(
        self,
        resource_type: str,
        resource_id: str,
        business_id: int
    ) -> Tuple[bool, int]:
        """
        Check if resource is currently being processed
        
        Args:
            resource_type: Type of resource ('recording', 'video', etc.)
            resource_id: Unique ID of resource (call_sid, video_id, etc.)
            business_id: Business ID for isolation
        
        Returns:
            (in_progress: bool, ttl_seconds: int)
        """
        key = f"playback:inprogress:{business_id}:{resource_type}:{resource_id}"
        
        if self.redis.exists(key):
            ttl = self.redis.ttl(key)
            logger.debug(
                f"⏳ PLAYBACK_DEDUP: In progress "
                f"type={resource_type} id={resource_id} ttl={ttl}s"
            )
            # Return 0 if TTL is -1 (key exists with no expiry) or -2 (key doesn't exist)
            # These shouldn't happen since we always set TTL, but handle gracefully
            return True, max(ttl, 0)
        
        return False, 0
    
    def mark_in_progress(
        self,
        resource_type: str,
        resource_id: str,
        business_id: int,
        ttl: Optional[int] = None
    ):
        """
        Mark resource as being processed
        
        Args:
            resource_type: Type of resource
            resource_id: Unique ID of resource
            business_id: Business ID for isolation
            ttl: Time-to-live in seconds (default: 15s)
        """
        key = f"playback:inprogress:{business_id}:{resource_type}:{resource_id}"
        ttl = ttl or self.DEFAULT_TTL
        
        self.redis.setex(key, ttl, "processing")
        
        logger.debug(
            f"▶️  PLAYBACK_DEDUP: Marked in progress "
            f"type={resource_type} id={resource_id} ttl={ttl}s"
        )
    
    def mark_complete(
        self,
        resource_type: str,
        resource_id: str,
        business_id: int
    ):
        """
        Mark resource as completed (removes in-progress marker)
        
        Args:
            resource_type: Type of resource
            resource_id: Unique ID of resource
            business_id: Business ID for isolation
        """
        key = f"playback:inprogress:{business_id}:{resource_type}:{resource_id}"
        deleted = self.redis.delete(key)
        
        if deleted:
            logger.debug(
                f"✅ PLAYBACK_DEDUP: Marked complete "
                f"type={resource_type} id={resource_id}"
            )


# Singleton instance
_playback_dedup_instance: Optional[PlaybackDedup] = None


def get_playback_dedup(redis_client=None) -> Optional[PlaybackDedup]:
    """
    Get or create PlaybackDedup singleton instance
    
    Args:
        redis_client: Redis connection (required on first call)
    
    Returns:
        PlaybackDedup instance or None if Redis not available
    """
    global _playback_dedup_instance
    
    if _playback_dedup_instance is None:
        if redis_client is None:
            logger.warning("PlaybackDedup: Redis client not provided, dedup disabled")
            return None
        
        _playback_dedup_instance = PlaybackDedup(redis_client)
        logger.info("✅ PlaybackDedup initialized")
    
    return _playback_dedup_instance
