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

# 🔥 SEMANTIC REPAIR CONSTANTS
MIN_VOCAB_LENGTH = 3  # Minimum vocabulary string length to attempt repair
SEMANTIC_REPAIR_ENABLED = False  # 🔥 DISABLED by requirement - too risky without strong confidence signals


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
        
        # 🔥 BUILD 307: Separate single-word and multi-word vocabulary
        # This prevents duplication when matching individual words to multi-word terms
        single_word_vocab = set()
        multi_word_vocab = set()
        for term in dictionary:
            if ' ' in term:
                multi_word_vocab.add(term)
            else:
                single_word_vocab.add(term)
        
        # 🔥 BUILD 307: First, check for multi-word matches in the full transcript
        # Replace them before individual word processing
        transcript_corrected = transcript
        for multi_term in multi_word_vocab:
            # Use fuzzy matching to find similar multi-word phrases
            term_words = multi_term.split()
            if len(term_words) == 2:
                # Build pattern for 2-word terms with word boundaries
                for i in range(len(words) - 1):
                    candidate = words[i] + " " + words[i+1]
                    candidate_clean = ' '.join(w.strip(".,!?;:\"'") for w in candidate.split())
                    score = fuzz.ratio(candidate_clean, multi_term)
                    if score >= 78:
                        # Mark these words as part of multi-word match (don't process individually)
                        # Just note it for logging
                        pass
        
        i = 0
        while i < len(words):
            w = words[i]
            # Strip punctuation for matching, but preserve it
            clean = w.strip(".,!?;:\"'")
            
            # 🔒 SAFETY: Skip tokens we should NEVER modify
            # 1. Too short (< 3 chars)
            if len(clean) < 3:
                corrected_words.append(w)
                i += 1
                continue
            
            # 2. Contains digits (times, dates, phone numbers, amounts)
            if re.search(r'\d', clean):
                corrected_words.append(w)
                i += 1
                continue
            
            # 3. Looks like a phone number pattern
            if re.match(r'^[\d\-\+\(\)]+$', clean):
                corrected_words.append(w)
                i += 1
                continue
            
            # 4. Already an exact match in vocabulary
            if clean in dictionary:
                corrected_words.append(w)
                i += 1
                continue
            
            # 5. Pure Hebrew numbers (שתיים, שלוש, etc.) - don't modify!
            hebrew_numbers = ["אחד", "אחת", "שתיים", "שניים", "שלוש", "שלושה", "ארבע", "ארבעה",
                           "חמש", "חמישה", "שש", "שישה", "שבע", "שבעה", "שמונה", "תשע", "תשעה",
                           "עשר", "עשרה", "עשרים", "שלושים", "ארבעים", "חמישים", "מאה", "אלף"]
            if clean in hebrew_numbers:
                corrected_words.append(w)
                i += 1
                continue
            
            # 🔥 BUILD 307: Check if current word is PART of a multi-word vocab term
            # If next words form a multi-word match, skip individual replacement
            is_part_of_multiword = False
            if i < len(words) - 1:
                for mw in multi_word_vocab:
                    mw_parts = mw.split()
                    if len(mw_parts) >= 2:
                        # Check if current position matches start of multi-word term
                        candidate_words = words[i:i+len(mw_parts)]
                        if len(candidate_words) == len(mw_parts):
                            candidate = ' '.join(cw.strip(".,!?;:\"'") for cw in candidate_words)
                            score = fuzz.ratio(candidate, mw)
                            if score >= 78:
                                # This is already a multi-word match - don't modify
                                is_part_of_multiword = True
                                # Keep original words
                                for cw in candidate_words:
                                    corrected_words.append(cw)
                                i += len(mw_parts)
                                break
            
            if is_part_of_multiword:
                continue
            
            # 🔥 BUILD 307: Only match against single-word vocabulary to avoid duplication
            # Skip matching if the only matches are multi-word terms
            result = process.extractOne(
                clean,
                single_word_vocab if single_word_vocab else dictionary,  # Fallback to all if no single words
                scorer=fuzz.WRatio,  # 🔥 WRatio is better for Hebrew partial matches
                score_cutoff=78  # 78% threshold - conservative
            )
            
            if result:
                matched_term, score, _ = result
                # Only correct if it's a clear win AND matched term is single word
                if score >= 78 and matched_term != clean and ' ' not in matched_term:
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
            
            i += 1
        
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


async def semantic_repair(text: str, business_id: int) -> str:
    """
    🔥 BUILD 301: 100% DYNAMIC semantic repair - uses ONLY business vocabulary
    🔥 FIX: More conservative to prevent changing valid Hebrew words
    🔥 NEW REQUIREMENT: DISABLED by default - too risky without confidence signals
    
    This function is DISABLED to prevent "I said X and it became Y" issues.
    Semantic repair without strong confidence signals (RMS, VAD stability) is too risky.
    
    To re-enable:
    1. Set SEMANTIC_REPAIR_ENABLED = True at module level
    2. Add confidence signal checks (RMS threshold, VAD stability)
    3. Use strict whitelist of known fixes only
    
    Args:
        text: Short transcript to repair (typically < 12 chars or 1-2 tokens)
        business_id: Business ID for vocabulary context
    
    Returns:
        Original text unchanged (repair disabled)
    """
    # 🔥 REQUIREMENT: Disable semantic repair - too risky without confidence signals
    if not SEMANTIC_REPAIR_ENABLED:
        logger.debug(f"[SEMANTIC_REPAIR] DISABLED globally - returning original text: '{text}'")
        return text
    
    if not text or len(text.strip()) < 2:
        return text
    
    try:
        import openai
        import re
        
        vocab = get_business_vocabulary(business_id)
        
        # Build vocabulary context
        vocab_items = []
        for key in ["services", "staff", "products", "locations"]:
            vocab_items.extend(vocab.get(key, [])[:5])
        vocab_str = ", ".join(vocab_items[:15]) if vocab_items else ""
        
        # 🔥 FIX: If no vocabulary, skip semantic repair
        # Don't try to repair without business context - too risky
        if not vocab_str or len(vocab_str.strip()) < MIN_VOCAB_LENGTH:
            logger.debug(f"[SEMANTIC_REPAIR] Skipping - no vocabulary for business {business_id}")
            return text
        
        business_context = vocab.get("business_context", "") or ""
        business_name = vocab.get("business_name", "") or ""
        
        # 🔥 BUILD 301: 100% DYNAMIC repair prompt - uses ONLY business vocabulary
        # 🔥 FIX: More conservative instructions - only fix if VERY confident
        prompt = f"""תמלול קצר מקו טלפון עברי (רועש).
משימה:
1. תקן רק אם אתה 100% בטוח שיש שגיאת תמלול ברורה.
2. השתמש רק באוצר המילים של העסק למטה.
3. אל תשנה מספרים, שעות, תאריכים, או מילים נפוצות.
4. אם לא בטוח לחלוטין - החזר כמו שזה ללא שינוי.

עסק: {business_name}
הקשר: {business_context}
מילים: {vocab_str}

החזר רק את הטקסט המתוקן (או המקורי אם לא בטוח).

קלט: "{text}"
"""
        
        client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            max_tokens=20,
            messages=[{"role": "user", "content": prompt}]
        )
        
        repaired = (response.choices[0].message.content or "").strip()
        
        # Remove quotes if the model added them
        if repaired.startswith('"') and repaired.endswith('"'):
            repaired = repaired[1:-1]
        if repaired.startswith("'") and repaired.endswith("'"):
            repaired = repaired[1:-1]
        
        # 🔥 FIX: Only apply repair if it seems like a real fix, not a random change
        # Don't repair if:
        # - Same text returned
        # - Only whitespace/punctuation differences
        # - Length changed by more than 50% (suspicious)
        if repaired and repaired != text:
            text_normalized = text.strip().replace(" ", "")
            repaired_normalized = repaired.strip().replace(" ", "")
            
            # Skip if only whitespace changed
            if text_normalized == repaired_normalized:
                return text
            
            # Skip if length changed too much (suspicious)
            len_ratio = len(repaired) / max(len(text), 1)
            if len_ratio < 0.5 or len_ratio > 1.5:
                logger.info(f"🔧 [STT_REPAIR] SKIPPED before='{text}' after='{repaired}' ratio={len_ratio:.2f} reason=suspicious_length_change")
                return text
            
            # 🔥 REQUIREMENT: Mandatory logging for every repair
            # Determine repair reason based on what changed
            if any(term in repaired for term in vocab_items):
                reason = "vocabulary_match"
            else:
                reason = "general_repair"
            
            logger.info(f"🔧 [STT_REPAIR] before='{text}' after='{repaired}' reason={reason} business_id={business_id}")
            return repaired
        
        return text
        
    except Exception as e:
        logger.warning(f"⚠️ [SEMANTIC_REPAIR] Failed: {e}")
        return text


def should_apply_semantic_repair(text: str) -> bool:
    """
    🔥 BUILD 301: Enhanced criteria for semantic repair
    
    Criteria:
    - Text <= 12 characters
    - OR 1-2 tokens only (single word / short phrase)
    - OR low Hebrew character ratio (suggests garbled text)
    """
    import re
    
    if not text:
        return False
    
    text = text.strip()
    
    # Short text always benefits from repair
    if len(text) <= 12:
        return True
    
    # 🔥 BUILD 301: 1-2 tokens = apply repair (per Watchdog doc)
    tokens = text.split()
    if len(tokens) <= 2:
        return True
    
    # Check Hebrew ratio - low ratio suggests garbled text
    hebrew_chars = len(re.findall(r'[\u0590-\u05FF]', text))
    total_chars = len(re.sub(r'\s', '', text))
    
    if total_chars > 0:
        hebrew_ratio = hebrew_chars / total_chars
        # If less than 50% Hebrew in what should be Hebrew text, repair it
        if hebrew_ratio < 0.5 and total_chars > 3:
            return True
    
    return False
