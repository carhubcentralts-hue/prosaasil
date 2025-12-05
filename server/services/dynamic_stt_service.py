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


def get_business_vocabulary(business_id: int) -> Dict[str, List[str]]:
    """
    Load business vocabulary from database
    
    Returns dict with keys: services, staff, products, locations
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
    Build a dynamic, business-specific STT prompt for OpenAI transcription
    
    Best practices from OpenAI research:
    - Keep prompt under 120 chars for optimal performance
    - Include business name, type, and key terminology
    - Use Hebrew with minimal English
    - Focus on "what to extract" not vocabulary lists
    
    Args:
        business_id: Business ID
        active_task: Current task context (e.g., "booking", "inquiry")
    
    Returns:
        Dynamic transcription prompt string
    """
    vocab = get_business_vocabulary(business_id)
    
    business_name = vocab.get("business_name", "")
    business_type = vocab.get("business_type", "general")
    business_context = vocab.get("business_context", "")
    
    # Build compact prompt (aim for ~80-100 chars)
    parts = []
    
    # Core context
    if business_context:
        parts.append(f"שיחה עם {business_context}.")
    elif business_name:
        parts.append(f"שיחה עם {business_name}.")
    else:
        parts.append("שיחה עברית.")
    
    # Key vocabulary hints (max 3-5 terms)
    hints = []
    
    # Add a few service hints
    services = vocab.get("services", [])[:3]
    if services:
        hints.extend(services)
    
    # Add staff names (first 2)
    staff = vocab.get("staff", [])[:2]
    if staff:
        hints.extend(staff)
    
    # Add product hints (first 2)
    products = vocab.get("products", [])[:2]
    if products:
        hints.extend(products)
    
    if hints:
        parts.append(f"מונחים: {', '.join(hints[:5])}.")
    
    # Task context
    if active_task:
        task_hints = {
            "booking": "קביעת תור",
            "inquiry": "שאלות",
            "support": "תמיכה",
            "sales": "מכירות"
        }
        task_text = task_hints.get(active_task, active_task)
        parts.append(f"נושא: {task_text}.")
    
    # Always end with Hebrew preference
    parts.append("העדף עברית.")
    
    prompt = " ".join(parts)
    
    # Ensure prompt stays under 120 chars
    if len(prompt) > 120:
        # Truncate hints
        prompt = f"שיחה עברית עם {business_name or 'עסק'}. העדף עברית."
    
    logger.debug(f"📝 [STT-PROMPT] Built prompt for business {business_id}: '{prompt}' ({len(prompt)} chars)")
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
        
        corrected = response.choices[0].message.content.strip()
        
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
) -> str:
    """
    Apply fast vocabulary-based corrections using fuzzy matching
    
    This is the fast path that runs BEFORE semantic post-processing.
    Uses RapidFuzz for near-matches to business vocabulary.
    
    Args:
        transcript: Original transcript
        business_id: Business ID
    
    Returns:
        Corrected transcript
    """
    if not transcript or len(transcript.strip()) < 2:
        return transcript
    
    try:
        from rapidfuzz import fuzz, process
        
        vocab = get_business_vocabulary(business_id)
        
        # Build vocabulary list for matching
        all_terms = []
        all_terms.extend(vocab.get("services", []))
        all_terms.extend(vocab.get("staff", []))
        all_terms.extend(vocab.get("products", []))
        all_terms.extend(vocab.get("locations", []))
        
        if not all_terms:
            return transcript
        
        # Split transcript into words and try to match each
        words = transcript.split()
        corrected_words = []
        corrections_made = False
        
        for word in words:
            if len(word) < 3:
                corrected_words.append(word)
                continue
            
            # Try fuzzy match
            result = process.extractOne(
                word,
                all_terms,
                scorer=fuzz.ratio,
                score_cutoff=75  # 75% threshold for vocabulary matching
            )
            
            if result:
                matched_term, score, _ = result
                if score >= 75 and matched_term != word:
                    logger.debug(f"🔧 [VOCAB-FIX] '{word}' → '{matched_term}' ({score:.0f}%)")
                    corrected_words.append(matched_term)
                    corrections_made = True
                else:
                    corrected_words.append(word)
            else:
                corrected_words.append(word)
        
        if corrections_made:
            result = " ".join(corrected_words)
            logger.info(f"🔧 [VOCAB-FIX] Applied vocabulary corrections for business {business_id}")
            return result
        
        return transcript
        
    except ImportError:
        logger.debug("⚠️ RapidFuzz not available for vocabulary corrections")
        return transcript
    except Exception as e:
        logger.warning(f"⚠️ [VOCAB-FIX] Failed: {e}")
        return transcript


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
