"""
Lead Extraction Service - Extract service type and city from Hebrew transcripts
Post-call pipeline: Uses full recording transcript to extract structured lead data
"""
import os
import logging
import json
from typing import Dict, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

# 🔥 REMOVED: Business vocabulary hardcoding removed - let Whisper work naturally!
# Hardcoded vocabulary can cause incorrect word substitutions and confuse the model.
# Better to let the model transcribe accurately without biasing it toward specific terms.

# Service canonicalization mapping - normalize specific services to canonical categories
# Maps specific service mentions to their canonical business category
SERVICE_CANONICALIZATION_MAP = {
    # Locksmith services - all map to "מנעולן"
    "פריצת מנעול": "מנעולן",
    "פריצת דלת": "מנעולן",
    "החלפת צילינדר": "מנעולן",
    "תיקון מנעול": "מנעולן",
    "תיקון מנעול חכם": "מנעולן",
    "פורץ מנעולים": "מנעולן",
    "שכפול מפתח": "מנעולן",
    "התקנת מנעול": "מנעולן",
    # Electrician services - all map to "חשמלאי"
    "תיקון חשמל": "חשמלאי",
    "התקנת גוף תאורה": "חשמלאי",
    "תיקון לוח חשמל": "חשמלאי",
    "תיקון מזגן": "חשמלאי",
    # Plumber services - all map to "שרברב"
    "תיקון צינור": "שרברב",
    "פתיחת סתימה": "שרברב",
    "תיקון ברז": "שרברב",
    "אינסטלטור": "שרברב",
    # Cleaning services - all map to "נקיון"
    "ניקיון דירה": "נקיון",
    "ניקיון משרדים": "נקיון",
    "ניקיון כללי": "נקיון",
}

def get_all_canonical_services() -> set:
    """
    Get set of all canonical service types.
    Used to check if a service_type is already in canonical form.
    """
    return set(SERVICE_CANONICALIZATION_MAP.values())

def is_canonical_service(service_type: Optional[str]) -> bool:
    """
    Check if service_type is already in canonical form.
    
    Returns True if the service is already a canonical value (e.g., "מנעולן", "חשמלאי")
    Returns False if it's a raw/specific service or None
    """
    if not service_type:
        return False
    
    canonical_services = get_all_canonical_services()
    return service_type.strip() in canonical_services

def canonicalize_service(service_category: Optional[str], business_id: Optional[int] = None) -> Optional[str]:
    """
    Normalize specific service mentions to canonical business categories.
    
    For example:
    - "פריצת מנעול" → "מנעולן"
    - "פריצת דלת" → "מנעולן"
    - "החלפת צילינדר" → "מנעולן"
    - "תיקון חשמל" → "חשמלאי"
    
    This ensures consistent service_type values in the database and prevents
    raw LLM extractions from creating fragmented service categories.
    
    Args:
        service_category: Raw service category from LLM extraction
        business_id: Optional business ID for future business-specific mappings
        
    Returns:
        Canonical service category, or original if no mapping found
    """
    if not service_category:
        return None
    
    # Normalize input: lowercase and strip whitespace
    normalized_input = service_category.strip().lower()
    
    # Check exact match in canonicalization map (case-insensitive)
    for raw_service, canonical_service in SERVICE_CANONICALIZATION_MAP.items():
        if normalized_input == raw_service.lower():
            logger.info(f"[SERVICE_CANON] raw='{service_category}' -> canon='{canonical_service}' (exact match)")
            print(f"[SERVICE_CANON] ✅ raw='{service_category}' -> canon='{canonical_service}' (exact match)")
            return canonical_service
    
    # Check if input contains any of the raw service patterns
    for raw_service, canonical_service in SERVICE_CANONICALIZATION_MAP.items():
        if raw_service.lower() in normalized_input:
            logger.info(f"[SERVICE_CANON] raw='{service_category}' -> canon='{canonical_service}' (partial match: '{raw_service}')")
            print(f"[SERVICE_CANON] ✅ raw='{service_category}' -> canon='{canonical_service}' (partial match: '{raw_service}')")
            return canonical_service
    
    # No mapping found - return original value
    # This allows new service types to be stored as-is until explicitly mapped
    logger.info(f"[SERVICE_CANON] raw='{service_category}' -> no mapping found, keeping original")
    print(f"[SERVICE_CANON] ℹ️ raw='{service_category}' -> no mapping, keeping original")
    return service_category

def extract_city_and_service_from_summary(summary_text: str) -> dict:
    """
    חילוץ עיר ותחום שירות מטקסט שיחה (סיכום או תמלול).
    
    קלט: טקסט שיחה - summary (מועדף) או transcript מלא (fallback)
    פלט: dict עם city, raw_city, service_category, confidence
    
    🔥 SMART FALLBACK: הפונקציה יכולה לעבוד עם:
    - סיכום GPT (אידיאלי - מרוכז ומדויק)
    - תמלול Whisper מלא (fallback - אם אין סיכום)
    - תמלול realtime (fallback אחרון)
    
    זו הפונקציה העיקרית לחילוץ בסוף שיחה.
    """
    if not summary_text or len(summary_text) < 20:
        logger.warning(f"[OFFLINE_EXTRACT] Text too short for extraction: {len(summary_text or '')} chars")
        return {
            "city": None,
            "raw_city": None,
            "service_category": None,
            "confidence": None,
        }
    
    try:
        logger.info(f"[OFFLINE_EXTRACT] Starting extraction from summary, length: {len(summary_text)} chars")
        
        # Get OpenAI client - reuse existing infrastructure
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Build prompt - focused on summary extraction
        system_prompt = """Extract data from Hebrew call summaries.

Extract two items:
1. CITY: Where service is needed (Hebrew)
2. SERVICE TYPE: Type of service needed (Hebrew)

Rules:
- Use only information in summary
- Do not invent or guess
- If not mentioned: return null
- Return JSON only
- If uncertain, leave empty
- Return canonical name (city) and raw input (raw_city)
- For service, extract specific service mentioned

Output JSON:
{
  "city": "<Hebrew city name or empty>",
  "raw_city": "<Raw city from customer or empty>",
  "service_category": "<Hebrew service type or empty>",
  "confidence": <float 0.0-1.0>
}

Confidence:
- 0.9-1.0: Both city and service explicit
- 0.7-0.9: Both found, one inferred
- 0.5-0.7: Only one clear
- 0.0-0.5: Weak evidence

Examples:
- "Customer needs locksmith in Tel Aviv" → {"city": "Tel Aviv", "raw_city": "Tel Aviv", "service_category": "locksmith", "confidence": 0.95}
"""
        
        user_prompt = f"""Extract city and service from call summary (Hebrew):

\"\"\"{summary_text}\"\"\"

Return JSON with four fields: city, raw_city, service_category, confidence.
"""
        
        # Call OpenAI
        logger.info(f"[OFFLINE_EXTRACT] Calling OpenAI for summary extraction...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cost-effective
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,  # Deterministic
            max_tokens=150,
            timeout=10.0
        )
        
        # Parse response
        raw_response = response.choices[0].message.content.strip()
        logger.info(f"[OFFLINE_EXTRACT] Raw OpenAI response: {raw_response[:200]}")
        
        # Extract JSON from response (handle markdown code blocks)
        json_text = raw_response
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()
        
        # Parse JSON
        try:
            result = json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(f"[OFFLINE_EXTRACT] JSON parse failed: {e}")
            logger.error(f"[OFFLINE_EXTRACT] Raw text: {json_text}")
            return {
                "city": None,
                "raw_city": None,
                "service_category": None,
                "confidence": None,
            }
        
        # Validate and extract fields
        city = result.get("city", "").strip()
        raw_city = result.get("raw_city", "").strip()
        service_category = result.get("service_category", "").strip()
        confidence = float(result.get("confidence", 0.0))
        
        # Normalize empty strings to None
        city = city if city else None
        raw_city = raw_city if raw_city else None
        service_category = service_category if service_category else None
        
        # Log results
        if city or service_category:
            logger.info(f"[OFFLINE_EXTRACT] Success from summary: city='{city}', service='{service_category}', confidence={confidence:.2f}")
        else:
            logger.info(f"[OFFLINE_EXTRACT] No reliable data found in summary")
        
        return {
            "city": city,
            "raw_city": raw_city,
            "service_category": service_category,
            "confidence": confidence
        }
        
    except Exception as e:
        logger.error(f"[OFFLINE_EXTRACT] Summary extraction failed: {type(e).__name__}: {str(e)[:200]}")
        import traceback
        traceback.print_exc()
        return {
            "city": None,
            "raw_city": None,
            "service_category": None,
            "confidence": None,
        }


def extract_lead_from_transcript(transcript: str, business_prompt: Optional[str] = None, business_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Extract service type and city from a full Hebrew call transcript using AI.
    
    This is a POST-CALL extraction - runs after the call ends, using the full
    high-quality Whisper transcript. Does NOT affect realtime call flow.
    
    Args:
        transcript: Full Hebrew transcript of the call
        business_prompt: Optional business-specific prompt for context
        business_id: Optional business ID for logging
        
    Returns:
        dict with keys: service, city, confidence
        Returns empty dict {} if extraction fails or no reliable data found
        
    Example:
        {
            "service": "פורץ מנעולים",
            "city": "ראשון לציון",
            "confidence": 0.92
        }
    """
    if not transcript or len(transcript.strip()) < 10:
        logger.warning(f"[OFFLINE_EXTRACT] Transcript too short for extraction: {len(transcript)} chars")
        return {}
    
    try:
        logger.info(f"[OFFLINE_EXTRACT] Starting extraction for business {business_id}, transcript length: {len(transcript)} chars")
        
        # Get OpenAI client
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Build system prompt - Hebrew-focused with business context
        system_prompt = """You are an extraction engine for Hebrew phone call transcripts.

GOAL:
Extract exactly TWO pieces of information from the call transcript, if and only if they are clearly mentioned:
  1) SERVICE TYPE: The type of service the customer needs (in Hebrew)
  2) CITY: The city where the service is needed (in Hebrew)

STRICT RULES:
- Use ONLY information explicitly mentioned or clearly implied in the transcript
- Do NOT invent or guess a city or service that is not clearly supported by the transcript
- If the customer mentions an area or landmark (e.g., "אזור קניון הזהב"), map it to the correct city
- If you are uncertain about either field, leave it empty (empty string)
- Respond in JSON
- Look for direct statements

Output JSON:
{
  "service": "<Hebrew service name or empty>",
  "city": "<Hebrew city name or empty>",
  "confidence": <float 0.0-1.0>
}

Confidence:
- 0.9-1.0: Both explicit with clear context
- 0.7-0.9: Both found, one inferred
- 0.5-0.7: One clear, other inferred or missing
- 0.0-0.5: Weak or no evidence

Good extractions:
- "I need locksmith in Rishon LeZion" → {"service": "locksmith", "city": "Rishon LeZion", "confidence": 0.95}
- "Problem with lock, live in Tel Aviv" → {"service": "lock repair", "city": "Tel Aviv", "confidence": 0.85}

Weak extractions (low confidence or empty):
- "Yes, need help" → {"service": "", "city": "", "confidence": 0.0}
- "Thanks, bye" → {"service": "", "city": "", "confidence": 0.0}
"""
        
        # Add business context if provided
        if business_prompt and len(business_prompt) > 50:
            # Extract relevant parts of business prompt (first 500 chars)
            business_context = business_prompt[:500]
            system_prompt += f"\n\nBusiness context:\n{business_context}\n"
            logger.info(f"[OFFLINE_EXTRACT] Added business context: {len(business_context)} chars")
        
        # Build user prompt with transcript
        user_prompt = f"""Full call transcript (Hebrew):

\"\"\"{transcript}\"\"\"

Extract service and city.
Return JSON with three fields: service, city, confidence.
"""
        
        # Call OpenAI with timeout
        logger.info(f"[OFFLINE_EXTRACT] Calling OpenAI for extraction...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cost-effective for extraction
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,  # Deterministic extraction
            max_tokens=150,  # Short response expected
            timeout=10.0  # 10s timeout for post-call processing
        )
        
        # Parse response
        raw_response = response.choices[0].message.content.strip()
        logger.info(f"[OFFLINE_EXTRACT] Raw OpenAI response: {raw_response[:200]}")
        
        # Extract JSON from response (handle markdown code blocks)
        json_text = raw_response
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()
        
        # Parse JSON
        try:
            result = json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(f"[OFFLINE_EXTRACT] JSON parse failed: {e}")
            logger.error(f"[OFFLINE_EXTRACT] Raw text: {json_text}")
            return {}
        
        # Validate structure
        if not isinstance(result, dict):
            logger.error(f"[OFFLINE_EXTRACT] Response is not a dict: {type(result)}")
            return {}
        
        # Extract and normalize fields
        service = result.get("service", "").strip()
        city = result.get("city", "").strip()
        confidence = float(result.get("confidence", 0.0))
        
        # Normalize empty values to None for DB consistency
        if not service:
            service = None
        if not city:
            city = None
        
        # Log results
        if service or city:
            logger.info(f"[OFFLINE_EXTRACT] Success: service='{service}', city='{city}', confidence={confidence:.2f}")
        else:
            logger.info(f"[OFFLINE_EXTRACT] No reliable data found in transcript")
        
        return {
            "service": service,
            "city": city,
            "confidence": confidence
        }
        
    except Exception as e:
        logger.error(f"[OFFLINE_EXTRACT] Extraction failed: {type(e).__name__}: {str(e)[:200]}")
        import traceback
        traceback.print_exc()
        return {}


def transcribe_recording_with_whisper(audio_file_path: str, call_sid: str) -> Optional[str]:
    """
    תמלול הקלטה מלאה בעברית - איכות מקסימלית עם GPT-4o Transcribe.
    
    This is the OFFLINE transcription (post-call) - different from realtime STT.
    Uses GPT-4o-transcribe with optimized settings for maximum Hebrew accuracy.
    Falls back to whisper-1 if GPT-4o-transcribe is not available.
    
    NOTE: Converts audio to optimal format (WAV 16kHz mono) before transcription.
    
    Args:
        audio_file_path: Path to the audio file (MP3/WAV)
        call_sid: Call SID for logging
        
    Returns:
        Full transcript text (Hebrew) or None if failed
    """
    if not audio_file_path or not os.path.exists(audio_file_path):
        logger.error(f"[OFFLINE_STT] Audio file not found: {audio_file_path}")
        return None
    
    # Initialize converted_file early to ensure it's in scope for cleanup
    converted_file = None
    
    try:
        file_size = os.path.getsize(audio_file_path)
        logger.info(f"[OFFLINE_STT] Starting transcription for call {call_sid}")
        logger.info(f"[OFFLINE_STT] File: {audio_file_path}, size: {file_size} bytes")
        print(f"[OFFLINE_STT] 🎧 Using GPT-4o transcribe for {call_sid}, size={file_size} bytes")
        
        # Convert audio to optimal format for transcription
        # WAV 16kHz mono PCM is the best format for STT quality
        file_to_transcribe = audio_file_path
        
        try:
            import subprocess
            import tempfile
            
            # Check if ffmpeg is available
            try:
                subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True, timeout=5)
                ffmpeg_available = True
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                ffmpeg_available = False
                logger.warning("[OFFLINE_STT] ffmpeg not available, using original audio file")
            
            if ffmpeg_available:
                # Create temporary file for converted audio
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                    converted_file = tmp_file.name
                
                # Convert to WAV 16kHz mono PCM using ffmpeg
                # -ac 1: mono (single channel)
                # -ar 16000: 16kHz sample rate (optimal for speech recognition)
                # -c:a pcm_s16le: PCM 16-bit little-endian (uncompressed, best quality)
                # -y: overwrite output file
                conversion_cmd = [
                    'ffmpeg',
                    '-i', audio_file_path,
                    '-ac', '1',              # mono
                    '-ar', '16000',          # 16kHz
                    '-c:a', 'pcm_s16le',     # PCM 16-bit
                    '-y',                    # overwrite
                    converted_file
                ]
                
                logger.info(f"[OFFLINE_STT] Converting audio to WAV 16kHz mono for {call_sid}")
                result = subprocess.run(
                    conversion_cmd,
                    capture_output=True,
                    timeout=60,  # 60 seconds max for conversion
                    text=True
                )
                
                if result.returncode == 0:
                    converted_size = os.path.getsize(converted_file)
                    logger.info(f"[OFFLINE_STT] ✅ Audio converted: {file_size} → {converted_size} bytes (WAV 16kHz mono)")
                    print(f"[OFFLINE_STT] ✅ Audio converted to optimal format (WAV 16kHz mono)")
                    file_to_transcribe = converted_file
                else:
                    logger.warning(f"[OFFLINE_STT] Audio conversion failed: {result.stderr}")
                    print(f"⚠️ [OFFLINE_STT] Audio conversion failed, using original file")
                    # Clean up failed conversion file
                    if os.path.exists(converted_file):
                        os.unlink(converted_file)
                    converted_file = None
        except Exception as conv_error:
            logger.warning(f"[OFFLINE_STT] Audio conversion error: {conv_error}")
            print(f"⚠️ [OFFLINE_STT] Audio conversion error, using original file: {conv_error}")
            if converted_file and os.path.exists(converted_file):
                try:
                    os.unlink(converted_file)
                except:
                    pass
            converted_file = None
        
        # Get OpenAI client
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Try GPT-4o-transcribe first (highest quality), fallback to whisper-1
        models_to_try = [
            ("gpt-4o-transcribe", "GPT-4o transcribe (highest quality)"),
            ("whisper-1", "Whisper-1 (fallback)")
        ]
        
        transcript_text = None
        last_error = None
        
        for model, model_desc in models_to_try:
            try:
                logger.info(f"[OFFLINE_STT] Trying model: {model}")
                print(f"[OFFLINE_STT] Attempting transcription with {model_desc}")
                
                # 🔥 CLEAN & SIMPLE: Natural Hebrew prompt without hardcoded vocabulary
                # Let Whisper transcribe accurately without biasing toward specific terms
                clean_hebrew_prompt = (
                    "זוהי שיחת טלפון בעברית ישראלית. "
                    "תמלל בדיוק מילה במילה כפי שנאמר, בעברית תקנית עם פיסוק מדויק. "
                    "אל תשנה, תתקן או תמציא מילים - תמלל בדיוק מה שנשמע."
                )
                
                # 🔥 MODEL-SPECIFIC FORMAT: Different models support different response formats
                # gpt-4o-transcribe: supports "json" or "text" (NOT verbose_json)
                # whisper-1: supports "verbose_json" for enhanced quality with timestamps
                
                try:
                    if model == "gpt-4o-transcribe":
                        # gpt-4o-transcribe uses "json" format (not verbose_json)
                        logger.info(f"[OFFLINE_STT] Using 'json' format for {model}")
                        with open(file_to_transcribe, 'rb') as audio_file:
                            transcript_response = client.audio.transcriptions.create(
                                model=model,
                                file=audio_file,
                                language="he",
                                temperature=0,
                                response_format="json",
                                prompt=clean_hebrew_prompt
                            )
                    else:
                        # whisper-1 supports verbose_json with enhanced quality
                        # Try with segment-level timestamps for maximum accuracy
                        try:
                            with open(file_to_transcribe, 'rb') as audio_file:
                                transcript_response = client.audio.transcriptions.create(
                                    model=model,
                                    file=audio_file,
                                    language="he",
                                    temperature=0,
                                    response_format="verbose_json",
                                    prompt=clean_hebrew_prompt,
                                    timestamp_granularities=["segment"]
                                )
                            logger.info(f"[OFFLINE_STT] Using timestamp_granularities for enhanced accuracy")
                        except Exception:
                            # Fallback: timestamp_granularities not supported, use basic verbose_json
                            logger.info(f"[OFFLINE_STT] timestamp_granularities not supported, using basic verbose_json")
                            with open(file_to_transcribe, 'rb') as audio_file:
                                transcript_response = client.audio.transcriptions.create(
                                    model=model,
                                    file=audio_file,
                                    language="he",
                                    temperature=0,
                                    response_format="verbose_json",
                                    prompt=clean_hebrew_prompt
                                )
                except Exception as file_error:
                    logger.error(f"[OFFLINE_STT] File handling error: {file_error}")
                    raise
                
                # Extract text from verbose_json response
                if isinstance(transcript_response, str):
                    transcript_text = transcript_response.strip()
                elif hasattr(transcript_response, 'text'):
                    transcript_text = transcript_response.text.strip()
                elif hasattr(transcript_response, 'segments'):
                    # Build transcript from segments for maximum accuracy
                    segments = transcript_response.segments
                    transcript_text = " ".join(seg.get('text', '').strip() for seg in segments).strip()
                    logger.info(f"[OFFLINE_STT] Reconstructed from {len(segments)} segments")
                else:
                    transcript_text = str(transcript_response).strip()
                
                # Success with this model!
                logger.info(f"[OFFLINE_STT] ✅ Success with {model}: {len(transcript_text)} chars")
                print(f"[OFFLINE_STT] ✅ Transcript obtained with {model} ({len(transcript_text)} chars) for {call_sid}")
                print(f"[OFFLINE_STT] Preview: {transcript_text[:120]!r}")
                break
                
            except Exception as model_error:
                last_error = model_error
                error_msg = str(model_error).lower()
                
                # Check if model not found - try fallback
                if "model" in error_msg and ("not found" in error_msg or "does not exist" in error_msg):
                    logger.warning(f"[OFFLINE_STT] Model {model} not available, trying fallback...")
                    print(f"⚠️ [OFFLINE_STT] {model} not available, trying fallback...")
                    continue
                else:
                    # Other error - log but try fallback anyway
                    logger.warning(f"[OFFLINE_STT] Error with {model}: {model_error}")
                    print(f"⚠️ [OFFLINE_STT] Error with {model}, trying fallback...")
                    continue
        
        # Check if we got a valid transcript
        if not transcript_text or len(transcript_text) < 10:
            logger.warning(f"[OFFLINE_STT] Transcription too short or empty: {len(transcript_text or '')} chars")
            print(f"⚠️ [OFFLINE_STT] Transcription too short or empty: {len(transcript_text or '')} chars")
            # Clean up converted file if exists
            if converted_file and os.path.exists(converted_file):
                try:
                    os.unlink(converted_file)
                except:
                    pass
            return None
        
        logger.info(f"[OFFLINE_STT] Transcription complete: {len(transcript_text)} chars")
        logger.info(f"[OFFLINE_STT] Transcript preview: {transcript_text[:150]!r}")
        
        # 🔥 BUILD 342: Clean up converted file after successful transcription
        if converted_file and os.path.exists(converted_file):
            try:
                os.unlink(converted_file)
                logger.info(f"[OFFLINE_STT] Cleaned up converted audio file")
            except Exception as cleanup_error:
                logger.warning(f"[OFFLINE_STT] Failed to cleanup converted file: {cleanup_error}")
        
        return transcript_text
        
    except Exception as e:
        logger.error(f"[OFFLINE_STT] Transcription failed for call {call_sid}: {type(e).__name__}: {str(e)[:200]}")
        print(f"❌ [OFFLINE_STT] Transcription failed for {call_sid}: {e}")
        import traceback
        traceback.print_exc()
        # Clean up converted file if exists (converted_file initialized at function start)
        if converted_file and os.path.exists(converted_file):
            try:
                os.unlink(converted_file)
            except:
                pass
        return None
