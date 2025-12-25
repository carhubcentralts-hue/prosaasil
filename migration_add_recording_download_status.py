"""
Migration: Add recording download status tracking columns to CallLog

This migration adds columns to track recording download status to prevent
duplicate download jobs and excessive API calls.

New columns:
- recording_download_status: Track download state (missing|queued|downloading|ready|failed)
- recording_last_enqueue_at: Last time download was enqueued
- recording_fail_count: Number of failed download attempts
- recording_next_retry_at: When to retry after failure
"""
from server.app_factory import get_process_app
from server.db import db
from sqlalchemy import text
import logging

log = logging.getLogger(__name__)

def run_migration():
    """Add recording download status tracking columns"""
    app = get_process_app()
    with app.app_context():
        try:
            # Check if columns already exist
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'call_log' 
                AND column_name IN ('recording_download_status', 'recording_last_enqueue_at', 'recording_fail_count', 'recording_next_retry_at')
            """)
            result = db.session.execute(check_query)
            existing_columns = [row[0] for row in result]
            
            if len(existing_columns) == 4:
                log.info("✅ Recording download status columns already exist - skipping migration")
                return
            
            log.info("🔄 Adding recording download status tracking columns to call_log table...")
            
            # Add columns one by one to handle existing data
            if 'recording_download_status' not in existing_columns:
                db.session.execute(text("""
                    ALTER TABLE call_log 
                    ADD COLUMN recording_download_status VARCHAR(32) DEFAULT NULL
                """))
                log.info("✅ Added recording_download_status column")
            
            if 'recording_last_enqueue_at' not in existing_columns:
                db.session.execute(text("""
                    ALTER TABLE call_log 
                    ADD COLUMN recording_last_enqueue_at TIMESTAMP DEFAULT NULL
                """))
                log.info("✅ Added recording_last_enqueue_at column")
            
            if 'recording_fail_count' not in existing_columns:
                db.session.execute(text("""
                    ALTER TABLE call_log 
                    ADD COLUMN recording_fail_count INTEGER DEFAULT 0
                """))
                log.info("✅ Added recording_fail_count column")
            
            if 'recording_next_retry_at' not in existing_columns:
                db.session.execute(text("""
                    ALTER TABLE call_log 
                    ADD COLUMN recording_next_retry_at TIMESTAMP DEFAULT NULL
                """))
                log.info("✅ Added recording_next_retry_at column")
            
            # Initialize status for existing recordings
            # Set status to 'ready' for calls that have recording_url and local file exists
            # Set status to 'missing' for calls that have recording_url but no local file
            log.info("🔄 Initializing recording_download_status for existing calls...")
            
            # Import here to avoid circular dependencies
            from server.services.recording_service import check_local_recording_exists
            from server.models_sql import CallLog
            
            # Get all calls with recording_url
            calls_with_recording = CallLog.query.filter(
                CallLog.recording_url.isnot(None),
                CallLog.recording_download_status.is_(None)
            ).all()
            
            ready_count = 0
            missing_count = 0
            
            for call in calls_with_recording:
                if check_local_recording_exists(call.call_sid):
                    call.recording_download_status = 'ready'
                    ready_count += 1
                else:
                    call.recording_download_status = 'missing'
                    missing_count += 1
            
            db.session.commit()
            
            log.info(f"✅ Migration completed successfully!")
            log.info(f"   - {ready_count} recordings marked as 'ready' (local file exists)")
            log.info(f"   - {missing_count} recordings marked as 'missing' (needs download)")
            
        except Exception as e:
            log.error(f"❌ Migration failed: {e}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_migration()
    print("✅ Migration completed - recording download status columns added")
