"""
FAQ Fast-Path Engine - Voice Calls Only
Multi-tenant FAQ matching with Hebrew normalization + hybrid scoring.
Target: 30-80ms response time.
"""
import os
import re
import time
import logging
from typing import Dict, List, Optional
from server.services.faq_cache import faq_cache, FAQ_EMBEDDINGS_ENABLED, SIMILARITY_THRESHOLD

logger = logging.getLogger(__name__)

FAQ_FASTPATH_ENABLED = os.getenv("FAQ_FASTPATH_ENABLED", "1") == "1"
MAX_QUERY_LENGTH = 200  # Skip FAQ matching for very long queries

def normalize_hebrew(text: str) -> str:
    """
    Normalize Hebrew text for matching:
    - Remove nikud (vowel points)
    - Remove punctuation
    - Lowercase
    - Condense whitespace
    Target: <5ms
    """
    if not text:
        return ""
    
    # Remove nikud (Hebrew vowel points: U+0591 to U+05C7)
    text = re.sub(r'[\u0591-\u05C7]', '', text)
    
    # Remove punctuation (keep Hebrew letters, numbers, spaces)
    text = re.sub(r'[^\u05D0-\u05EA\u0590-\u05FFa-zA-Z0-9\s]', ' ', text)
    
    # Lowercase and condense whitespace
    text = ' '.join(text.lower().split())
    
    return text

def keyword_score(query: str, patterns: List[str]) -> float:
    """
    Score query against keyword patterns using regex.
    Returns score 0.0-1.0 based on pattern matches.
    Target: <10ms
    """
    if not patterns:
        return 0.0
    
    normalized_query = normalize_hebrew(query)
    matches = 0
    
    for pattern in patterns:
        try:
            # Use pattern as-is (don't lowercase - it breaks regex metacharacters)
            # re.IGNORECASE handles case-insensitive matching
            if re.search(pattern, normalized_query, re.IGNORECASE):
                matches += 1
        except re.error:
            # Invalid regex pattern - skip
            logger.warning(f"Invalid regex pattern: {pattern}")
            continue
    
    # Score = percentage of patterns matched
    return matches / len(patterns) if patterns else 0.0

def match_faq(business_id: int, user_text: str, channel: str = "voice") -> Optional[Dict]:
    """
    Match user query to FAQ using hybrid scoring (embeddings + keywords).
    
    Args:
        business_id: Business ID for multi-tenant isolation
        user_text: User's query text
        channel: "voice" (only voice calls supported in fast-path)
    
    Returns:
        {
            "question": str,
            "answer": str,
            "score": float,
            "intent_key": str,
            "method": "embeddings" | "keywords"
        } or None if no match above threshold
    
    Target: 30-80ms total
    """
    start_time = time.time()
    
    # Validation
    if not FAQ_FASTPATH_ENABLED:
        logger.debug("FAQ fast-path is disabled")
        return None
    
    if not user_text or len(user_text) > MAX_QUERY_LENGTH:
        logger.debug(f"Query too long or empty: {len(user_text)} chars")
        return None
    
    if channel != "voice":
        logger.debug(f"FAQ fast-path only supports 'voice' channel, got: {channel}")
        return None
    
    # Try embeddings-based matching first (if enabled)
    if FAQ_EMBEDDINGS_ENABLED:
        try:
            result = faq_cache.find_best_match(business_id, user_text)
            if result:
                elapsed_ms = (time.time() - start_time) * 1000
                logger.info(f"[FAQ] EMBEDDINGS match biz={business_id} score={result['score']:.3f} ms={elapsed_ms:.0f}ms")
                result["method"] = "embeddings"
                # intent_key, channels, priority, lang already populated by find_best_match()
                return result
        except Exception as e:
            logger.warning(f"[FAQ] Embeddings failed, falling back to keywords: {e}")
    
    # Fallback: keyword/regex matching
    try:
        cache_entry = faq_cache.get_or_load(business_id)
        if not cache_entry or len(cache_entry.faqs) == 0:
            logger.debug(f"No FAQs available for business {business_id}")
            return None
        
        best_match = None
        best_score = 0.0
        
        for faq in cache_entry.faqs:
            # Check if FAQ is for voice channel
            faq_channels = faq.get("channels", "voice")
            if faq_channels not in ["voice", "both"]:
                continue
            
            # Get patterns for keyword matching
            patterns = faq.get("patterns_json", [])
            if not patterns:
                # No patterns - skip keyword matching
                continue
            
            # Calculate keyword score
            kw_score = keyword_score(user_text, patterns)
            
            # Apply priority boost (0-0.1 based on priority 0-10)
            priority = faq.get("priority", 0)
            priority_boost = min(priority / 100.0, 0.1)  # Max 0.1 boost
            
            final_score = kw_score + priority_boost
            
            if final_score > best_score:
                best_score = final_score
                best_match = faq
        
        if best_match and best_score >= SIMILARITY_THRESHOLD:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(f"[FAQ] KEYWORD match biz={business_id} score={best_score:.3f} ms={elapsed_ms:.0f}ms")
            return {
                "question": best_match["question"],
                "answer": best_match["answer"],
                "score": best_score,
                "intent_key": best_match.get("intent_key", "unknown"),
                "method": "keywords"
            }
        
        logger.debug(f"[FAQ] No match above threshold {SIMILARITY_THRESHOLD} (best: {best_score:.3f})")
        return None
        
    except Exception as e:
        logger.error(f"[FAQ] Keyword matching error: {e}", exc_info=True)
        return None
