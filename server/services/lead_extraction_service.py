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

# 🔥 BUILD 342: Business vocabulary for better Hebrew transcription
# Common service types and Israeli cities to improve STT accuracy
HEBREW_BUSINESS_VOCABULARY = {
    "services": [
        "פורץ מנעולים", "חשמלאי", "אינסטלטור", "נקיון", "שרברב",
        "מנעולן", "טכנאי", "תיקון", "התקנה", "שירות", "בדיקה"
    ],
    "cities": [
        "תל אביב", "ירושלים", "חיפה", "באר שבע", "פתח תקווה",
        "ראשון לציון", "אשדוד", "נתניה", "בני ברק", "חולון",
        "רמת גן", "בת ים", "הרצליה", "כפר סבא", "מודיעין",
        "בית שאן", "מצפה רמון", "אילת", "טבריה", "צפת"
    ]
}

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
        system_prompt = """You are a data extraction engine for Hebrew phone call summaries.

GOAL:
Extract exactly TWO pieces of information from the call summary:
  1) CITY: The city where the service is needed (in Hebrew)
  2) SERVICE TYPE: The type of service/professional the customer needs (in Hebrew)

STRICT RULES:
- Use ONLY information explicitly mentioned in the summary
- Do NOT invent or guess city or service
- If uncertain, leave the field empty
- Return both canonical name (city) and raw input (raw_city) if mentioned
- For service, extract the SPECIFIC service mentioned (e.g., "תיקון מנעול חכם", "חשמלאי", "קיצור דלתות")

OUTPUT FORMAT (JSON ONLY):
{
  "city": "<Hebrew city name or empty string>",
  "raw_city": "<Raw city input from customer or empty string>",
  "service_category": "<Hebrew service/professional type or empty string>",
  "confidence": <float between 0.0 and 1.0>
}

CONFIDENCE SCORING:
- 0.9-1.0: Both city and service explicitly mentioned
- 0.7-0.9: Both found but one needs inference
- 0.5-0.7: Only one clearly mentioned
- 0.0-0.5: Weak or no evidence

Examples:
- "לקוח צריך פורץ מנעולים בתל אביב" → {"city": "תל אביב", "raw_city": "תל אביב", "service_category": "פורץ מנעולים", "confidence": 0.95}
- "לקוח מעוניין בתיקון מנעול חכם בעיר בית שאן" → {"city": "בית שאן", "raw_city": "בית שאן", "service_category": "תיקון מנעול חכם", "confidence": 0.95}
"""
        
        user_prompt = f"""Extract city and service from this call summary (in Hebrew):

\"\"\"{summary_text}\"\"\"

Return ONLY valid JSON with the four required fields: city, raw_city, service_category, confidence.
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
- The conversation is in Hebrew, but you will respond in JSON
- Look for direct statements like: "אני צריך..." (service), "אני גר ב..." (city), "באזור..." (city)

OUTPUT FORMAT (JSON ONLY):
{
  "service": "<Hebrew service name or empty string if not found>",
  "city": "<Hebrew city name or empty string if not found>",
  "confidence": <float between 0.0 and 1.0 representing confidence in BOTH values together>
}

CONFIDENCE SCORING:
- 0.9-1.0: Both service and city explicitly mentioned with clear context
- 0.7-0.9: Both found but one is inferred from context
- 0.5-0.7: One clearly mentioned, other inferred or missing
- 0.0-0.5: Weak or no evidence for either field

Examples of GOOD extractions:
- "אני צריך פורץ מנעולים בראשון לציון" → {"service": "פורץ מנעולים", "city": "ראשון לציון", "confidence": 0.95}
- "יש לי בעיה עם המנעול, אני גר בתל אביב" → {"service": "תיקון מנעולים", "city": "תל אביב", "confidence": 0.85}

Examples of WEAK extractions (return low confidence or empty):
- "כן, אני צריך עזרה" → {"service": "", "city": "", "confidence": 0.0} (too vague)
- "תודה, להתראות" → {"service": "", "city": "", "confidence": 0.0} (no info)
"""
        
        # Add business context if provided
        if business_prompt and len(business_prompt) > 50:
            # Extract relevant parts of business prompt (first 500 chars)
            business_context = business_prompt[:500]
            system_prompt += f"\n\nBUSINESS CONTEXT (for domain understanding):\n{business_context}\n"
            logger.info(f"[OFFLINE_EXTRACT] Added business context: {len(business_context)} chars")
        
        # Build user prompt with transcript
        user_prompt = f"""This is the FULL transcript of the call (in Hebrew):

\"\"\"{transcript}\"\"\"

Extract the service and city according to the rules above.
Return ONLY valid JSON with the three required fields: service, city, confidence.
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
                
                # 🔥 BUILD 342: Enhanced prompt with business vocabulary hints
                # Build prompt dynamically from vocabulary constants
                services_text = ", ".join(HEBREW_BUSINESS_VOCABULARY["services"][:5])  # First 5 services
                cities_text = ", ".join(HEBREW_BUSINESS_VOCABULARY["cities"][:10])     # First 10 cities
                
                business_vocabulary_prompt = (
                    f"תמלל מילה במילה שיחת טלפון בעברית בין לקוח לנציג שירות. "
                    f"תכתוב בעברית תקנית עם פיסוק. "
                    f"השיחה עוסקת בבקשת שירות (למשל: {services_text}) "
                    f"ומיקום (ערים בישראל כמו: {cities_text}). "
                    f"אל תוסיף או תמציא מידע שלא נאמר."
                )
                
                # 🔥 BUILD 342: Use converted file if available (WAV 16kHz mono)
                with open(file_to_transcribe, 'rb') as audio_file:
                    transcript_response = client.audio.transcriptions.create(
                        model=model,
                        file=audio_file,
                        language="he",  # Hebrew
                        temperature=0,  # Most deterministic/accurate
                        response_format="text",  # Plain text output
                        prompt=business_vocabulary_prompt
                    )
                
                # Extract text
                if isinstance(transcript_response, str):
                    transcript_text = transcript_response.strip()
                else:
                    transcript_text = transcript_response.text.strip() if hasattr(transcript_response, 'text') else str(transcript_response).strip()
                
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
