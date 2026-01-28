"""
WhatsApp Sessions Cleanup Job

This job processes stale WhatsApp sessions and generates summaries.
Replaces the session processor thread with proper RQ job scheduling.
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def whatsapp_sessions_cleanup_job():
    """
    Process stale WhatsApp sessions (inactive for 30+ minutes)
    
    This job should be scheduled to run every 5 minutes by the scheduler service.
    Generates AI summaries for sessions and marks them as processed.
    
    This job is idempotent - sessions are marked as processed and won't be re-processed.
    """
    logger.info("📱 [WA_SESSIONS_CLEANUP] Starting session processing")
    
    try:
        from flask import current_app
        from server.db import db
        from server.models_sql import WhatsAppSession, Lead
        from server.services.ai_service import get_ai_service
        from sqlalchemy import inspect
        
        with current_app.app_context():
            # Check if table exists
            inspector = inspect(db.engine)
            if 'whatsapp_session' not in inspector.get_table_names():
                logger.info("⚠️ [WA_SESSIONS_CLEANUP] Table does not exist yet, skipping")
                return {'status': 'skipped', 'reason': 'table_not_exists'}
            
            # Find stale sessions (last activity > 30 minutes ago, not yet summarized)
            cutoff_time = datetime.utcnow() - timedelta(minutes=30)
            
            stale_sessions = WhatsAppSession.query.filter(
                WhatsAppSession.last_activity_at < cutoff_time,
                WhatsAppSession.summary == None,  # Not yet summarized
                WhatsAppSession.message_count > 0  # Has messages
            ).limit(50).all()  # Process in batches to avoid long-running jobs
            
            if not stale_sessions:
                logger.info("✅ [WA_SESSIONS_CLEANUP] No stale sessions to process")
                return {'status': 'success', 'processed': 0}
            
            logger.info(f"📱 [WA_SESSIONS_CLEANUP] Found {len(stale_sessions)} stale sessions")
            
            ai_service = get_ai_service()
            processed = 0
            
            for session in stale_sessions:
                try:
                    # Get lead for context
                    lead = Lead.query.filter_by(
                        business_id=session.business_id,
                        phone_e164=session.customer_wa_id
                    ).first()
                    
                    if not lead or not lead.notes:
                        logger.info(f"⚠️ No lead or notes for session {session.id}")
                        session.summary = "No conversation data available"
                        processed += 1
                        continue
                    
                    # Extract conversation from notes
                    conversation_lines = []
                    for line in lead.notes.split('\n')[-20:]:  # Last 20 messages
                        if line.strip():
                            conversation_lines.append(line.strip())
                    
                    conversation_text = '\n'.join(conversation_lines)
                    
                    # Generate summary using AI
                    try:
                        summary = ai_service.generate_conversation_summary(
                            conversation_text=conversation_text,
                            business_id=session.business_id,
                            max_length=500
                        )
                        
                        session.summary = summary or "Unable to generate summary"
                        logger.info(f"✅ Generated summary for session {session.id}")
                    except Exception as ai_error:
                        logger.warning(f"⚠️ AI summary failed for session {session.id}: {ai_error}")
                        session.summary = "Summary generation failed"
                    
                    processed += 1
                    
                except Exception as session_error:
                    logger.error(f"❌ Failed to process session {session.id}: {session_error}")
                    session.summary = "Processing error"
                    continue
            
            # Commit all updates
            db.session.commit()
            
            logger.info(f"✅ [WA_SESSIONS_CLEANUP] Processed {processed} sessions")
            return {'status': 'success', 'processed': processed}
            
    except Exception as e:
        logger.error(f"❌ [WA_SESSIONS_CLEANUP] Failed: {e}")
        import traceback
        traceback.print_exc()
        raise  # Re-raise for RQ to handle retry
