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
    Transcribe a full recording using OpenAI Whisper for high accuracy.
    
    This is the OFFLINE transcription (post-call) - different from realtime STT.
    Uses Whisper with optimized settings for Hebrew accuracy.
    
    Args:
        audio_file_path: Path to the audio file (MP3/WAV)
        call_sid: Call SID for logging
        
    Returns:
        Full transcript text (Hebrew) or None if failed
    """
    if not audio_file_path or not os.path.exists(audio_file_path):
        logger.error(f"[OFFLINE_STT] Audio file not found: {audio_file_path}")
        return None
    
    try:
        logger.info(f"[OFFLINE_STT] Starting transcription for call {call_sid}")
        logger.info(f"[OFFLINE_STT] File: {audio_file_path}, size: {os.path.getsize(audio_file_path)} bytes")
        
        # Get OpenAI client
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Transcribe with Whisper - optimized for accuracy
        with open(audio_file_path, 'rb') as audio_file:
            # Get file size for logging
            file_size = os.path.getsize(audio_file_path)
            logger.info(f"[OFFLINE_STT] Whisper model=whisper-1, file_size={file_size} bytes, language=he")
            print(f"[OFFLINE_STT] Whisper model=whisper-1, file_size={file_size} bytes, language=he")
            
            transcript_response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="he",  # Hebrew
                temperature=0.0,  # Most deterministic/accurate
                response_format="text",  # Plain text output
                prompt="שיחת טלפון בעברית בין לקוח למוקד שירות מנעולן. תמלל בעברית תקינה."  # Context hint for better accuracy
            )
        
        # Extract text
        if isinstance(transcript_response, str):
            transcript_text = transcript_response.strip()
        else:
            transcript_text = transcript_response.text.strip() if hasattr(transcript_response, 'text') else str(transcript_response).strip()
        
        # Log detailed preview
        logger.info(f"[OFFLINE_STT] Transcription complete: {len(transcript_text)} chars")
        print(f"[OFFLINE_STT] ✅ Transcript obtained: {len(transcript_text)} chars")
        print(f"[OFFLINE_STT] Transcript preview (first 150 chars): {transcript_text[:150]!r}")
        logger.info(f"[OFFLINE_STT] Transcript preview: {transcript_text[:150]!r}")
        
        # Validate
        if not transcript_text or len(transcript_text) < 10:
            logger.warning(f"[OFFLINE_STT] Transcription too short or empty: {len(transcript_text)} chars")
            print(f"⚠️ [OFFLINE_STT] Transcription too short or empty: {len(transcript_text)} chars")
            return None
        
        return transcript_text
        
    except Exception as e:
        logger.error(f"[OFFLINE_STT] Transcription failed for call {call_sid}: {type(e).__name__}: {str(e)[:200]}")
        import traceback
        traceback.print_exc()
        return None
