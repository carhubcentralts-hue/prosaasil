"""
Call Summarization Job for RQ Worker

This job processes call transcripts and generates summaries for long calls.
Runs after transcription is complete and handles chunking for very long transcripts.
"""
import logging
import os
import openai
from datetime import datetime
from server.app_factory import get_process_app
from server.db import db

logger = logging.getLogger(__name__)

# Configuration constants
MIN_TRANSCRIPT_LENGTH = 100  # Minimum transcript length to attempt summarization
CHUNK_SIZE = 2500  # Characters per chunk for long transcripts
MAX_CHUNK_SIZE = 3000  # Maximum characters per chunk


def chunk_transcript(transcript: str, chunk_size: int = CHUNK_SIZE, max_chunk_size: int = MAX_CHUNK_SIZE) -> list[str]:
    """
    Split a long transcript into chunks for processing.
    
    Args:
        transcript: Full transcript text
        chunk_size: Target size for each chunk
        max_chunk_size: Maximum size before forcing a split
        
    Returns:
        List of transcript chunks
    """
    if len(transcript) <= max_chunk_size:
        return [transcript]
    
    chunks = []
    current_pos = 0
    
    while current_pos < len(transcript):
        # Find the next chunk boundary
        end_pos = min(current_pos + chunk_size, len(transcript))
        
        # If not at the end, try to break at a sentence boundary
        if end_pos < len(transcript):
            # Look for sentence endings (period, question mark, exclamation)
            for i in range(end_pos, max(current_pos, end_pos - 500), -1):
                if transcript[i] in '.?!\n':
                    end_pos = i + 1
                    break
        
        chunks.append(transcript[current_pos:end_pos].strip())
        current_pos = end_pos
    
    return chunks


def summarize_transcript_chunk(chunk: str, chunk_index: int, total_chunks: int) -> str:
    """
    Summarize a single chunk of transcript using OpenAI.
    
    Args:
        chunk: Transcript chunk to summarize
        chunk_index: Index of this chunk (0-based)
        total_chunks: Total number of chunks
        
    Returns:
        Summary text for the chunk
    """
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.error("[SUMMARIZE] No OPENAI_API_KEY found")
            return ""
        
        client = openai.OpenAI(api_key=api_key)
        
        # Prepare prompt based on whether this is a single chunk or part of a series
        if total_chunks == 1:
            system_prompt = "אתה עוזר AI המסכם שיחות טלפון בעברית. תן סיכום תמציתי וברור."
            user_prompt = f"סכם את השיחה הבאה בצורה תמציתית (80-150 מילים):\n\n{chunk}"
        else:
            system_prompt = "אתה עוזר AI המסכם שיחות טלפון בעברית. אתה מסכם חלק משיחה ארוכה יותר."
            user_prompt = f"זהו חלק {chunk_index + 1} מתוך {total_chunks} של שיחה ארוכה. סכם חלק זה בצורה תמציתית:\n\n{chunk}"
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cost-effective model for summaries
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=300
        )
        
        summary = response.choices[0].message.content.strip()
        logger.info(f"[SUMMARIZE] Generated summary for chunk {chunk_index + 1}/{total_chunks} ({len(summary)} chars)")
        return summary
        
    except Exception as e:
        logger.error(f"[SUMMARIZE] Error summarizing chunk {chunk_index + 1}: {e}")
        return ""


def merge_chunk_summaries(chunk_summaries: list[str]) -> str:
    """
    Merge multiple chunk summaries into a cohesive final summary.
    
    Args:
        chunk_summaries: List of summaries from individual chunks
        
    Returns:
        Final merged summary
    """
    if len(chunk_summaries) == 1:
        return chunk_summaries[0]
    
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.error("[SUMMARIZE] No OPENAI_API_KEY found for merging")
            # Fallback: just concatenate with separators
            return "\n\n---\n\n".join(chunk_summaries)
        
        client = openai.OpenAI(api_key=api_key)
        
        # Combine chunk summaries
        combined = "\n\n".join([f"חלק {i+1}:\n{s}" for i, s in enumerate(chunk_summaries)])
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "אתה עוזר AI המסכם שיחות טלפון בעברית. תקבל מספר סיכומים של חלקים משיחה אחת ארוכה."},
                {"role": "user", "content": f"מזג את הסיכומים הבאים לסיכום אחד תמציתי וקוהרנטי של השיחה כולה:\n\n{combined}"}
            ],
            temperature=0.3,
            max_tokens=400
        )
        
        merged_summary = response.choices[0].message.content.strip()
        logger.info(f"[SUMMARIZE] Merged {len(chunk_summaries)} chunk summaries into final summary ({len(merged_summary)} chars)")
        return merged_summary
        
    except Exception as e:
        logger.error(f"[SUMMARIZE] Error merging summaries: {e}")
        # Fallback: just concatenate with separators
        return "\n\n---\n\n".join(chunk_summaries)


def summarize_call(call_sid: str):
    """
    RQ Worker job - Generate summary for a call with completed transcript.
    
    This job:
    1. Waits for transcript to be ready (checks final_transcript or transcription)
    2. Chunks long transcripts (>3000 chars) for processing
    3. Generates summaries using OpenAI
    4. Merges chunk summaries if needed
    5. Updates CallLog with the final summary
    
    Args:
        call_sid: Twilio Call SID to summarize
        
    Returns:
        dict: Job result with success status and summary
    """
    app = get_process_app()
    
    with app.app_context():
        from server.models_sql import CallLog
        
        try:
            # Find the call
            call = CallLog.query.filter_by(call_sid=call_sid).first()
            if not call:
                logger.error(f"[SUMMARIZE] Call not found: {call_sid}")
                return {"success": False, "error": "Call not found"}
            
            # Mark as processing
            call.summary_status = "processing"
            db.session.commit()
            logger.info(f"[SUMMARIZE] Starting summarization for call {call_sid}")
            
            # Get transcript (prefer final_transcript from recording, fallback to realtime transcription)
            transcript = call.final_transcript or call.transcription or ""
            
            # Check if transcript is ready and long enough
            if len(transcript) < MIN_TRANSCRIPT_LENGTH:
                logger.warning(f"[SUMMARIZE] Transcript too short for {call_sid}: {len(transcript)} chars")
                call.summary_status = "failed"
                db.session.commit()
                return {"success": False, "error": "Transcript too short"}
            
            logger.info(f"[SUMMARIZE] Processing transcript for {call_sid} ({len(transcript)} chars)")
            
            # Chunk the transcript if needed
            chunks = chunk_transcript(transcript)
            logger.info(f"[SUMMARIZE] Split into {len(chunks)} chunks")
            
            # Summarize each chunk
            chunk_summaries = []
            for i, chunk in enumerate(chunks):
                summary = summarize_transcript_chunk(chunk, i, len(chunks))
                if summary:
                    chunk_summaries.append(summary)
                else:
                    logger.warning(f"[SUMMARIZE] Failed to summarize chunk {i+1}")
            
            if not chunk_summaries:
                logger.error(f"[SUMMARIZE] No summaries generated for {call_sid}")
                call.summary_status = "failed"
                db.session.commit()
                return {"success": False, "error": "Summarization failed"}
            
            # Merge summaries if multiple chunks
            final_summary = merge_chunk_summaries(chunk_summaries)
            
            # Update call with summary
            call.summary = final_summary
            call.summary_status = "completed"
            db.session.commit()
            
            logger.info(f"[SUMMARIZE] ✅ Summary completed for {call_sid} ({len(final_summary)} chars)")
            
            return {
                "success": True,
                "call_sid": call_sid,
                "summary_length": len(final_summary),
                "chunks_processed": len(chunks)
            }
            
        except Exception as e:
            logger.error(f"[SUMMARIZE] Error processing {call_sid}: {e}", exc_info=True)
            
            # Mark as failed in database
            try:
                call = CallLog.query.filter_by(call_sid=call_sid).first()
                if call:
                    call.summary_status = "failed"
                    db.session.commit()
            except Exception as db_err:
                logger.error(f"[SUMMARIZE] Failed to update status: {db_err}")
            
            return {"success": False, "error": str(e)}


def enqueue_summarize_call(call_sid: str, delay: int = 30):
    """
    Enqueue a call summarization job with optional delay.
    
    This is typically called after transcription is complete.
    The delay allows time for final_transcript to be fully written.
    
    Args:
        call_sid: Twilio Call SID to summarize
        delay: Seconds to delay before processing (default: 30)
        
    Returns:
        RQ Job object or None if enqueue failed
    """
    try:
        from redis import Redis
        from rq import Queue
        from datetime import timedelta
        
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        redis_conn = Redis.from_url(redis_url)
        queue = Queue('default', connection=redis_conn)
        
        # Calculate execution time
        from datetime import datetime, timedelta
        scheduled_time = datetime.utcnow() + timedelta(seconds=delay)
        
        # Schedule the job for future execution
        job = queue.enqueue_at(
            scheduled_time,
            summarize_call,
            call_sid,
            job_timeout='10m',  # 10 minute timeout for long transcripts
            result_ttl=3600,  # Keep result for 1 hour
            failure_ttl=86400,  # Keep failures for 24 hours
            job_id=f"summarize_{call_sid}",  # Prevent duplicate jobs
        )
        
        logger.info(f"[SUMMARIZE] Enqueued summarization for {call_sid} (job_id={job.id}, delay={delay}s)")
        return job
        
    except Exception as e:
        logger.error(f"[SUMMARIZE] Failed to enqueue summarization for {call_sid}: {e}")
        return None
