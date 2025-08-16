"""
Database migrations - additive only, no DROP operations
"""
from server.db import db
from datetime import datetime
import logging

log = logging.getLogger(__name__)

def check_column_exists(table_name, column_name):
    """Check if column exists in table"""
    from sqlalchemy import text
    result = db.session.execute(text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = :table_name AND column_name = :column_name
    """), {"table_name": table_name, "column_name": column_name})
    return result.fetchone() is not None

def check_table_exists(table_name):
    """Check if table exists"""
    from sqlalchemy import text
    result = db.session.execute(text("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_name = :table_name
    """), {"table_name": table_name})
    return result.fetchone() is not None

def apply_migrations():
    """Apply all pending migrations"""
    migrations_applied = []
    
    # Migration 1: Add transcript column to CallLog
    if check_table_exists('call_log') and not check_column_exists('call_log', 'transcript'):
        from sqlalchemy import text
        db.session.execute(text("ALTER TABLE call_log ADD COLUMN transcript TEXT"))
        migrations_applied.append("add_call_log_transcript")
        log.info("Applied migration: add_call_log_transcript")
    
    # Migration 2: Create CallTurn table
    if not check_table_exists('call_turn'):
        from sqlalchemy import text
        db.session.execute(text("""
            CREATE TABLE call_turn (
                id SERIAL PRIMARY KEY,
                call_sid VARCHAR(64) NOT NULL,
                business_id INTEGER NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                mode VARCHAR(10) DEFAULT 'stream',
                t_audio_ms INTEGER,
                t_nlp_ms INTEGER,
                t_tts_ms INTEGER,
                t_total_ms INTEGER,
                error_code VARCHAR(50)
            )
        """))
        db.session.execute(text("CREATE INDEX idx_call_turn_sid ON call_turn(call_sid)"))
        db.session.execute(text("CREATE INDEX idx_call_turn_business_time ON call_turn(business_id, started_at)"))
        migrations_applied.append("create_call_turn_table")
        log.info("Applied migration: create_call_turn_table")
    
    # Migration 3: Add feature flags to Business table
    feature_flags = [
        'enable_calls_stream',
        'enable_recording_fallback', 
        'enable_payments_paypal',
        'enable_payments_tranzila'
    ]
    
    for flag in feature_flags:
        if check_table_exists('business') and not check_column_exists('business', flag):
            from sqlalchemy import text
            default_value = 'true' if flag.startswith('enable_calls') or flag.startswith('enable_recording') else 'false'
            db.session.execute(text(f"ALTER TABLE business ADD COLUMN {flag} BOOLEAN DEFAULT {default_value}"))
            migrations_applied.append(f"add_business_{flag}")
            log.info(f"Applied migration: add_business_{flag}")
    
    if migrations_applied:
        db.session.commit()
        log.info(f"Applied {len(migrations_applied)} migrations: {', '.join(migrations_applied)}")
    else:
        log.info("No migrations needed - database is up to date")
    
    return migrations_applied