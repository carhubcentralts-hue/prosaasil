# -*- coding: utf-8 -*-
"""
⚡ BUILD 117 - Greeting Builder Service
Builds and caches pre-computed greeting audio frames
Falls back to live TTS if cache fails
"""
import logging
from typing import List, Callable, Optional

from .greeting_cache import GreetingCache
from .audio_utils import pcm16_to_frames

log = logging.getLogger("greeting_builder")

# Global cache instance
_greeting_cache = GreetingCache(max_businesses=256)


def get_cached_greeting_frames(
    business_id: str,
    locale: str,
    voice_id: str,
    greeting_text: str,
    tts_synth_func: Callable[[str], Optional[bytes]]
) -> List[str]:
    """
    Get pre-built greeting frames from cache or build them.
    
    Args:
        business_id: Business identifier
        locale: Language locale (e.g., "he-IL")
        voice_id: TTS voice identifier (e.g., "he-IL-Wavenet-D")
        greeting_text: Greeting text to synthesize
        tts_synth_func: Function that synthesizes text and returns PCM16 bytes
                       Should accept (text: str) and return bytes or None
    
    Returns:
        List of base64-encoded μ-law 20ms audio frames
        
    Raises:
        Exception: If both cache lookup and TTS synthesis fail
    """
    # Create cache key
    key = GreetingCache.make_key(business_id, locale, voice_id, greeting_text)
    
    # Try cache first
    cached = _greeting_cache.get(key)
    if cached:
        log.info(f"✅ CACHE HIT for business={business_id}, {len(cached)} frames")
        return cached
    
    # Cache miss - need to synthesize
    log.info(f"❌ CACHE MISS for business={business_id}, synthesizing...")
    
    try:
        # Call TTS to get PCM16 audio
        pcm16_bytes = tts_synth_func(greeting_text)
        
        if not pcm16_bytes:
            raise Exception("TTS returned no audio data")
        
        # Convert to μ-law frames
        # Note: TTS already returns 8kHz PCM16, so source_rate=8000
        frames = pcm16_to_frames(pcm16_bytes, source_rate=8000)
        
        if not frames:
            raise Exception("No frames generated from audio")
        
        # Cache for next time
        _greeting_cache.put(key, frames)
        
        log.info(f"✅ SYNTHESIZED & CACHED: business={business_id}, {len(frames)} frames")
        return frames
        
    except Exception as e:
        log.error(f"❌ Failed to build greeting for business={business_id}: {e}")
        raise


def invalidate_greeting_for_business(business_id: str) -> int:
    """
    Remove cached greetings for a business.
    
    Call this when business greeting/voice settings change.
    
    Args:
        business_id: Business identifier
        
    Returns:
        Number of cache entries removed
    """
    count = _greeting_cache.invalidate_business(business_id)
    log.info(f"Invalidated {count} greeting(s) for business={business_id}")
    return count


def get_cache_stats() -> dict:
    """
    Get greeting cache statistics.
    
    Returns:
        Dictionary with cache stats
    """
    return _greeting_cache.get_stats()
