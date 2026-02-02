"""
WhatsApp Sessions Cleanup Job

This job processes stale WhatsApp sessions and generates summaries.
Replaces the session processor thread with proper RQ job scheduling.

🔥 FIX: Uses the CORRECT implementation from whatsapp_session_service.py
which properly queries WhatsAppMessage table instead of the broken
lead.notes approach.
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def whatsapp_sessions_cleanup_job():
    """
    Process stale WhatsApp sessions (inactive for 5+ minutes)

    This job should be scheduled to run every 5 minutes by the scheduler service.
    Generates AI summaries for sessions and marks them as processed.

    This job is idempotent - sessions are marked as processed and won't be re-processed.

    🔥 FIX: Now uses the CORRECT implementation from whatsapp_session_service.py:
    - get_session_messages() queries WhatsAppMessage table (not lead.notes!)
    - generate_session_summary() builds proper conversation text from actual messages
    - close_session() saves summary and updates unified customer memory on Lead
    """
    logger.info("📱 [WA_SESSIONS_CLEANUP] Starting session processing")

    try:
        from flask import current_app
        from server.db import db
        from sqlalchemy import inspect

        # Try to import required models - gracefully handle missing models
        try:
            from server.models_sql import WhatsAppConversation
        except ImportError as import_err:
            logger.info(f"⚠️ [WA_SESSIONS_CLEANUP] Model import failed: {import_err}, skipping")
            return {'status': 'skipped', 'reason': 'model_not_found', 'error': str(import_err)}

        with current_app.app_context():
            # Check if table exists
            inspector = inspect(db.engine)
            if 'whatsapp_conversation' not in inspector.get_table_names():
                logger.info("⚠️ [WA_SESSIONS_CLEANUP] Table does not exist yet, skipping")
                return {'status': 'skipped', 'reason': 'table_not_exists'}

            # 🔥 FIX: Use the CORRECT implementation from whatsapp_session_service
            # This properly:
            # 1. Finds stale sessions via get_stale_sessions()
            # 2. Queries WhatsAppMessage table for actual messages (not lead.notes!)
            # 3. Generates proper AI summary from actual conversation
            # 4. Updates Lead with unified customer memory fields
            from server.services.whatsapp_session_service import process_stale_sessions

            processed = process_stale_sessions()

            logger.info(f"✅ [WA_SESSIONS_CLEANUP] Processed {processed} sessions using correct session service")
            return {'status': 'success', 'processed': processed}

    except Exception as e:
        logger.error(f"❌ [WA_SESSIONS_CLEANUP] Failed: {e}")
        import traceback
        traceback.print_exc()
        raise  # Re-raise for RQ to handle retry
