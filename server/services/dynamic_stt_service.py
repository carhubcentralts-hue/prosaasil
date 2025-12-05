"""
BUILD 204: Dynamic STT Enhancement Service
Provides business-specific transcription improvements using:
1. Dynamic STT prompts based on business vocabulary
2. GPT-4o-mini semantic post-processing for low-confidence transcripts
3. 100% database-driven - zero hardcoded values
"""
import logging
import json
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
import os

logger = logging.getLogger(__name__)

# Cache for business vocabularies (thread-safe with simple dict)
_vocabulary_cache: Dict[int, Dict] = {}
_cache_expiry: Dict[int, float] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


@dataclass
class STTEnhancement:
    """Result of STT enhancement"""
    original_text: str
    enhanced_text: str
    confidence: float
    corrections_made: List[str]
    semantic_fix_applied: bool


def get_business_vocabulary(business_id: int) -> Dict[str, Any]:
    """
    Load business vocabulary from database
    
    Returns dict with keys: services, staff, products, locations, business_name, business_type, business_context
    All 100% from DB - no hardcoded values
    """
    import time
    
    # Check cache
    now = time.time()
    if business_id in _vocabulary_cache:
        if now < _cache_expiry.get(business_id, 0):
            return _vocabulary_cache[business_id]
    
    try:
        from server.models_sql import BusinessSettings, Business
        
        settings = BusinessSettings.query.filter_by(tenant_id=business_id).first()
        business = Business.query.get(business_id)
        
        vocab = {
            "services": [],
            "staff": [],
            "products": [],
            "locations": [],
            "business_name": business.name if business else "",
            "business_type": business.business_type if business else "general",
            "business_context": ""
        }
        
        if settings:
            # Load vocabulary JSON
            if settings.stt_vocabulary_json:
                try:
                    stt_vocab = settings.stt_vocabulary_json
                    if isinstance(stt_vocab, str):
                        stt_vocab = json.loads(stt_vocab)
                    
                    vocab["services"] = stt_vocab.get("services", [])
                    vocab["staff"] = stt_vocab.get("staff", [])
                    vocab["products"] = stt_vocab.get("products", [])
                    vocab["locations"] = stt_vocab.get("locations", [])
                    logger.info(f"✅ [STT-VOCAB] Loaded vocabulary for business {business_id}: "
                               f"{len(vocab['services'])} services, {len(vocab['staff'])} staff")
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"⚠️ [STT-VOCAB] Invalid JSON for business {business_id}: {e}")
            
            # Load business context
            if settings.business_context:
                vocab["business_context"] = settings.business_context
        
        # Cache result
        _vocabulary_cache[business_id] = vocab
        _cache_expiry[business_id] = now + CACHE_TTL_SECONDS
        
        return vocab
        
    except Exception as e:
        logger.error(f"❌ [STT-VOCAB] Failed to load vocabulary for business {business_id}: {e}")
        return {
            "services": [],
            "staff": [],
            "products": [],
            "locations": [],
            "business_name": "",
            "business_type": "general",
            "business_context": ""
        }


def build_dynamic_stt_prompt(business_id: int, active_task: str = "") -> str:
    """
    Build a TELEPHONY-OPTIMIZED STT prompt for OpenAI transcription
    
    🔥 BUILD 206: Expert recommendations for 8kHz G.711 μ-law telephony:
    - Keep prompt VERY short (under 100 chars)
    - Focus on BEHAVIOR not vocabulary lists
    - Tell model what NOT to do (prevent hallucinations)
    - Business name + 4-6 key terms MAX
    
    Args:
        business_id: Business ID
        active_task: Current task context (e.g., "booking", "inquiry")
    
    Returns:
        Telephony-optimized transcription prompt
    """
    vocab = get_business_vocabulary(business_id)
    
    business_name = vocab.get("business_name", "")
    
    # 🔥 BUILD 206: TELEPHONY-OPTIMIZED prompt structure
    # Core instruction: behavior-focused, not vocabulary-focused
    # Expert recommendation: "תמלל עברית בשיחה טלפונית. הימנע מהוספת מילים."
    
    # Start with core telephony instruction
    prompt_parts = ["תמלל עברית בשיחה טלפונית."]
    
    # Add business context (very brief)
    if business_name:
        prompt_parts.append(f"עסק: {business_name}.")
    
    # Add ONLY 4-6 key hints (expert recommendation)
    hints = []
    services = vocab.get("services", [])[:3]
    staff = vocab.get("staff", [])[:2]
    if services:
        hints.extend(services)
    if staff:
        hints.extend(staff)
    
    if hints:
        prompt_parts.append(f"מילים: {', '.join(hints[:5])}.")
    
    # Critical: anti-hallucination instruction
    prompt_parts.append("רק תמלל, לא להוסיף.")
    
    prompt = " ".join(prompt_parts)
    
    # Ensure prompt stays under 100 chars for optimal performance
    if len(prompt) > 100:
        prompt = f"תמלל עברית טלפונית. עסק: {business_name[:15] if business_name else 'כללי'}. רק תמלל."
    
    logger.debug(f"📝 [STT-PROMPT] Telephony prompt for business {business_id}: '{prompt}' ({len(prompt)} chars)")
    return prompt


async def semantic_post_process(
    transcript: str,
    business_id: int,
    confidence: float = 1.0,
    min_confidence_for_fix: float = 0.7
) -> STTEnhancement:
    """
    Post-process transcript using GPT-4o-mini for semantic correction
    
    Only applies to low-confidence transcripts to avoid latency on good transcriptions.
    Uses business vocabulary for context-aware corrections.
    
    Args:
        transcript: Original transcript text
        business_id: Business ID for vocabulary lookup
        confidence: Transcript confidence (0-1)
        min_confidence_for_fix: Only process if confidence below this threshold
    
    Returns:
        STTEnhancement with original and corrected text
    """
    # Fast path: high confidence transcripts pass through
    if confidence >= min_confidence_for_fix or not transcript or len(transcript.strip()) < 3:
        return STTEnhancement(
            original_text=transcript,
            enhanced_text=transcript,
            confidence=confidence,
            corrections_made=[],
            semantic_fix_applied=False
        )
    
    try:
        import openai
        
        vocab = get_business_vocabulary(business_id)
        
        # Build context for GPT
        context_parts = []
        if vocab["business_name"]:
            context_parts.append(f"עסק: {vocab['business_name']}")
        if vocab["business_type"] != "general":
            context_parts.append(f"סוג: {vocab['business_type']}")
        if vocab["services"]:
            context_parts.append(f"שירותים: {', '.join(vocab['services'][:5])}")
        if vocab["staff"]:
            context_parts.append(f"צוות: {', '.join(vocab['staff'][:3])}")
        if vocab["products"]:
            context_parts.append(f"מוצרים: {', '.join(vocab['products'][:3])}")
        
        context = " | ".join(context_parts) if context_parts else "עסק כללי"
        
        # Call GPT-4o-mini for semantic fix
        client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=100,
            messages=[
                {
                    "role": "system",
                    "content": f"""אתה מתקן תמלולים עבריים. הקשר: {context}
תפקידך: תקן שגיאות תמלול ברורות בהתאם להקשר העסקי.
כללים:
1. רק תקן טעויות ברורות (כמו "תפורת" → "תספורת")
2. אל תוסיף או תמציא מילים
3. אם הטקסט נכון או לא ברור - החזר אותו כמו שהוא
4. החזר רק את הטקסט המתוקן, בלי הסברים"""
                },
                {
                    "role": "user",
                    "content": f"תקן: {transcript}"
                }
            ]
        )
        
        corrected = (response.choices[0].message.content or "").strip()
        
        # Track corrections
        corrections = []
        if corrected != transcript:
            corrections.append(f"'{transcript}' → '{corrected}'")
            logger.info(f"🔧 [SEMANTIC-FIX] Corrected for business {business_id}: {corrections[0]}")
        
        return STTEnhancement(
            original_text=transcript,
            enhanced_text=corrected,
            confidence=confidence,
            corrections_made=corrections,
            semantic_fix_applied=len(corrections) > 0
        )
        
    except Exception as e:
        logger.warning(f"⚠️ [SEMANTIC-FIX] Failed for business {business_id}: {e}")
        # Return original on failure
        return STTEnhancement(
            original_text=transcript,
            enhanced_text=transcript,
            confidence=confidence,
            corrections_made=[],
            semantic_fix_applied=False
        )


def apply_vocabulary_corrections(
    transcript: str,
    business_id: int
) -> tuple[str, Dict[str, str]]:
    """
    Apply fast vocabulary-based corrections using fuzzy matching
    
    🔥 BUILD 204: CONSERVATIVE APPROACH - Only fix obvious near-misses, never damage critical data
    
    NEVER TOUCH:
    - Numbers (phone numbers, times, dates, amounts)
    - Very short tokens (< 3 chars)
    - Words that are already exact matches
    - Pure punctuation
    
    Args:
        transcript: Original transcript
        business_id: Business ID
    
    Returns:
        Tuple of (corrected_transcript, corrections_dict)
    """
    import re
    
    if not transcript or len(transcript.strip()) < 2:
        return transcript, {}
    
    try:
        from rapidfuzz import fuzz, process
        
        vocab = get_business_vocabulary(business_id)
        
        # Build vocabulary set for matching
        dictionary = set()
        for key in ("services", "products", "staff", "locations"):
            for item in vocab.get(key) or []:
                item = (item or "").strip()
                if item:
                    dictionary.add(item)
        
        if not dictionary:
            return transcript, {}
        
        words = transcript.split()
        corrections = {}
        corrected_words = []
        
        for w in words:
            # Strip punctuation for matching, but preserve it
            clean = w.strip(".,!?;:\"'")
            
            # 🔒 SAFETY: Skip tokens we should NEVER modify
            # 1. Too short (< 3 chars)
            if len(clean) < 3:
                corrected_words.append(w)
                continue
            
            # 2. Contains digits (times, dates, phone numbers, amounts)
            if re.search(r'\d', clean):
                corrected_words.append(w)
                continue
            
            # 3. Looks like a phone number pattern
            if re.match(r'^[\d\-\+\(\)]+$', clean):
                corrected_words.append(w)
                continue
            
            # 4. Already an exact match in vocabulary
            if clean in dictionary:
                corrected_words.append(w)
                continue
            
            # 5. Pure Hebrew numbers (שתיים, שלוש, etc.) - don't modify!
            hebrew_numbers = ["אחד", "אחת", "שתיים", "שניים", "שלוש", "שלושה", "ארבע", "ארבעה",
                           "חמש", "חמישה", "שש", "שישה", "שבע", "שבעה", "שמונה", "תשע", "תשעה",
                           "עשר", "עשרה", "עשרים", "שלושים", "ארבעים", "חמישים", "מאה", "אלף"]
            if clean in hebrew_numbers:
                corrected_words.append(w)
                continue
            
            # Try fuzzy match with conservative threshold
            result = process.extractOne(
                clean,
                dictionary,
                scorer=fuzz.WRatio,  # 🔥 WRatio is better for Hebrew partial matches
                score_cutoff=78  # 78% threshold - conservative
            )
            
            if result:
                matched_term, score, _ = result
                # Only correct if it's a clear win
                if score >= 78 and matched_term != clean:
                    # Preserve original punctuation
                    if w.endswith(tuple(".,!?;:\"\'")):
                        new_word = matched_term + w[-1]
                    else:
                        new_word = matched_term
                    
                    corrections[clean] = matched_term
                    corrected_words.append(new_word)
                    logger.info(f"🔧 [STT_CORRECTION] original='{clean}', corrected='{matched_term}', score={score:.0f}, business_id={business_id}")
                else:
                    corrected_words.append(w)
            else:
                corrected_words.append(w)
        
        corrected_text = " ".join(corrected_words)
        
        if corrections:
            logger.info(f"🔧 [VOCAB-FIX] Applied {len(corrections)} corrections for business {business_id}: {corrections}")
        
        return corrected_text, corrections
        
    except ImportError:
        logger.debug("⚠️ RapidFuzz not available for vocabulary corrections")
        return transcript, {}
    except Exception as e:
        logger.warning(f"⚠️ [VOCAB-FIX] Failed: {e}")
        return transcript, {}


def clear_vocabulary_cache(business_id: Optional[int] = None):
    """Clear vocabulary cache (call after settings update)"""
    global _vocabulary_cache, _cache_expiry
    
    if business_id:
        _vocabulary_cache.pop(business_id, None)
        _cache_expiry.pop(business_id, None)
        logger.info(f"🗑️ Cleared STT vocabulary cache for business {business_id}")
    else:
        _vocabulary_cache.clear()
        _cache_expiry.clear()
        logger.info("🗑️ Cleared all STT vocabulary caches")
