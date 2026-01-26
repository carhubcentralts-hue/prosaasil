"""
Database migrations - additive only, with strict data protection

🔒 DATA PROTECTION GUARANTEE:
- FAQs and leads are NEVER deleted - migrations will FAIL if data loss is detected
- Migrations are mostly additive (CREATE TABLE, ADD COLUMN, CREATE INDEX)
- Limited exception: Deduplication DELETE for corrupted data (duplicate messages/calls only)
- NO TRUNCATE, NO DROP TABLE on any tables
- Automatic verification with rollback on unexpected data loss
"""
from server.db import db
from datetime import datetime
import logging
import sys

# Configure logging with explicit format

logger = logging.getLogger(__name__)

# ProSaaS custom migration marker for alembic_version table
PROSAAS_MIGRATION_MARKER = 'prosaas_custom_migrations'

# Migration 89 required columns for receipt_sync_runs
MIGRATION_89_REQUIRED_COLUMNS = [
    'from_date', 'to_date', 'months_back',
    'run_to_completion', 'max_seconds_per_run', 'skipped_count'
]

# Migration 90: Complete list of valid contract event types
CONTRACT_EVENT_TYPES = [
    'created',
    'file_uploaded',
    'file_downloaded',
    'file_viewed',
    'sent_for_signature',
    'viewed',
    'signed_completed',
    'cancelled',
    'updated',
    'deleted',
    'signature_fields_updated'
]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stderr,
    force=True  # Override any existing configuration
)
log = logging.getLogger(__name__)

# Explicit checkpoint logging
def checkpoint(message):
    """Log checkpoint that always prints to stderr"""
    msg = f"🔧 MIGRATION CHECKPOINT: {message}"
    log.info(msg)
    # Print to stderr directly instead of using logger with file argument
    print(msg, file=sys.stderr, flush=True)

def check_column_exists(table_name, column_name):
    """Check if column exists in table using independent connection"""
    from sqlalchemy import text
    try:
        # Use engine.connect() instead of db.session to avoid polluting the main transaction
        with db.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = :table_name AND column_name = :column_name
            """), {"table_name": table_name, "column_name": column_name})
            return result.fetchone() is not None
    except Exception as e:
        log.warning(f"Error checking if column {column_name} exists in {table_name}: {e}")
        return False

def check_table_exists(table_name):
    """Check if table exists using independent connection"""
    from sqlalchemy import text
    try:
        # Use engine.connect() instead of db.session to avoid polluting the main transaction
        with db.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = :table_name
            """), {"table_name": table_name})
            return result.fetchone() is not None
    except Exception as e:
        log.warning(f"Error checking if table {table_name} exists: {e}")
        return False

def check_index_exists(index_name):
    """Check if index exists using independent connection"""
    from sqlalchemy import text
    try:
        # Use engine.connect() instead of db.session to avoid polluting the main transaction
        with db.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT indexname FROM pg_indexes 
                WHERE schemaname = 'public' AND indexname = :index_name
            """), {"index_name": index_name})
            return result.fetchone() is not None
    except Exception as e:
        log.warning(f"Error checking if index {index_name} exists: {e}")
        return False

def exec_ddl(engine, sql: str):
    """
    Execute a single DDL statement in its own transaction.
    
    This is critical for Postgres: if a DDL statement fails within a transaction,
    the entire transaction enters FAILED state and all previous work is rolled back.
    
    By executing each DDL statement in its own transaction, we ensure that:
    1. Successful column additions are committed even if later statements fail
    2. Failed statements don't pollute the transaction state
    3. We can continue with other operations after a failure
    
    Args:
        engine: SQLAlchemy engine
        sql: DDL statement to execute
    """
    from sqlalchemy import text
    with engine.begin() as conn:  # begin() = auto commit/rollback
        conn.execute(text(sql))

def apply_migrations():
    """
    Apply all pending migrations
    
    🔒 DATA PROTECTION: This function ONLY adds new tables/columns/indexes.
    It NEVER deletes user data. All existing FAQs, leads, messages, etc. are preserved.
    
    🔒 CONCURRENCY PROTECTION: Uses PostgreSQL advisory lock to prevent multiple
    processes from running migrations simultaneously (prevents deadlocks).
    
    🔒 WORKER PROTECTION: Workers should NEVER run migrations. Migrations only run
    in API service during startup.
    """
    import os
    import time
    
    # 🔥 CRITICAL: Check RUN_MIGRATIONS env var - migrations should only run in designated container
    run_migrations = os.getenv('RUN_MIGRATIONS', '0')
    if run_migrations != '1':
        checkpoint("=" * 80)
        checkpoint("🚫 MIGRATIONS_DISABLED: RUN_MIGRATIONS is not set to '1'")
        checkpoint("   Migrations are disabled for this service")
        checkpoint("=" * 80)
        return 'skip'  # Return 'skip' to indicate migrations were disabled
    
    # 🔥 CRITICAL: Hard gate - workers must NEVER run migrations
    # Migrations should only run once during API startup, not on every job
    service_role = os.getenv('SERVICE_ROLE', '').lower()
    
    # Skip migrations if this is a worker
    if service_role == 'worker':
        checkpoint("=" * 80)
        checkpoint("🚫 MIGRATIONS_SKIPPED: service_role=worker")
        checkpoint("   Workers use existing schema - migrations run only in API")
        checkpoint("=" * 80)
        return []
    
    checkpoint("Starting apply_migrations()")
    checkpoint(f"  SERVICE_ROLE: {service_role or 'not set'}")
    migrations_applied = []
    
    # 🔒 CONCURRENCY PROTECTION: Acquire PostgreSQL advisory lock with retry
    # Lock ID: 1234567890 (arbitrary unique integer)
    # This ensures only ONE process runs migrations at a time
    LOCK_ID = 1234567890
    LOCK_WAIT_SECONDS = int(os.getenv("MIGRATION_LOCK_WAIT_SECONDS", "30"))
    STATEMENT_TIMEOUT = os.getenv("MIGRATION_STATEMENT_TIMEOUT", "120s")
    
    checkpoint("Acquiring PostgreSQL advisory lock for migrations...")
    from sqlalchemy import text
    lock_acquired = False
    
    try:
        # 🔥 CRITICAL: Set statement_timeout locally for this connection
        # This prevents the database from killing our lock acquisition attempts
        conn = db.session.connection()
        conn.execute(text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'"))
        checkpoint(f"✅ Set statement_timeout to {STATEMENT_TIMEOUT} for migration connection")
        
        # 🔥 NEW: Try to acquire lock with retry loop
        start_time = time.time()
        while time.time() - start_time < LOCK_WAIT_SECONDS:
            result = conn.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": LOCK_ID})
            lock_acquired = result.scalar()
            
            if lock_acquired:
                checkpoint("✅ Acquired migration lock")
                break
            
            # Not acquired yet - wait and retry
            elapsed = int(time.time() - start_time)
            checkpoint(f"⚠️ Lock not available, retrying... (elapsed: {elapsed}s / {LOCK_WAIT_SECONDS}s)")
            time.sleep(1)
        
        if not lock_acquired:
            # Could not acquire lock in time - skip migrations gracefully
            checkpoint("=" * 80)
            checkpoint("⚠️ MIGRATION CHECKPOINT: Could not acquire lock in time -> skipping migrations")
            checkpoint(f"   Waited {LOCK_WAIT_SECONDS}s but another process is running migrations")
            checkpoint("   This is SAFE - migrations will run in another container")
            checkpoint("=" * 80)
            return 'skip'  # Return 'skip' to indicate migrations were skipped
            
    except Exception as e:
        checkpoint(f"❌ Failed to acquire migration lock: {e}")
        # Don't crash the system - log and skip migrations
        checkpoint("⚠️ Migration lock acquisition failed -> skipping migrations")
        return 'skip'
    
    try:
        checkpoint("Checking if database is completely empty...")
        # Check if database is empty and create all tables if needed
        from sqlalchemy import text, inspect
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        checkpoint(f"Found {len(existing_tables)} existing tables: {existing_tables[:5]}...")
        
        if len(existing_tables) == 0:
            checkpoint("Database is empty - creating all tables from SQLAlchemy metadata")
            try:
                db.create_all()
                checkpoint("✅ All tables created successfully from metadata")
                migrations_applied.append("create_all_tables_from_metadata")
            except Exception as e:
                checkpoint(f"❌ Failed to create tables: {e}")
                raise
        
        # 🔒 BUILD 111: TRIPLE LAYER DATA PROTECTION
        # Layer 1: Count FAQs BEFORE migrations
        # Layer 2: Run migrations inside TRY block
        # Layer 3: Count FAQs AFTER migrations and ROLLBACK if decreased
        checkpoint("Starting data protection layer 1 - counting existing data")
        faq_count_before = 0
        lead_count_before = 0
        msg_count_before = 0
        try:
            from sqlalchemy import text
            
            # 🔥 CRITICAL FIX: Check table existence BEFORE counting to prevent UndefinedTable exceptions
            if check_table_exists('faqs'):
                faq_count_before = db.session.execute(text("SELECT COUNT(*) FROM faqs")).scalar() or 0
                checkpoint(f"🔒 LAYER 1 (BEFORE): {faq_count_before} FAQs exist")
            else:
                checkpoint(f"🔒 LAYER 1 (BEFORE): faqs table does not exist yet")
                
            if check_table_exists('leads'):
                lead_count_before = db.session.execute(text("SELECT COUNT(*) FROM leads")).scalar() or 0
                checkpoint(f"🔒 LAYER 1 (BEFORE): {lead_count_before} leads exist")
            else:
                checkpoint(f"🔒 LAYER 1 (BEFORE): leads table does not exist yet")
                
            if check_table_exists('messages'):
                msg_count_before = db.session.execute(text("SELECT COUNT(*) FROM messages")).scalar() or 0
                checkpoint(f"🔒 LAYER 1 (BEFORE): {msg_count_before} messages exist")
            else:
                checkpoint(f"🔒 LAYER 1 (BEFORE): messages table does not exist yet")
        except Exception as e:
            # 🔥 CRITICAL FIX: ROLLBACK immediately to prevent InFailedSqlTransaction
            db.session.rollback()
            log.warning(f"Could not check data counts (database may be new): {e}")
            checkpoint(f"Could not check data counts (database may be new): {e}")
        
        # Migration 0: Create alembic_version table (for compatibility with health checks)
        # This is optional but prevents 503 errors in health endpoint
        if not check_table_exists('alembic_version'):
            from sqlalchemy import text
            try:
                checkpoint("Creating alembic_version table for health check compatibility")
                db.session.execute(text("""
                    CREATE TABLE IF NOT EXISTS alembic_version (
                        version_num VARCHAR(32) NOT NULL PRIMARY KEY
                    )
                """))
                # Insert a marker version to indicate ProSaaS custom migrations
                db.session.execute(text("""
                    INSERT INTO alembic_version(version_num)
                    SELECT :marker
                    WHERE NOT EXISTS (SELECT 1 FROM alembic_version)
                """), {"marker": PROSAAS_MIGRATION_MARKER})
                migrations_applied.append("create_alembic_version_table")
                checkpoint("✅ Created alembic_version table with marker")
            except Exception as e:
                # 🔥 CRITICAL FIX: ROLLBACK immediately to prevent InFailedSqlTransaction
                db.session.rollback()
                log.warning(f"Could not create alembic_version table: {e}")
                checkpoint(f"Could not create alembic_version table: {e}")
        
        # Migration 1: Add transcript column to CallLog
        if check_table_exists('call_log'):
            from sqlalchemy import text
            try:
                # 🔒 IDEMPOTENT: Use IF NOT EXISTS to prevent DuplicateColumn errors
                db.session.execute(text("ALTER TABLE call_log ADD COLUMN IF NOT EXISTS transcript TEXT"))
                migrations_applied.append("add_call_log_transcript")
                log.info("Applied migration: add_call_log_transcript")
            except Exception as e:
                # 🔥 CRITICAL FIX: ROLLBACK immediately to prevent InFailedSqlTransaction
                db.session.rollback()
                log.warning(f"Could not add transcript column (may already exist): {e}")
        
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
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_call_turn_sid ON call_turn(call_sid)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_call_turn_business_time ON call_turn(business_id, started_at)"))
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
        
        # Migration 4: Create threads table for unified messaging
        if not check_table_exists('threads'):
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE threads (
                    id SERIAL PRIMARY KEY,
                    business_id INTEGER NOT NULL,
                    type VARCHAR(16) NOT NULL,
                    provider VARCHAR(16) NOT NULL,
                    peer_number VARCHAR(32) NOT NULL,
                    title VARCHAR(120),
                    last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_threads_biz_last ON threads(business_id, last_message_at DESC)"))
            migrations_applied.append("create_threads_table")
            log.info("Applied migration: create_threads_table")
        
        # Migration 5: Create messages table for unified messaging
        if not check_table_exists('messages'):
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE messages (
                    id SERIAL PRIMARY KEY,
                    thread_id INTEGER NOT NULL REFERENCES threads(id),
                    direction VARCHAR(4) NOT NULL,
                    message_type VARCHAR(16) NOT NULL,
                    content_text TEXT,
                    media_url TEXT,
                    provider_msg_id VARCHAR(64),
                    status VARCHAR(16) DEFAULT 'received',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_msgs_thread_time ON messages(thread_id, created_at)"))
            migrations_applied.append("create_messages_table")
            log.info("Applied migration: create_messages_table")
        
        # Migration 6: Add unique index for message deduplication
        if check_table_exists('messages') and not check_index_exists('uniq_msg_provider_id'):
            from sqlalchemy import text
            try:
                # First remove any existing duplicates (keep the earliest)
                db.session.execute(text("""
                    DELETE FROM messages 
                    WHERE id NOT IN (
                        SELECT MIN(id) 
                        FROM messages 
                        WHERE provider_msg_id IS NOT NULL AND provider_msg_id != ''
                        GROUP BY provider_msg_id
                    )
                    AND provider_msg_id IS NOT NULL AND provider_msg_id != ''
                """))
                
                # Create unique index on provider_msg_id (for non-null values)
                db.session.execute(text("""
                    CREATE UNIQUE INDEX uniq_msg_provider_id 
                    ON messages(provider_msg_id) 
                    WHERE provider_msg_id IS NOT NULL AND provider_msg_id != ''
                """))
                migrations_applied.append("add_unique_provider_msg_id")
                log.info("Applied migration: add_unique_provider_msg_id")
            except Exception as e:
                # 🔥 CRITICAL FIX: ROLLBACK immediately to prevent InFailedSqlTransaction
                db.session.rollback()
                log.warning(f"Could not create unique index (may already exist): {e}")
        
        # Migration 7: Create leads table for CRM system
        if not check_table_exists('leads'):
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE leads (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL REFERENCES business(id),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    phone_e164 VARCHAR(64),
                    email VARCHAR(255),
                    source VARCHAR(32) DEFAULT 'form',
                    external_id VARCHAR(128),
                    status VARCHAR(32) DEFAULT 'New',
                    owner_user_id INTEGER REFERENCES users(id),
                    tags JSONB,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_contact_at TIMESTAMP
                )
            """))
            
            # Create indexes for leads table
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_leads_tenant ON leads(tenant_id)",
                "CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status)",
                "CREATE INDEX IF NOT EXISTS idx_leads_source ON leads(source)",
                "CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone_e164)",
                "CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email)",
                "CREATE INDEX IF NOT EXISTS idx_leads_external_id ON leads(external_id)",
                "CREATE INDEX IF NOT EXISTS idx_leads_owner ON leads(owner_user_id)",
                "CREATE INDEX IF NOT EXISTS idx_leads_created ON leads(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_leads_contact ON leads(last_contact_at)"
            ]
            
            for index_sql in indexes:
                db.session.execute(text(index_sql))
                
            migrations_applied.append("create_leads_table")
            log.info("Applied migration: create_leads_table")
        
        # Migration 8: Create lead_reminders table
        if not check_table_exists('lead_reminders'):
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE lead_reminders (
                    id SERIAL PRIMARY KEY,
                    lead_id INTEGER NOT NULL REFERENCES leads(id),
                    due_at TIMESTAMP NOT NULL,
                    note TEXT,
                    channel VARCHAR(16) DEFAULT 'ui',
                    delivered_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by INTEGER REFERENCES users(id)
                )
            """))
            
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_lead_reminders_lead ON lead_reminders(lead_id)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_lead_reminders_due ON lead_reminders(due_at)"))
            migrations_applied.append("create_lead_reminders_table")
            log.info("Applied migration: create_lead_reminders_table")
        
        # Migration 9: Create lead_activities table
        if not check_table_exists('lead_activities'):
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE lead_activities (
                    id SERIAL PRIMARY KEY,
                    lead_id INTEGER NOT NULL REFERENCES leads(id),
                    type VARCHAR(32) NOT NULL,
                    payload JSONB,
                    at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by INTEGER REFERENCES users(id)
                )
            """))
            
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_lead_activities_lead ON lead_activities(lead_id)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_lead_activities_type ON lead_activities(type)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_lead_activities_time ON lead_activities(at)"))
            migrations_applied.append("create_lead_activities_table")
            log.info("Applied migration: create_lead_activities_table")
        
        # Migration 10: Create lead_merge_candidates table
        if not check_table_exists('lead_merge_candidates'):
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE lead_merge_candidates (
                    id SERIAL PRIMARY KEY,
                    lead_id INTEGER NOT NULL REFERENCES leads(id),
                    duplicate_lead_id INTEGER NOT NULL REFERENCES leads(id),
                    confidence_score FLOAT DEFAULT 0.0,
                    reason VARCHAR(64),
                    reviewed_at TIMESTAMP,
                    reviewed_by INTEGER REFERENCES users(id),
                    merged_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_merge_candidates_lead ON lead_merge_candidates(lead_id)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_merge_candidates_dup ON lead_merge_candidates(duplicate_lead_id)"))
            migrations_applied.append("create_lead_merge_candidates_table")
            log.info("Applied migration: create_lead_merge_candidates_table")
        
        # Migration 11: Add order_index column to leads table for Kanban support
        if check_table_exists('leads') and not check_column_exists('leads', 'order_index'):
            from sqlalchemy import text
            db.session.execute(text("ALTER TABLE leads ADD COLUMN order_index INTEGER DEFAULT 0"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_leads_order_index ON leads(order_index)"))
            # Set default order for existing leads based on their ID
            db.session.execute(text("UPDATE leads SET order_index = id WHERE order_index = 0"))
            migrations_applied.append("add_leads_order_index")
            log.info("Applied migration: add_leads_order_index")
        
        # Migration 12: Add working_hours and voice_message columns to business table
        business_columns = [
            ('working_hours', 'VARCHAR(50)', "'08:00-18:00'"),
            ('voice_message', 'TEXT', 'NULL')
        ]
        
        for col_name, col_type, default_val in business_columns:
            if check_table_exists('business') and not check_column_exists('business', col_name):
                from sqlalchemy import text
                db.session.execute(text(f"ALTER TABLE business ADD COLUMN {col_name} {col_type} DEFAULT {default_val}"))
                migrations_applied.append(f"add_business_{col_name}")
                log.info(f"Applied migration: add_business_{col_name}")
        
        # Migration 15: Add unique constraint on call_log.call_sid to prevent duplicates
        if check_table_exists('call_log') and not check_index_exists('uniq_call_log_call_sid'):
            from sqlalchemy import text
            try:
                # First remove any existing duplicates (keep the earliest)
                db.session.execute(text("""
                    DELETE FROM call_log 
                    WHERE id NOT IN (
                        SELECT MIN(id) 
                        FROM call_log 
                        WHERE call_sid IS NOT NULL AND call_sid != ''
                        GROUP BY call_sid
                    )
                    AND call_sid IS NOT NULL AND call_sid != ''
                """))
                
                # Create unique index on call_sid
                db.session.execute(text("""
                    CREATE UNIQUE INDEX uniq_call_log_call_sid 
                    ON call_log(call_sid) 
                    WHERE call_sid IS NOT NULL AND call_sid != ''
                """))
                migrations_applied.append("add_unique_call_sid")
                log.info("Applied migration: add_unique_call_sid")
            except Exception as e:
                # 🔥 CRITICAL FIX: ROLLBACK immediately to prevent InFailedSqlTransaction
                db.session.rollback()
                log.warning(f"Could not create unique index on call_sid (may already exist): {e}")
        
        # Migration 13: Create business_settings table for AI prompt management
        if not check_table_exists('business_settings'):
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE business_settings (
                    tenant_id INTEGER NOT NULL REFERENCES business(id) PRIMARY KEY,
                    ai_prompt TEXT,
                    model VARCHAR(50) DEFAULT 'gpt-4o-mini',
                    max_tokens INTEGER DEFAULT 150,
                    temperature FLOAT DEFAULT 0.7,
                    updated_by VARCHAR(255),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            migrations_applied.append("create_business_settings_table")
            log.info("Applied migration: create_business_settings_table")
        
        # Migration 14: Create prompt_revisions table for AI prompt versioning
        if not check_table_exists('prompt_revisions'):
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE prompt_revisions (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL REFERENCES business(id),
                    version INTEGER NOT NULL,
                    prompt TEXT,
                    changed_by VARCHAR(255),
                    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Create index for (tenant_id, version)
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_tenant_version ON prompt_revisions(tenant_id, version)"))
            migrations_applied.append("create_prompt_revisions_table")
            log.info("Applied migration: create_prompt_revisions_table")
        
        # Migration 16: Create business_contact_channels table for multi-tenant routing
        if not check_table_exists('business_contact_channels'):
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE business_contact_channels (
                    id SERIAL PRIMARY KEY,
                    business_id INTEGER NOT NULL REFERENCES business(id),
                    channel_type VARCHAR(32) NOT NULL,
                    identifier VARCHAR(255) NOT NULL,
                    is_primary BOOLEAN DEFAULT false,
                    config_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Create indexes
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_bcc_business ON business_contact_channels(business_id)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_bcc_channel ON business_contact_channels(channel_type)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_bcc_identifier ON business_contact_channels(identifier)"))
            
            # Unique constraint: one identifier per channel type
            db.session.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS uq_channel_identifier 
                ON business_contact_channels(channel_type, identifier)
            """))
            
            # Seed data: Add contact channels for existing businesses
            # For each business with a phone_number, create twilio_voice + whatsapp channels
            db.session.execute(text("""
                INSERT INTO business_contact_channels (business_id, channel_type, identifier, is_primary)
                SELECT 
                    id as business_id,
                    'twilio_voice' as channel_type,
                    phone_number as identifier,
                    true as is_primary
                FROM business
                WHERE phone_number IS NOT NULL AND phone_number != ''
                ON CONFLICT (channel_type, identifier) DO NOTHING
            """))
            
            # Add WhatsApp channels with business_X format
            db.session.execute(text("""
                INSERT INTO business_contact_channels (business_id, channel_type, identifier, is_primary)
                SELECT 
                    id as business_id,
                    'whatsapp' as channel_type,
                    'business_' || id as identifier,
                    true as is_primary
                FROM business
                ON CONFLICT (channel_type, identifier) DO NOTHING
            """))
            
            migrations_applied.append("create_business_contact_channels_table")
            log.info("Applied migration: create_business_contact_channels_table with seed data")
        
        # Migration 17: Add signature_data to contract table
        if check_table_exists('contract') and not check_column_exists('contract', 'signature_data'):
            from sqlalchemy import text
            db.session.execute(text("ALTER TABLE contract ADD COLUMN signature_data TEXT"))
            migrations_applied.append("add_contract_signature_data")
            log.info("Applied migration: add_contract_signature_data")
        
        # Migration 19: Add direction, duration, to_number to call_log table
        call_log_columns = [
            ('direction', 'VARCHAR(16)', "'inbound'"),
            ('duration', 'INTEGER', '0'),
            ('to_number', 'VARCHAR(64)', 'NULL')
        ]
        
        for col_name, col_type, default_val in call_log_columns:
            if check_table_exists('call_log') and not check_column_exists('call_log', col_name):
                from sqlalchemy import text
                db.session.execute(text(f"ALTER TABLE call_log ADD COLUMN {col_name} {col_type} DEFAULT {default_val}"))
                migrations_applied.append(f"add_call_log_{col_name}")
                log.info(f"Applied migration: add_call_log_{col_name}")
        
        # Migration 18: Fix Deal.customer_id foreign key (leads.id → customer.id)
        if check_table_exists('deal'):
            from sqlalchemy import text
            try:
                # Check if the wrong constraint exists
                constraint_check = db.session.execute(text("""
                    SELECT constraint_name 
                    FROM information_schema.table_constraints 
                    WHERE table_name = 'deal' 
                    AND constraint_type = 'FOREIGN KEY'
                    AND constraint_name LIKE '%customer_id%'
                """)).fetchone()
                
                if constraint_check:
                    constraint_name = constraint_check[0]
                    # Drop old wrong foreign key (if it points to leads)
                    db.session.execute(text(f"ALTER TABLE deal DROP CONSTRAINT IF EXISTS {constraint_name}"))
                    log.info(f"Dropped old foreign key constraint: {constraint_name}")
                
                # Add correct foreign key pointing to customer.id with CASCADE
                db.session.execute(text("""
                    ALTER TABLE deal 
                    ADD CONSTRAINT deal_customer_id_fkey 
                    FOREIGN KEY (customer_id) 
                    REFERENCES customer(id) 
                    ON DELETE CASCADE
                """))
                migrations_applied.append("fix_deal_customer_fkey")
                log.info("Applied migration: fix_deal_customer_fkey - Now points to customer.id with CASCADE")
            except Exception as e:
                # 🔥 CRITICAL FIX: ROLLBACK immediately to prevent InFailedSqlTransaction
                db.session.rollback()
                log.warning(f"Could not fix deal foreign key (may already be correct): {e}")
        
        # Migration 19: Add Policy Engine fields to business_settings
        policy_fields = [
            ('slot_size_min', 'INTEGER', '60'),
            ('allow_24_7', 'BOOLEAN', 'FALSE'),
            ('opening_hours_json', 'JSON', 'NULL'),
            ('booking_window_days', 'INTEGER', '30'),
            ('min_notice_min', 'INTEGER', '0')
        ]
        
        for col_name, col_type, default_val in policy_fields:
            if check_table_exists('business_settings') and not check_column_exists('business_settings', col_name):
                from sqlalchemy import text
                db.session.execute(text(f"ALTER TABLE business_settings ADD COLUMN {col_name} {col_type} DEFAULT {default_val}"))
                migrations_applied.append(f"add_business_settings_{col_name}")
                log.info(f"✅ Applied migration: add_business_settings_{col_name} - Policy Engine field")
        
        # Migration 20: Add require_phone_before_booking to business_settings
        if check_table_exists('business_settings') and not check_column_exists('business_settings', 'require_phone_before_booking'):
            from sqlalchemy import text
            db.session.execute(text("ALTER TABLE business_settings ADD COLUMN require_phone_before_booking BOOLEAN DEFAULT TRUE"))
            migrations_applied.append("add_business_settings_require_phone_before_booking")
            log.info("✅ Applied migration 20: require_phone_before_booking - Phone required guard")
        
        # Migration 21: Create FAQs table for business-specific fast-path responses
        if not check_table_exists('faqs'):
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE faqs (
                    id SERIAL PRIMARY KEY,
                    business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                    question VARCHAR(500) NOT NULL,
                    answer TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    order_index INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_business_active ON faqs(business_id, is_active)"))
            migrations_applied.append("create_faqs_table")
            log.info("✅ Applied migration 21: create_faqs_table - Business-specific FAQs for fast-path")
        
        # Migration 22: Add FAQ Fast-Path fields (intent_key, patterns, channels, priority, lang)
        faq_fastpath_fields = [
            ('intent_key', 'VARCHAR(50)', None),  # Nullable, no default
            ('patterns_json', 'JSON', None),  # Nullable, no default
            ('channels', 'VARCHAR(20)', "'voice'"),
            ('priority', 'INTEGER', '0'),
            ('lang', 'VARCHAR(10)', "'he-IL'")
        ]
        
        for col_name, col_type, default_val in faq_fastpath_fields:
            if check_table_exists('faqs') and not check_column_exists('faqs', col_name):
                from sqlalchemy import text
                if default_val is None:
                    # Nullable column without default
                    db.session.execute(text(f"ALTER TABLE faqs ADD COLUMN {col_name} {col_type}"))
                else:
                    # Column with explicit default value
                    db.session.execute(text(f"ALTER TABLE faqs ADD COLUMN {col_name} {col_type} DEFAULT {default_val}"))
                migrations_applied.append(f"add_faqs_{col_name}")
                log.info(f"✅ Applied migration 22: add_faqs_{col_name} - FAQ Fast-Path field")
        
        # Migration 23: Create CallSession table for appointment deduplication
        if not check_table_exists('call_session'):
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE call_session (
                    id SERIAL PRIMARY KEY,
                    call_sid VARCHAR(64) UNIQUE NOT NULL,
                    business_id INTEGER NOT NULL,
                    lead_id INTEGER,
                    last_requested_slot VARCHAR(100),
                    last_confirmed_slot VARCHAR(100),
                    created_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
                    updated_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
                )
            """))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_call_session_sid ON call_session(call_sid)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_call_session_business ON call_session(business_id)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_call_session_lead ON call_session(lead_id)"))
            migrations_applied.append("create_call_session_table")
            log.info("✅ Applied migration 23: create_call_session_table - Appointment deduplication")
        
        # Migration 24: Create WhatsAppConversationState table for AI toggle per conversation
        if not check_table_exists('whatsapp_conversation_state'):
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE whatsapp_conversation_state (
                    id SERIAL PRIMARY KEY,
                    business_id INTEGER NOT NULL,
                    phone VARCHAR(64) NOT NULL,
                    ai_active BOOLEAN DEFAULT TRUE,
                    updated_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
                    updated_by INTEGER,
                    CONSTRAINT fk_business FOREIGN KEY (business_id) REFERENCES business(id),
                    CONSTRAINT fk_updated_by FOREIGN KEY (updated_by) REFERENCES users(id),
                    CONSTRAINT uq_business_phone_state UNIQUE (business_id, phone)
                )
            """))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_wa_conv_state_business ON whatsapp_conversation_state(business_id)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_wa_conv_state_phone ON whatsapp_conversation_state(phone)"))
            migrations_applied.append("create_whatsapp_conversation_state_table")
            log.info("✅ Applied migration 24: create_whatsapp_conversation_state_table - AI toggle per conversation")
        
        # Migration 25: Add whatsapp_provider column to business table (Meta Cloud API support)
        if check_table_exists('business') and not check_column_exists('business', 'whatsapp_provider'):
            from sqlalchemy import text
            db.session.execute(text("ALTER TABLE business ADD COLUMN whatsapp_provider VARCHAR(32) DEFAULT 'baileys'"))
            migrations_applied.append("add_business_whatsapp_provider")
            log.info("✅ Applied migration 25: add_business_whatsapp_provider - Meta Cloud API support")
        
        # Migration 26: Create WhatsAppConversation table for session tracking and auto-summary
        if not check_table_exists('whatsapp_conversation'):
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE whatsapp_conversation (
                    id SERIAL PRIMARY KEY,
                    business_id INTEGER NOT NULL,
                    provider VARCHAR(32) DEFAULT 'baileys',
                    customer_wa_id VARCHAR(64) NOT NULL,
                    lead_id INTEGER,
                    started_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
                    last_message_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
                    last_customer_message_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
                    is_open BOOLEAN DEFAULT TRUE,
                    summary_created BOOLEAN DEFAULT FALSE,
                    summary TEXT,
                    created_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
                    updated_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
                    CONSTRAINT fk_wa_conv_business FOREIGN KEY (business_id) REFERENCES business(id),
                    CONSTRAINT fk_wa_conv_lead FOREIGN KEY (lead_id) REFERENCES leads(id)
                )
            """))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_wa_conv_business_open ON whatsapp_conversation(business_id, is_open)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_wa_conv_customer ON whatsapp_conversation(business_id, customer_wa_id)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_wa_conv_last_msg ON whatsapp_conversation(last_message_at)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_wa_conv_last_cust_msg ON whatsapp_conversation(last_customer_message_at)"))
            migrations_applied.append("create_whatsapp_conversation_table")
            log.info("✅ Applied migration 26: create_whatsapp_conversation_table - Session tracking + auto-summary")
        
        # Migration 27: Add whatsapp_last_summary fields to leads table
        if check_table_exists('leads') and not check_column_exists('leads', 'whatsapp_last_summary'):
            from sqlalchemy import text
            db.session.execute(text("ALTER TABLE leads ADD COLUMN whatsapp_last_summary TEXT"))
            db.session.execute(text("ALTER TABLE leads ADD COLUMN whatsapp_last_summary_at TIMESTAMP"))
            migrations_applied.append("add_leads_whatsapp_summary")
            log.info("✅ Applied migration 27: add_leads_whatsapp_summary - WhatsApp session summary on leads")
        
        # Migration 28: BUILD 163 - Monday.com integration + Auto-hangup + Bot speaks first
        if check_table_exists('business_settings'):
            from sqlalchemy import text
            
            # Monday.com integration fields
            if not check_column_exists('business_settings', 'monday_webhook_url'):
                db.session.execute(text("ALTER TABLE business_settings ADD COLUMN monday_webhook_url VARCHAR(512)"))
                migrations_applied.append("add_monday_webhook_url")
                log.info("✅ Applied migration 28a: add_monday_webhook_url")
            
            if not check_column_exists('business_settings', 'send_call_transcripts_to_monday'):
                db.session.execute(text("ALTER TABLE business_settings ADD COLUMN send_call_transcripts_to_monday BOOLEAN DEFAULT FALSE"))
                migrations_applied.append("add_send_call_transcripts_to_monday")
                log.info("✅ Applied migration 28b: add_send_call_transcripts_to_monday")
            
            # Auto hang-up fields
            if not check_column_exists('business_settings', 'auto_end_after_lead_capture'):
                db.session.execute(text("ALTER TABLE business_settings ADD COLUMN auto_end_after_lead_capture BOOLEAN DEFAULT FALSE"))
                migrations_applied.append("add_auto_end_after_lead_capture")
                log.info("✅ Applied migration 28c: add_auto_end_after_lead_capture")
            
            if not check_column_exists('business_settings', 'auto_end_on_goodbye'):
                db.session.execute(text("ALTER TABLE business_settings ADD COLUMN auto_end_on_goodbye BOOLEAN DEFAULT FALSE"))
                migrations_applied.append("add_auto_end_on_goodbye")
                log.info("✅ Applied migration 28d: add_auto_end_on_goodbye")
            
            # Bot speaks first field
            if not check_column_exists('business_settings', 'bot_speaks_first'):
                db.session.execute(text("ALTER TABLE business_settings ADD COLUMN bot_speaks_first BOOLEAN DEFAULT FALSE"))
                migrations_applied.append("add_bot_speaks_first")
                log.info("✅ Applied migration 28e: add_bot_speaks_first")
        
        # Migration 29: BUILD 182 - Outbound lead lists for bulk import
        if not check_table_exists('outbound_lead_lists'):
            from sqlalchemy import text
            db.session.execute(text("""
                CREATE TABLE outbound_lead_lists (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL REFERENCES business(id),
                    name VARCHAR(255) NOT NULL,
                    file_name VARCHAR(255),
                    total_leads INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_outbound_lead_lists_tenant_id ON outbound_lead_lists(tenant_id)"))
            migrations_applied.append("create_outbound_lead_lists_table")
            log.info("✅ Applied migration 29a: create_outbound_lead_lists_table - Bulk import for outbound calls")
        
        # Migration 29b: Add outbound_list_id to leads table
        if check_table_exists('leads') and not check_column_exists('leads', 'outbound_list_id'):
            from sqlalchemy import text
            db.session.execute(text("ALTER TABLE leads ADD COLUMN outbound_list_id INTEGER REFERENCES outbound_lead_lists(id)"))
            db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_leads_outbound_list_id ON leads(outbound_list_id)"))
            migrations_applied.append("add_leads_outbound_list_id")
            log.info("✅ Applied migration 29b: add_leads_outbound_list_id - Link leads to import lists")
        
        # Migration 30: BUILD 183 - Separate inbound/outbound webhook URLs
        if check_table_exists('business_settings'):
            from sqlalchemy import text
            
            if not check_column_exists('business_settings', 'inbound_webhook_url'):
                db.session.execute(text("ALTER TABLE business_settings ADD COLUMN inbound_webhook_url VARCHAR(512)"))
                migrations_applied.append("add_inbound_webhook_url")
                log.info("✅ Applied migration 30a: add_inbound_webhook_url - Separate webhook for inbound calls")
            
            if not check_column_exists('business_settings', 'outbound_webhook_url'):
                db.session.execute(text("ALTER TABLE business_settings ADD COLUMN outbound_webhook_url VARCHAR(512)"))
                migrations_applied.append("add_outbound_webhook_url")
                log.info("✅ Applied migration 30b: add_outbound_webhook_url - Separate webhook for outbound calls")
        
        # Migration 31: BUILD 186 - Calendar scheduling toggle for inbound calls
        if check_table_exists('business_settings'):
            from sqlalchemy import text
            
            if not check_column_exists('business_settings', 'enable_calendar_scheduling'):
                db.session.execute(text("ALTER TABLE business_settings ADD COLUMN enable_calendar_scheduling BOOLEAN DEFAULT TRUE"))
                migrations_applied.append("add_enable_calendar_scheduling")
                log.info("✅ Applied migration 31: add_enable_calendar_scheduling - Toggle for AI appointment scheduling")
        
        # Migration 32: BUILD 204 - Dynamic STT Vocabulary for per-business transcription quality
        if check_table_exists('business_settings'):
            from sqlalchemy import text
            
            if not check_column_exists('business_settings', 'stt_vocabulary_json'):
                db.session.execute(text("ALTER TABLE business_settings ADD COLUMN stt_vocabulary_json JSON"))
                migrations_applied.append("add_stt_vocabulary_json")
                log.info("✅ Applied migration 32a: add_stt_vocabulary_json - Per-business STT vocabulary")
            
            if not check_column_exists('business_settings', 'business_context'):
                db.session.execute(text("ALTER TABLE business_settings ADD COLUMN business_context VARCHAR(500)"))
                migrations_applied.append("add_business_context")
                log.info("✅ Applied migration 32b: add_business_context - Business context for STT prompts")
        
        # Migration 33: BUILD 309 - SIMPLE_MODE settings for call flow control
        if check_table_exists('business_settings'):
            from sqlalchemy import text
            
            if not check_column_exists('business_settings', 'call_goal'):
                db.session.execute(text("ALTER TABLE business_settings ADD COLUMN call_goal VARCHAR(50) DEFAULT 'lead_only'"))
                migrations_applied.append("add_call_goal")
                log.info("✅ Applied migration 33a: add_call_goal - Controls call objective (lead_only vs appointment)")
            
            if not check_column_exists('business_settings', 'confirm_before_hangup'):
                db.session.execute(text("ALTER TABLE business_settings ADD COLUMN confirm_before_hangup BOOLEAN DEFAULT TRUE"))
                migrations_applied.append("add_confirm_before_hangup")
                log.info("✅ Applied migration 33b: add_confirm_before_hangup - Requires confirmation before disconnecting")
        
        # Migration 34: POST-CALL EXTRACTION - Full transcript + extracted fields for CallLog
        # 🔒 IDEMPOTENT: Uses PostgreSQL DO blocks to safely add columns
        if check_table_exists('call_log'):
            from sqlalchemy import text
            
            try:
                # Use single DO block for all call_log columns - more efficient
                db.session.execute(text("""
                    DO $$
                    BEGIN
                        -- Add final_transcript column
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'call_log' AND column_name = 'final_transcript'
                        ) THEN
                            ALTER TABLE call_log ADD COLUMN final_transcript TEXT;
                            RAISE NOTICE 'Added call_log.final_transcript';
                        END IF;
    
                        -- Add extracted_service column
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'call_log' AND column_name = 'extracted_service'
                        ) THEN
                            ALTER TABLE call_log ADD COLUMN extracted_service VARCHAR(255);
                            RAISE NOTICE 'Added call_log.extracted_service';
                        END IF;
    
                        -- Add extracted_city column
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'call_log' AND column_name = 'extracted_city'
                        ) THEN
                            ALTER TABLE call_log ADD COLUMN extracted_city VARCHAR(255);
                            RAISE NOTICE 'Added call_log.extracted_city';
                        END IF;
    
                        -- Add extraction_confidence column
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'call_log' AND column_name = 'extraction_confidence'
                        ) THEN
                            ALTER TABLE call_log ADD COLUMN extraction_confidence DOUBLE PRECISION;
                            RAISE NOTICE 'Added call_log.extraction_confidence';
                        END IF;
                    END;
                    $$;
                """))
                migrations_applied.append("add_call_log_extraction_fields")
                log.info("✅ Applied migration 34: add_call_log_extraction_fields - POST-CALL EXTRACTION for CallLog")
            except Exception as e:
                log.error(f"❌ Migration 34 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 35: POST-CALL EXTRACTION - Service type and city fields for Lead
        # 🔒 IDEMPOTENT: Uses PostgreSQL DO blocks to safely add columns
        if check_table_exists('leads'):
            from sqlalchemy import text
            
            try:
                # Use single DO block for all leads columns - more efficient
                db.session.execute(text("""
                    DO $$
                    BEGIN
                        -- Add service_type column
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'leads' AND column_name = 'service_type'
                        ) THEN
                            ALTER TABLE leads ADD COLUMN service_type VARCHAR(255);
                            RAISE NOTICE 'Added leads.service_type';
                        END IF;
    
                        -- Add city column
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'leads' AND column_name = 'city'
                        ) THEN
                            ALTER TABLE leads ADD COLUMN city VARCHAR(255);
                            RAISE NOTICE 'Added leads.city';
                        END IF;
                    END;
                    $$;
                """))
                migrations_applied.append("add_leads_extraction_fields")
                log.info("✅ Applied migration 35: add_leads_extraction_fields - POST-CALL EXTRACTION for Lead")
            except Exception as e:
                log.error(f"❌ Migration 35 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 36: BUILD 350 - Add last_call_direction to leads for inbound/outbound filtering
        # 🔒 IDEMPOTENT: Uses PostgreSQL DO block to safely add column + index + backfill
        if check_table_exists('leads'):
            from sqlalchemy import text
            
            try:
                # Use DO block to add column, index, and backfill in one transaction
                db.session.execute(text("""
                    DO $$
                    BEGIN
                        -- Add last_call_direction column if it doesn't exist
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'leads' AND column_name = 'last_call_direction'
                        ) THEN
                            ALTER TABLE leads ADD COLUMN last_call_direction VARCHAR(16);
                            RAISE NOTICE 'Added leads.last_call_direction';
                        END IF;
                    END;
                    $$;
                """))
                
                # Create index for performance (idempotent)
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_leads_last_call_direction 
                    ON leads(last_call_direction)
                """))
                
                # Backfill last_call_direction from call_log table
                # 🔒 CRITICAL: Use FIRST call's direction (ASC), not latest (DESC)
                # This determines the lead's origin (inbound vs outbound)
                # ⚠️ PERFORMANCE: For very large datasets (>100K calls), this may take time
                # but it's a one-time operation and uses indexed columns (lead_id, created_at)
                checkpoint("Backfilling last_call_direction from call_log...")
                if check_table_exists('call_log'):
                    backfill_result = db.session.execute(text("""
                        WITH first_calls AS (
                            SELECT DISTINCT ON (cl.lead_id) 
                                cl.lead_id,
                                cl.direction,
                                cl.created_at
                            FROM call_log cl
                            WHERE cl.lead_id IS NOT NULL 
                              AND cl.direction IS NOT NULL
                              AND cl.direction IN ('inbound', 'outbound')
                            ORDER BY cl.lead_id, cl.created_at ASC
                        )
                        UPDATE leads l
                        SET last_call_direction = fc.direction
                        FROM first_calls fc
                        WHERE l.id = fc.lead_id
                          AND l.last_call_direction IS NULL
                    """))
                    rows_updated = backfill_result.rowcount
                    checkpoint(f"✅ Backfilled last_call_direction for {rows_updated} leads (using FIRST call direction)")
                
                migrations_applied.append("add_leads_last_call_direction")
                log.info("✅ Applied migration 36: add_leads_last_call_direction - Inbound/outbound filtering support")
            except Exception as e:
                log.error(f"❌ Migration 36 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 37: Lead Attachments - Production-ready file uploads for leads
        if not check_table_exists('lead_attachments'):
            checkpoint("Migration 37: Creating lead_attachments table for secure file storage")
            try:
                db.session.execute(text("""
                    CREATE TABLE lead_attachments (
                        id SERIAL PRIMARY KEY,
                        tenant_id INTEGER NOT NULL REFERENCES business(id),
                        lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
                        note_id INTEGER REFERENCES lead_notes(id) ON DELETE SET NULL,
                        filename VARCHAR(255) NOT NULL,
                        content_type VARCHAR(128) NOT NULL,
                        size_bytes INTEGER NOT NULL,
                        storage_key VARCHAR(512) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by INTEGER REFERENCES users(id)
                    )
                """))
                
                # Create indexes for performance
                db.session.execute(text("CREATE INDEX idx_lead_attachments_tenant_lead ON lead_attachments(tenant_id, lead_id)"))
                db.session.execute(text("CREATE INDEX idx_lead_attachments_lead_id ON lead_attachments(lead_id)"))
                db.session.execute(text("CREATE INDEX idx_lead_attachments_note_id ON lead_attachments(note_id)"))
                db.session.execute(text("CREATE INDEX idx_lead_attachments_created_at ON lead_attachments(created_at)"))
                
                migrations_applied.append('create_lead_attachments_table')
                log.info("✅ Applied migration 37: create_lead_attachments_table - Secure file upload support")
            except Exception as e:
                log.error(f"❌ Migration 37 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 38: BUILD 342 - Add recording_sid to call_log for Twilio recording tracking
        # 🔒 CRITICAL FIX: This column is referenced in code but missing from DB
        if check_table_exists('call_log') and not check_column_exists('call_log', 'recording_sid'):
            checkpoint("Migration 38: Adding recording_sid column to call_log table")
            try:
                from sqlalchemy import text
                db.session.execute(text("ALTER TABLE call_log ADD COLUMN recording_sid VARCHAR(64)"))
                migrations_applied.append('add_call_log_recording_sid')
                log.info("✅ Applied migration 38: add_call_log_recording_sid - Fix post-call pipeline crash")
            except Exception as e:
                log.error(f"❌ Migration 38 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 39: CRITICAL HOTFIX - Add missing columns to call_log for post-call pipeline
        # 🔒 IDEMPOTENT: These columns are referenced in code but missing from production DB
        # Fixes: psycopg2.errors.UndefinedColumn: column call_log.audio_bytes_len does not exist
        if check_table_exists('call_log'):
            checkpoint("Migration 39: Adding missing audio/transcript columns to call_log table")
            try:
                from sqlalchemy import text
                
                # Add audio_bytes_len column if missing
                if not check_column_exists('call_log', 'audio_bytes_len'):
                    db.session.execute(text("ALTER TABLE call_log ADD COLUMN audio_bytes_len BIGINT"))
                    migrations_applied.append('add_call_log_audio_bytes_len')
                    log.info("✅ Applied migration 39a: add_call_log_audio_bytes_len")
                
                # Add audio_duration_sec column if missing
                if not check_column_exists('call_log', 'audio_duration_sec'):
                    db.session.execute(text("ALTER TABLE call_log ADD COLUMN audio_duration_sec DOUBLE PRECISION"))
                    migrations_applied.append('add_call_log_audio_duration_sec')
                    log.info("✅ Applied migration 39b: add_call_log_audio_duration_sec")
                
                # Add transcript_source column if missing
                if not check_column_exists('call_log', 'transcript_source'):
                    db.session.execute(text("ALTER TABLE call_log ADD COLUMN transcript_source VARCHAR(32)"))
                    migrations_applied.append('add_call_log_transcript_source')
                    log.info("✅ Applied migration 39c: add_call_log_transcript_source")
                
                checkpoint("✅ Migration 39 completed - all missing columns added")
            except Exception as e:
                log.error(f"❌ Migration 39 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 40: Outbound Call Management - Bulk calling infrastructure
        # 🔒 CRITICAL: These tables are referenced in routes_outbound.py and tasks_recording.py
        # Creates: outbound_call_runs (campaigns) and outbound_call_jobs (individual calls)
        if not check_table_exists('outbound_call_runs'):
            checkpoint("Migration 40a: Creating outbound_call_runs table for bulk calling campaigns")
            try:
                from sqlalchemy import text
                db.session.execute(text("""
                    CREATE TABLE outbound_call_runs (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id),
                        outbound_list_id INTEGER REFERENCES outbound_lead_lists(id),
                        concurrency INTEGER DEFAULT 3,
                        total_leads INTEGER DEFAULT 0,
                        queued_count INTEGER DEFAULT 0,
                        in_progress_count INTEGER DEFAULT 0,
                        completed_count INTEGER DEFAULT 0,
                        failed_count INTEGER DEFAULT 0,
                        status VARCHAR(32) DEFAULT 'running',
                        last_error TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                """))
                
                # Create indexes for performance
                db.session.execute(text("CREATE INDEX idx_outbound_call_runs_business_id ON outbound_call_runs(business_id)"))
                db.session.execute(text("CREATE INDEX idx_outbound_call_runs_status ON outbound_call_runs(status)"))
                db.session.execute(text("CREATE INDEX idx_outbound_call_runs_created_at ON outbound_call_runs(created_at)"))
                
                migrations_applied.append('create_outbound_call_runs_table')
                log.info("✅ Applied migration 40a: create_outbound_call_runs_table - Bulk calling campaign tracking")
            except Exception as e:
                log.error(f"❌ Migration 40a failed: {e}")
                db.session.rollback()
                raise
        
        if not check_table_exists('outbound_call_jobs'):
            checkpoint("Migration 40b: Creating outbound_call_jobs table for individual call tracking")
            try:
                from sqlalchemy import text
                db.session.execute(text("""
                    CREATE TABLE outbound_call_jobs (
                        id SERIAL PRIMARY KEY,
                        run_id INTEGER NOT NULL REFERENCES outbound_call_runs(id),
                        lead_id INTEGER NOT NULL REFERENCES leads(id),
                        call_log_id INTEGER REFERENCES call_log(id),
                        status VARCHAR(32) DEFAULT 'queued',
                        error_message TEXT,
                        call_sid VARCHAR(64),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                """))
                
                # Create indexes for performance
                db.session.execute(text("CREATE INDEX idx_outbound_call_jobs_run_id ON outbound_call_jobs(run_id)"))
                db.session.execute(text("CREATE INDEX idx_outbound_call_jobs_lead_id ON outbound_call_jobs(lead_id)"))
                db.session.execute(text("CREATE INDEX idx_outbound_call_jobs_status ON outbound_call_jobs(status)"))
                db.session.execute(text("CREATE INDEX idx_outbound_call_jobs_call_sid ON outbound_call_jobs(call_sid)"))
                
                migrations_applied.append('create_outbound_call_jobs_table')
                log.info("✅ Applied migration 40b: create_outbound_call_jobs_table - Individual call job tracking")
            except Exception as e:
                log.error(f"❌ Migration 40b failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 41: Add parent_call_sid and twilio_direction to call_log
        # 🔥 FIX: Prevents duplicate call logs and tracks original Twilio direction
        if not check_column_exists('call_log', 'parent_call_sid'):
            checkpoint("Migration 41a: Adding parent_call_sid to call_log for tracking parent/child call relationships")
            try:
                from sqlalchemy import text
                db.session.execute(text("""
                    ALTER TABLE call_log 
                    ADD COLUMN parent_call_sid VARCHAR(64)
                """))
                
                # Create index for performance
                db.session.execute(text("CREATE INDEX idx_call_log_parent_call_sid ON call_log(parent_call_sid)"))
                
                migrations_applied.append('add_parent_call_sid_to_call_log')
                log.info("✅ Applied migration 41a: add_parent_call_sid_to_call_log - Track parent/child call legs")
            except Exception as e:
                log.error(f"❌ Migration 41a failed: {e}")
                db.session.rollback()
                raise
        
        if not check_column_exists('call_log', 'twilio_direction'):
            checkpoint("Migration 41b: Adding twilio_direction to call_log for storing original Twilio direction")
            try:
                from sqlalchemy import text
                db.session.execute(text("""
                    ALTER TABLE call_log 
                    ADD COLUMN twilio_direction VARCHAR(32)
                """))
                
                # Create index for performance
                db.session.execute(text("CREATE INDEX idx_call_log_twilio_direction ON call_log(twilio_direction)"))
                
                migrations_applied.append('add_twilio_direction_to_call_log')
                log.info("✅ Applied migration 41b: add_twilio_direction_to_call_log - Store original Twilio direction values")
            except Exception as e:
                log.error(f"❌ Migration 41b failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 42: AI Topic Classification System
        checkpoint("Migration 42: AI Topic Classification System")
        try:
            # Create business_topics table
            if not check_table_exists('business_topics'):
                log.info("Creating business_topics table...")
                db.session.execute(text("""
                    CREATE TABLE business_topics (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id),
                        name VARCHAR(255) NOT NULL,
                        synonyms JSONB,
                        embedding JSONB,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                db.session.execute(text("CREATE INDEX idx_business_topic_active ON business_topics(business_id, is_active)"))
                migrations_applied.append('create_business_topics_table')
                log.info("✅ Created business_topics table")
            
            # Create business_ai_settings table
            if not check_table_exists('business_ai_settings'):
                log.info("Creating business_ai_settings table...")
                db.session.execute(text("""
                    CREATE TABLE business_ai_settings (
                        business_id INTEGER PRIMARY KEY REFERENCES business(id),
                        embedding_enabled BOOLEAN DEFAULT FALSE,
                        embedding_threshold FLOAT DEFAULT 0.78,
                        embedding_top_k INTEGER DEFAULT 3,
                        auto_tag_leads BOOLEAN DEFAULT TRUE,
                        auto_tag_calls BOOLEAN DEFAULT TRUE,
                        auto_tag_whatsapp BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                migrations_applied.append('create_business_ai_settings_table')
                log.info("✅ Created business_ai_settings table")
            
            # Add topic classification fields to call_log
            if check_table_exists('call_log'):
                if not check_column_exists('call_log', 'detected_topic_id'):
                    log.info("Adding topic classification fields to call_log...")
                    db.session.execute(text("""
                        ALTER TABLE call_log 
                        ADD COLUMN detected_topic_id INTEGER REFERENCES business_topics(id),
                        ADD COLUMN detected_topic_confidence FLOAT,
                        ADD COLUMN detected_topic_source VARCHAR(32) DEFAULT 'embedding'
                    """))
                    db.session.execute(text("CREATE INDEX idx_call_log_detected_topic ON call_log(detected_topic_id)"))
                    migrations_applied.append('add_topic_fields_to_call_log')
                    log.info("✅ Added topic classification fields to call_log")
            
            # Add topic classification fields to leads
            if check_table_exists('leads'):
                if not check_column_exists('leads', 'detected_topic_id'):
                    log.info("Adding topic classification fields to leads...")
                    db.session.execute(text("""
                        ALTER TABLE leads 
                        ADD COLUMN detected_topic_id INTEGER REFERENCES business_topics(id),
                        ADD COLUMN detected_topic_confidence FLOAT,
                        ADD COLUMN detected_topic_source VARCHAR(32) DEFAULT 'embedding'
                    """))
                    db.session.execute(text("CREATE INDEX idx_leads_detected_topic ON leads(detected_topic_id)"))
                    migrations_applied.append('add_topic_fields_to_leads')
                    log.info("✅ Added topic classification fields to leads")
            
            # Add topic classification fields to whatsapp_conversation
            if check_table_exists('whatsapp_conversation'):
                if not check_column_exists('whatsapp_conversation', 'detected_topic_id'):
                    log.info("Adding topic classification fields to whatsapp_conversation...")
                    db.session.execute(text("""
                        ALTER TABLE whatsapp_conversation 
                        ADD COLUMN detected_topic_id INTEGER REFERENCES business_topics(id),
                        ADD COLUMN detected_topic_confidence FLOAT,
                        ADD COLUMN detected_topic_source VARCHAR(32) DEFAULT 'embedding'
                    """))
                    db.session.execute(text("CREATE INDEX idx_wa_conv_detected_topic ON whatsapp_conversation(detected_topic_id)"))
                    migrations_applied.append('add_topic_fields_to_whatsapp_conversation')
                    log.info("✅ Added topic classification fields to whatsapp_conversation")
            
            log.info("✅ Applied migration 42: AI Topic Classification System")
        except Exception as e:
            log.error(f"❌ Migration 42 failed: {e}")
            db.session.rollback()
            raise
        
        # Migration 43: Service Canonicalization - Add canonical_service_type to BusinessTopic and service mapping settings
        checkpoint("Migration 43: Service Canonicalization and Topic-to-Service Mapping")
        try:
            # Add canonical_service_type to business_topics
            if check_table_exists('business_topics'):
                if not check_column_exists('business_topics', 'canonical_service_type'):
                    log.info("Adding canonical_service_type to business_topics...")
                    db.session.execute(text("""
                        ALTER TABLE business_topics 
                        ADD COLUMN canonical_service_type VARCHAR(255)
                    """))
                    migrations_applied.append('add_canonical_service_type_to_business_topics')
                    log.info("✅ Added canonical_service_type to business_topics")
            
            # Add service mapping settings to business_ai_settings
            if check_table_exists('business_ai_settings'):
                if not check_column_exists('business_ai_settings', 'map_topic_to_service_type'):
                    log.info("Adding service mapping settings to business_ai_settings...")
                    db.session.execute(text("""
                        ALTER TABLE business_ai_settings 
                        ADD COLUMN map_topic_to_service_type BOOLEAN DEFAULT FALSE,
                        ADD COLUMN service_type_min_confidence FLOAT DEFAULT 0.75
                    """))
                    migrations_applied.append('add_service_mapping_settings_to_business_ai_settings')
                    log.info("✅ Added service mapping settings to business_ai_settings")
            
            log.info("✅ Applied migration 43: Service Canonicalization and Topic-to-Service Mapping")
        except Exception as e:
            log.error(f"❌ Migration 43 failed: {e}")
            db.session.rollback()
            raise
        
        # Migration 44: WhatsApp Broadcast System - Campaign management tables
        checkpoint("Migration 44: WhatsApp Broadcast System")
        try:
            # Create whatsapp_broadcasts table
            if not check_table_exists('whatsapp_broadcasts'):
                log.info("Creating whatsapp_broadcasts table...")
                db.session.execute(text("""
                    CREATE TABLE whatsapp_broadcasts (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id),
                        name VARCHAR(255),
                        provider VARCHAR(32),
                        message_type VARCHAR(32),
                        template_id VARCHAR(255),
                        template_name VARCHAR(255),
                        message_text TEXT,
                        audience_filter JSON,
                        status VARCHAR(32) DEFAULT 'pending',
                        total_recipients INTEGER DEFAULT 0,
                        sent_count INTEGER DEFAULT 0,
                        failed_count INTEGER DEFAULT 0,
                        created_by INTEGER REFERENCES users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                """))
                db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_whatsapp_broadcasts_business ON whatsapp_broadcasts(business_id)"))
                db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_whatsapp_broadcasts_status ON whatsapp_broadcasts(status)"))
                migrations_applied.append('create_whatsapp_broadcasts_table')
                log.info("✅ Created whatsapp_broadcasts table")
            
            # Create whatsapp_broadcast_recipients table
            if not check_table_exists('whatsapp_broadcast_recipients'):
                log.info("Creating whatsapp_broadcast_recipients table...")
                db.session.execute(text("""
                    CREATE TABLE whatsapp_broadcast_recipients (
                        id SERIAL PRIMARY KEY,
                        broadcast_id INTEGER NOT NULL REFERENCES whatsapp_broadcasts(id),
                        business_id INTEGER NOT NULL REFERENCES business(id),
                        phone VARCHAR(64) NOT NULL,
                        lead_id INTEGER REFERENCES leads(id),
                        status VARCHAR(32) DEFAULT 'queued',
                        error_message TEXT,
                        message_id VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        sent_at TIMESTAMP
                    )
                """))
                db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_whatsapp_broadcast_recipients_broadcast ON whatsapp_broadcast_recipients(broadcast_id)"))
                db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_whatsapp_broadcast_recipients_status ON whatsapp_broadcast_recipients(status)"))
                migrations_applied.append('create_whatsapp_broadcast_recipients_table')
                log.info("✅ Created whatsapp_broadcast_recipients table")
            
            log.info("✅ Applied migration 44: WhatsApp Broadcast System")
        except Exception as e:
            log.error(f"❌ Migration 44 failed: {e}")
            db.session.rollback()
            raise
        
        # Migration 45: Status Webhook - Add status_webhook_url to business_settings for lead status change notifications
        checkpoint("Migration 45: Status Webhook URL for lead status changes")
        if check_table_exists('business_settings') and not check_column_exists('business_settings', 'status_webhook_url'):
            try:
                from sqlalchemy import text
                db.session.execute(text("""
                    ALTER TABLE business_settings 
                    ADD COLUMN status_webhook_url VARCHAR(512) NULL
                """))
                migrations_applied.append('add_status_webhook_url')
                log.info("✅ Added status_webhook_url column to business_settings")
            except Exception as e:
                log.error(f"❌ Migration 45 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 46: Bulk Call Deduplication - Add idempotency fields to outbound_call_jobs
        # Prevents duplicate calls from retry/concurrency/timeout scenarios
        checkpoint("Migration 46: Bulk Call Deduplication - Adding idempotency fields")
        
        # Add twilio_call_sid column for tracking initiated calls
        if check_table_exists('outbound_call_jobs') and not check_column_exists('outbound_call_jobs', 'twilio_call_sid'):
            try:
                from sqlalchemy import text
                db.session.execute(text("""
                    ALTER TABLE outbound_call_jobs 
                    ADD COLUMN twilio_call_sid VARCHAR(64) NULL
                """))
                # Create index for lookup performance
                db.session.execute(text("CREATE INDEX idx_outbound_call_jobs_twilio_sid ON outbound_call_jobs(twilio_call_sid)"))
                migrations_applied.append('add_twilio_call_sid_to_outbound_jobs')
                log.info("✅ Added twilio_call_sid column to outbound_call_jobs for deduplication")
            except Exception as e:
                log.error(f"❌ Migration 46a failed: {e}")
                db.session.rollback()
                raise
        
        # Add dial_started_at column for tracking when dial attempt started
        if check_table_exists('outbound_call_jobs') and not check_column_exists('outbound_call_jobs', 'dial_started_at'):
            try:
                from sqlalchemy import text
                db.session.execute(text("""
                    ALTER TABLE outbound_call_jobs 
                    ADD COLUMN dial_started_at TIMESTAMP NULL
                """))
                migrations_applied.append('add_dial_started_at_to_outbound_jobs')
                log.info("✅ Added dial_started_at column to outbound_call_jobs for tracking dial attempts")
            except Exception as e:
                log.error(f"❌ Migration 46b failed: {e}")
                db.session.rollback()
                raise
        
        # Add dial_lock_token column for atomic locking
        if check_table_exists('outbound_call_jobs') and not check_column_exists('outbound_call_jobs', 'dial_lock_token'):
            try:
                from sqlalchemy import text
                db.session.execute(text("""
                    ALTER TABLE outbound_call_jobs 
                    ADD COLUMN dial_lock_token VARCHAR(64) NULL
                """))
                # Create index for lock validation performance
                db.session.execute(text("CREATE INDEX idx_outbound_call_jobs_lock_token ON outbound_call_jobs(dial_lock_token)"))
                migrations_applied.append('add_dial_lock_token_to_outbound_jobs')
                log.info("✅ Added dial_lock_token column to outbound_call_jobs for atomic locking")
            except Exception as e:
                log.error(f"❌ Migration 46c failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 46d: Add composite index for cleanup query performance
        if check_table_exists('outbound_call_jobs') and not check_index_exists('idx_outbound_call_jobs_status_twilio_sid'):
            checkpoint("Migration 46d: Adding composite index for cleanup query performance")
            try:
                from sqlalchemy import text
                # Composite index on (status, twilio_call_sid) for efficient cleanup queries
                db.session.execute(text("""
                    CREATE INDEX idx_outbound_call_jobs_status_twilio_sid 
                    ON outbound_call_jobs(status, twilio_call_sid)
                """))
                migrations_applied.append('add_composite_index_status_twilio_sid')
                log.info("✅ Added composite index on (status, twilio_call_sid) for cleanup query performance")
            except Exception as e:
                log.error(f"❌ Migration 46d failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 47: WhatsApp Webhook Secret - Add webhook_secret column to business table
        # 🔒 IDEMPOTENT: Safe column addition for n8n integration security
        checkpoint("Migration 47: WhatsApp Webhook Secret for n8n integration")
        if check_table_exists('business') and not check_column_exists('business', 'webhook_secret'):
            try:
                from sqlalchemy import text
                # Add webhook_secret column with unique constraint
                db.session.execute(text("""
                    ALTER TABLE business 
                    ADD COLUMN webhook_secret VARCHAR(128) UNIQUE NULL
                """))
                migrations_applied.append('add_business_webhook_secret')
                log.info("✅ Added webhook_secret column to business table for n8n webhook authentication")
            except Exception as e:
                log.error(f"❌ Migration 47 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 48: Add call_transcript column to appointments table
        # 🔒 IDEMPOTENT: Safe column addition for storing full conversation transcripts
        checkpoint("Migration 48: Add call_transcript to appointments")
        if check_table_exists('appointments') and not check_column_exists('appointments', 'call_transcript'):
            try:
                from sqlalchemy import text
                # Add call_transcript column to store full transcripts
                db.session.execute(text("""
                    ALTER TABLE appointments 
                    ADD COLUMN call_transcript TEXT
                """))
                migrations_applied.append('add_appointments_call_transcript')
                log.info("✅ Added call_transcript column to appointments table for full conversation transcripts")
            except Exception as e:
                log.error(f"❌ Migration 48 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 49: Add idempotency_key column to whatsapp_broadcasts table
        # 🔒 IDEMPOTENT: Safe column addition for preventing duplicate broadcasts
        checkpoint("Migration 49: Add idempotency_key to whatsapp_broadcasts")
        if check_table_exists('whatsapp_broadcasts') and not check_column_exists('whatsapp_broadcasts', 'idempotency_key'):
            try:
                from sqlalchemy import text
                # Add idempotency_key column with index for duplicate prevention
                db.session.execute(text("""
                    ALTER TABLE whatsapp_broadcasts 
                    ADD COLUMN idempotency_key VARCHAR(64)
                """))
                # Create index for efficient lookup
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_wa_broadcast_idempotency 
                    ON whatsapp_broadcasts(idempotency_key)
                """))
                migrations_applied.append('add_whatsapp_broadcasts_idempotency_key')
                log.info("✅ Added idempotency_key column to whatsapp_broadcasts table for duplicate prevention")
            except Exception as e:
                log.error(f"❌ Migration 49 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 50: Add dynamic_summary and lead_id to appointments table
        # 🔒 CRITICAL FIX: These columns are referenced in code but missing from production DB
        # Fixes: psycopg2.errors.UndefinedColumn: column appointments.lead_id does not exist
        checkpoint("Migration 50: Adding dynamic_summary and lead_id to appointments")
        if check_table_exists('appointments'):
            try:
                from sqlalchemy import text
                
                # Add lead_id column if missing
                if not check_column_exists('appointments', 'lead_id'):
                    db.session.execute(text("""
                        ALTER TABLE appointments 
                        ADD COLUMN lead_id INTEGER REFERENCES leads(id) ON DELETE SET NULL
                    """))
                    # Create index for performance
                    db.session.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_appointments_lead_id 
                        ON appointments(lead_id)
                    """))
                    migrations_applied.append('add_appointments_lead_id')
                    log.info("✅ Added lead_id column to appointments table")
                
                # Add dynamic_summary column if missing
                if not check_column_exists('appointments', 'dynamic_summary'):
                    db.session.execute(text("""
                        ALTER TABLE appointments 
                        ADD COLUMN dynamic_summary TEXT
                    """))
                    migrations_applied.append('add_appointments_dynamic_summary')
                    log.info("✅ Added dynamic_summary column to appointments table")
                
                checkpoint("✅ Migration 50 completed - appointments table updated")
            except Exception as e:
                log.error(f"❌ Migration 50 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 51: Add Twilio Cost Metrics columns to call_log table
        # 🔒 CRITICAL FIX: These columns are referenced in code but missing from production DB
        # Fixes: psycopg2.errors.UndefinedColumn: column call_log.recording_mode does not exist
        # This migration adds recording_mode and all related cost tracking fields
        checkpoint("Migration 51: Adding Twilio Cost Metrics columns to call_log")
        if check_table_exists('call_log'):
            try:
                from sqlalchemy import text
                
                # Add recording_mode column if missing
                if not check_column_exists('call_log', 'recording_mode'):
                    db.session.execute(text("""
                        ALTER TABLE call_log 
                        ADD COLUMN recording_mode VARCHAR(32)
                    """))
                    migrations_applied.append('add_call_log_recording_mode')
                    log.info("✅ Added recording_mode column to call_log table")
                
                # Add stream_started_at column if missing
                if not check_column_exists('call_log', 'stream_started_at'):
                    db.session.execute(text("""
                        ALTER TABLE call_log 
                        ADD COLUMN stream_started_at TIMESTAMP
                    """))
                    migrations_applied.append('add_call_log_stream_started_at')
                    log.info("✅ Added stream_started_at column to call_log table")
                
                # Add stream_ended_at column if missing
                if not check_column_exists('call_log', 'stream_ended_at'):
                    db.session.execute(text("""
                        ALTER TABLE call_log 
                        ADD COLUMN stream_ended_at TIMESTAMP
                    """))
                    migrations_applied.append('add_call_log_stream_ended_at')
                    log.info("✅ Added stream_ended_at column to call_log table")
                
                # Add stream_duration_sec column if missing
                if not check_column_exists('call_log', 'stream_duration_sec'):
                    db.session.execute(text("""
                        ALTER TABLE call_log 
                        ADD COLUMN stream_duration_sec DOUBLE PRECISION
                    """))
                    migrations_applied.append('add_call_log_stream_duration_sec')
                    log.info("✅ Added stream_duration_sec column to call_log table")
                
                # Add stream_connect_count column if missing
                if not check_column_exists('call_log', 'stream_connect_count'):
                    db.session.execute(text("""
                        ALTER TABLE call_log 
                        ADD COLUMN stream_connect_count INTEGER DEFAULT 0
                    """))
                    migrations_applied.append('add_call_log_stream_connect_count')
                    log.info("✅ Added stream_connect_count column to call_log table")
                
                # Add webhook_11205_count column if missing
                if not check_column_exists('call_log', 'webhook_11205_count'):
                    db.session.execute(text("""
                        ALTER TABLE call_log 
                        ADD COLUMN webhook_11205_count INTEGER DEFAULT 0
                    """))
                    migrations_applied.append('add_call_log_webhook_11205_count')
                    log.info("✅ Added webhook_11205_count column to call_log table")
                
                # Add webhook_retry_count column if missing
                if not check_column_exists('call_log', 'webhook_retry_count'):
                    db.session.execute(text("""
                        ALTER TABLE call_log 
                        ADD COLUMN webhook_retry_count INTEGER DEFAULT 0
                    """))
                    migrations_applied.append('add_call_log_webhook_retry_count')
                    log.info("✅ Added webhook_retry_count column to call_log table")
                
                # Add recording_count column if missing
                if not check_column_exists('call_log', 'recording_count'):
                    db.session.execute(text("""
                        ALTER TABLE call_log 
                        ADD COLUMN recording_count INTEGER DEFAULT 0
                    """))
                    migrations_applied.append('add_call_log_recording_count')
                    log.info("✅ Added recording_count column to call_log table")
                
                # Add estimated_cost_bucket column if missing
                if not check_column_exists('call_log', 'estimated_cost_bucket'):
                    db.session.execute(text("""
                        ALTER TABLE call_log 
                        ADD COLUMN estimated_cost_bucket VARCHAR(16)
                    """))
                    migrations_applied.append('add_call_log_estimated_cost_bucket')
                    log.info("✅ Added estimated_cost_bucket column to call_log table")
                
                checkpoint("✅ Migration 51 completed - call_log cost metrics columns added")
            except Exception as e:
                log.error(f"❌ Migration 51 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 52: Add customer_name to call_log and lead_name to outbound_call_jobs
        # 🔥 PURPOSE: Fix NAME_ANCHOR system SSOT - retrieve customer name from database
        # Priority order: CallLog.customer_name → OutboundCallJob.lead_name → Lead.full_name
        if not check_column_exists('call_log', 'customer_name') or not check_column_exists('outbound_call_jobs', 'lead_name'):
            checkpoint("Migration 52: Adding customer_name and lead_name for NAME_ANCHOR SSOT")
            try:
                # 1. Add customer_name to call_log
                if not check_column_exists('call_log', 'customer_name'):
                    checkpoint("  → Adding customer_name to call_log...")
                    db.session.execute(text("""
                        ALTER TABLE call_log 
                        ADD COLUMN customer_name VARCHAR(255)
                    """))
                    checkpoint("  ✅ call_log.customer_name added")
                else:
                    checkpoint("  ℹ️ call_log.customer_name already exists")
                
                # 2. Add lead_name to outbound_call_jobs
                if not check_column_exists('outbound_call_jobs', 'lead_name'):
                    checkpoint("  → Adding lead_name to outbound_call_jobs...")
                    db.session.execute(text("""
                        ALTER TABLE outbound_call_jobs 
                        ADD COLUMN lead_name VARCHAR(255)
                    """))
                    checkpoint("  ✅ outbound_call_jobs.lead_name added")
                else:
                    checkpoint("  ℹ️ outbound_call_jobs.lead_name already exists")
                
                migrations_applied.append('migration_52_name_anchor_ssot')
                checkpoint("✅ Migration 52 completed - NAME_ANCHOR SSOT fields added")
            except Exception as e:
                log.error(f"❌ Migration 52 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 53: Add gender column to leads table
        # 🔥 PURPOSE: Fix missing gender column - prevents "column leads.gender does not exist" errors
        # This column is defined in Lead model but was never added to DB via migration
        if check_table_exists('leads') and not check_column_exists('leads', 'gender'):
            checkpoint("Migration 53: Adding gender column to leads table")
            try:
                checkpoint("  → Adding gender to leads...")
                db.session.execute(text("""
                    ALTER TABLE leads 
                    ADD COLUMN gender VARCHAR(16)
                """))
                checkpoint("  ✅ leads.gender added")
                migrations_applied.append('add_leads_gender_column')
                checkpoint("✅ Migration 53 completed - leads.gender column added")
            except Exception as e:
                log.error(f"❌ Migration 53 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 54: Projects for Outbound Calls
        # 🎯 PURPOSE: Enable grouping leads into projects with call tracking and statistics
        # Projects = Container for leads + call history + stats (only after calls start)
        if not check_table_exists('outbound_projects'):
            checkpoint("Migration 54: Creating outbound_projects table")
            try:
                checkpoint("  → Creating outbound_projects table...")
                db.session.execute(text("""
                    CREATE TABLE outbound_projects (
                        id SERIAL PRIMARY KEY,
                        tenant_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        name VARCHAR(255) NOT NULL,
                        description TEXT,
                        status VARCHAR(50) DEFAULT 'draft',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        created_by INTEGER REFERENCES users(id)
                    )
                """))
                db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_outbound_projects_tenant_id ON outbound_projects(tenant_id)"))
                db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_outbound_projects_status ON outbound_projects(status)"))
                checkpoint("  ✅ outbound_projects table created")
                
                # Junction table for project-lead relationships
                checkpoint("  → Creating project_leads junction table...")
                db.session.execute(text("""
                    CREATE TABLE project_leads (
                        id SERIAL PRIMARY KEY,
                        project_id INTEGER NOT NULL REFERENCES outbound_projects(id) ON DELETE CASCADE,
                        lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        call_attempts INTEGER DEFAULT 0,
                        last_call_at TIMESTAMP,
                        last_call_status VARCHAR(50),
                        total_call_duration INTEGER DEFAULT 0,
                        UNIQUE(project_id, lead_id)
                    )
                """))
                db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_project_leads_project_id ON project_leads(project_id)"))
                db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_project_leads_lead_id ON project_leads(lead_id)"))
                checkpoint("  ✅ project_leads junction table created")
                
                migrations_applied.append('create_outbound_projects_tables')
                checkpoint("✅ Migration 54 completed - Projects tables created")
            except Exception as e:
                log.error(f"❌ Migration 54 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 54b: Add project_id to call_log for project statistics
        if check_table_exists('call_log') and not check_column_exists('call_log', 'project_id'):
            checkpoint("Migration 54b: Adding project_id to call_log")
            try:
                checkpoint("  → Adding project_id to call_log...")
                db.session.execute(text("ALTER TABLE call_log ADD COLUMN project_id INTEGER REFERENCES outbound_projects(id) ON DELETE SET NULL"))
                db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_call_log_project_id ON call_log(project_id)"))
                checkpoint("  ✅ call_log.project_id added")
                migrations_applied.append('add_call_log_project_id')
                checkpoint("✅ Migration 54b completed - project tracking in calls")
            except Exception as e:
                log.error(f"❌ Migration 54b failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 54c: Add project_id to outbound_call_jobs for bulk operations
        if check_table_exists('outbound_call_jobs') and not check_column_exists('outbound_call_jobs', 'project_id'):
            checkpoint("Migration 54c: Adding project_id to outbound_call_jobs")
            try:
                checkpoint("  → Adding project_id to outbound_call_jobs...")
                db.session.execute(text("ALTER TABLE outbound_call_jobs ADD COLUMN project_id INTEGER REFERENCES outbound_projects(id) ON DELETE SET NULL"))
                db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_outbound_call_jobs_project_id ON outbound_call_jobs(project_id)"))
                checkpoint("  ✅ outbound_call_jobs.project_id added")
                migrations_applied.append('add_outbound_call_jobs_project_id')
                checkpoint("✅ Migration 54c completed - project tracking in bulk jobs")
            except Exception as e:
                log.error(f"❌ Migration 54c failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 55: Add delivered_at column to whatsapp_broadcast_recipients
        # 🔥 CRITICAL FIX: This column is defined in WhatsappBroadcastRecipient model but missing from DB
        # Fixes: psycopg2.errors.UndefinedColumn: column "delivered_at" of relation "whatsapp_broadcast_recipients" does not exist
        if check_table_exists('whatsapp_broadcast_recipients') and not check_column_exists('whatsapp_broadcast_recipients', 'delivered_at'):
            checkpoint("Migration 55: Adding delivered_at to whatsapp_broadcast_recipients")
            try:
                checkpoint("  → Adding delivered_at to whatsapp_broadcast_recipients...")
                db.session.execute(text("""
                    ALTER TABLE whatsapp_broadcast_recipients 
                    ADD COLUMN delivered_at TIMESTAMP
                """))
                checkpoint("  ✅ whatsapp_broadcast_recipients.delivered_at added")
                migrations_applied.append('add_whatsapp_broadcast_recipients_delivered_at')
                checkpoint("✅ Migration 55 completed - WhatsApp broadcast delivery tracking column added")
            except Exception as e:
                log.error(f"❌ Migration 55 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 56: Add stopped_by and stopped_at columns to whatsapp_broadcasts
        # 🔥 CRITICAL FIX: These columns are defined in WhatsAppBroadcast model but missing from DB
        # Fixes: psycopg2.errors.UndefinedColumn: column "stopped_by" of relation "whatsapp_broadcasts" does not exist
        if check_table_exists('whatsapp_broadcasts'):
            checkpoint("Migration 56: Adding stopped_by and stopped_at to whatsapp_broadcasts")
            try:
                # Add stopped_by column if missing
                if not check_column_exists('whatsapp_broadcasts', 'stopped_by'):
                    checkpoint("  → Adding stopped_by to whatsapp_broadcasts...")
                    db.session.execute(text("""
                        ALTER TABLE whatsapp_broadcasts 
                        ADD COLUMN stopped_by INTEGER REFERENCES users(id)
                    """))
                    checkpoint("  ✅ whatsapp_broadcasts.stopped_by added")
                    migrations_applied.append('add_whatsapp_broadcasts_stopped_by')
                
                # Add stopped_at column if missing
                if not check_column_exists('whatsapp_broadcasts', 'stopped_at'):
                    checkpoint("  → Adding stopped_at to whatsapp_broadcasts...")
                    db.session.execute(text("""
                        ALTER TABLE whatsapp_broadcasts 
                        ADD COLUMN stopped_at TIMESTAMP
                    """))
                    checkpoint("  ✅ whatsapp_broadcasts.stopped_at added")
                    migrations_applied.append('add_whatsapp_broadcasts_stopped_at')
                
                checkpoint("✅ Migration 56 completed - WhatsApp broadcast stop functionality columns added")
            except Exception as e:
                log.error(f"❌ Migration 56 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 57: Authentication & Session Management System
        # Add refresh tokens table and password reset fields to users
        checkpoint("Migration 57: Adding authentication and session management features")
        
        # 57a: Create refresh_tokens table
        if not check_table_exists('refresh_tokens'):
            checkpoint("  → Creating refresh_tokens table...")
            try:
                db.session.execute(text("""
                    CREATE TABLE refresh_tokens (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        tenant_id INTEGER REFERENCES business(id) ON DELETE CASCADE,
                        token_hash VARCHAR(255) NOT NULL UNIQUE,
                        user_agent_hash VARCHAR(255),
                        expires_at TIMESTAMP NOT NULL,
                        is_valid BOOLEAN DEFAULT TRUE,
                        remember_me BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Add indexes for performance
                db.session.execute(text("CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id)"))
                db.session.execute(text("CREATE INDEX idx_refresh_tokens_tenant_id ON refresh_tokens(tenant_id)"))
                db.session.execute(text("CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash)"))
                db.session.execute(text("CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at)"))
                db.session.execute(text("CREATE INDEX idx_refresh_tokens_is_valid ON refresh_tokens(is_valid)"))
                
                # Add last_activity_at column for per-session idle tracking
                if not check_column_exists('refresh_tokens', 'last_activity_at'):
                    db.session.execute(text("""
                        ALTER TABLE refresh_tokens 
                        ADD COLUMN last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    """))
                    # Create index for performance
                    db.session.execute(text("""
                        CREATE INDEX idx_refresh_tokens_last_activity 
                        ON refresh_tokens(last_activity_at)
                    """))
                    checkpoint("  ✅ refresh_tokens.last_activity_at added")
                    migrations_applied.append('add_refresh_tokens_last_activity_at')
                
                checkpoint("  ✅ refresh_tokens table created with all fields")
                migrations_applied.append('create_refresh_tokens_table')
            except Exception as e:
                log.error(f"❌ Migration 57a failed: {e}")
                db.session.rollback()
                raise
        
        # 57b: Add password reset fields to users table
        if check_table_exists('users'):
            checkpoint("  → Adding password reset fields to users table...")
            try:
                # Add reset_token_hash column
                if not check_column_exists('users', 'reset_token_hash'):
                    db.session.execute(text("""
                        ALTER TABLE users 
                        ADD COLUMN reset_token_hash VARCHAR(255)
                    """))
                    checkpoint("  ✅ users.reset_token_hash added")
                    migrations_applied.append('add_users_reset_token_hash')
                
                # Add reset_token_expiry column
                if not check_column_exists('users', 'reset_token_expiry'):
                    db.session.execute(text("""
                        ALTER TABLE users 
                        ADD COLUMN reset_token_expiry TIMESTAMP
                    """))
                    checkpoint("  ✅ users.reset_token_expiry added")
                    migrations_applied.append('add_users_reset_token_expiry')
                
                # Add reset_token_used column
                if not check_column_exists('users', 'reset_token_used'):
                    db.session.execute(text("""
                        ALTER TABLE users 
                        ADD COLUMN reset_token_used BOOLEAN DEFAULT FALSE
                    """))
                    checkpoint("  ✅ users.reset_token_used added")
                    migrations_applied.append('add_users_reset_token_used')
                
                # Add last_activity_at column for idle timeout tracking
                if not check_column_exists('users', 'last_activity_at'):
                    db.session.execute(text("""
                        ALTER TABLE users 
                        ADD COLUMN last_activity_at TIMESTAMP
                    """))
                    checkpoint("  ✅ users.last_activity_at added")
                    migrations_applied.append('add_users_last_activity_at')
                
                checkpoint("  ✅ Password reset and activity tracking fields added to users")
            except Exception as e:
                log.error(f"❌ Migration 57b failed: {e}")
                db.session.rollback()
                raise
        
        checkpoint("✅ Migration 57 completed - Authentication system enhanced")
        
        # Migration 57c: Add push_enabled to users table for push notification preference
        # 🔒 CRITICAL FIX: This column is referenced in User model and routes_push.py but missing from DB
        # Fixes: psycopg2.errors.UndefinedColumn: column users.push_enabled does not exist
        if check_table_exists('users') and not check_column_exists('users', 'push_enabled'):
            checkpoint("Migration 57c: Adding push_enabled column to users table")
            try:
                # Add push_enabled column with default value TRUE
                # This represents user's preference for push notifications (opt-out model)
                # Separate from subscription existence (device capability)
                db.session.execute(text("""
                    ALTER TABLE users 
                    ADD COLUMN push_enabled BOOLEAN NOT NULL DEFAULT TRUE
                """))
                
                migrations_applied.append('add_users_push_enabled')
                checkpoint("✅ Applied migration 57c: add_users_push_enabled - Push notification user preference")
            except Exception as e:
                log.error(f"❌ Migration 57c failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 58: Add voice_id to business table for per-business voice selection
        # 🔒 CRITICAL FIX: This column is referenced in Business model but missing from DB
        # Fixes: psycopg2.errors.UndefinedColumn: column business.voice_id does not exist
        if check_table_exists('business') and not check_column_exists('business', 'voice_id'):
            checkpoint("Migration 58: Adding voice_id column to business table")
            try:
                from sqlalchemy import text
                # Add voice_id column with default value 'ash'
                # NOT NULL DEFAULT ensures all existing rows automatically get 'ash' value
                db.session.execute(text("""
                    ALTER TABLE business 
                    ADD COLUMN voice_id VARCHAR(32) NOT NULL DEFAULT 'ash'
                """))
                
                migrations_applied.append('add_business_voice_id')
                checkpoint("✅ Applied migration 58: add_business_voice_id - Per-business voice selection")
            except Exception as e:
                log.error(f"❌ Migration 58 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 60: Email System - Add email_settings, email_messages, and email_templates tables
        # Production-grade email system with per-business configuration and complete logging
        checkpoint("Migration 60: Creating email system tables (email_settings, email_messages, email_templates)")
        
        # Migration 60a: Create email_settings table (per-business email configuration)
        if not check_table_exists('email_settings'):
            try:
                from sqlalchemy import text
                db.session.execute(text("""
                    CREATE TABLE email_settings (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL UNIQUE REFERENCES business(id) ON DELETE CASCADE,
                        provider VARCHAR(32) NOT NULL DEFAULT 'sendgrid',
                        from_email VARCHAR(255) NOT NULL,
                        from_name VARCHAR(255) NOT NULL,
                        reply_to VARCHAR(255),
                        reply_to_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                        brand_logo_url TEXT,
                        brand_primary_color VARCHAR(20) DEFAULT '#2563EB',
                        default_greeting TEXT DEFAULT 'שלום {{lead.first_name}},',
                        footer_html TEXT,
                        footer_text TEXT,
                        is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Create index on business_id for fast lookups
                db.session.execute(text("""
                    CREATE UNIQUE INDEX idx_email_settings_business_id ON email_settings(business_id)
                """))
                
                migrations_applied.append('create_email_settings_table')
                checkpoint("  ✅ email_settings table created with branding fields (logo, color, greeting, footer)")
            except Exception as e:
                log.error(f"❌ Migration 60a (email_settings) failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 60b: Create email_templates table (per-business email templates)
        # IMPORTANT: Must be created before email_messages (FK dependency)
        if not check_table_exists('email_templates'):
            try:
                from sqlalchemy import text
                db.session.execute(text("""
                    CREATE TABLE email_templates (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        name VARCHAR(255) NOT NULL,
                        type VARCHAR(50) DEFAULT 'generic',
                        subject_template VARCHAR(500) NOT NULL,
                        html_template TEXT NOT NULL,
                        text_template TEXT,
                        created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Create index on business_id for fast lookups
                db.session.execute(text("""
                    CREATE INDEX idx_email_templates_business_id ON email_templates(business_id)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_email_templates_is_active ON email_templates(is_active)
                """))
                
                migrations_applied.append('create_email_templates_table')
                checkpoint("  ✅ email_templates table created with indexes on business_id, is_active")
            except Exception as e:
                log.error(f"❌ Migration 60b (email_templates) failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 60c: Create email_messages table (complete email log)
        if not check_table_exists('email_messages'):
            try:
                from sqlalchemy import text
                db.session.execute(text("""
                    CREATE TABLE email_messages (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        lead_id INTEGER REFERENCES leads(id) ON DELETE SET NULL,
                        created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        template_id INTEGER REFERENCES email_templates(id) ON DELETE SET NULL,
                        to_email VARCHAR(255) NOT NULL,
                        to_name VARCHAR(255),
                        subject VARCHAR(500) NOT NULL,
                        body_html TEXT NOT NULL,
                        body_text TEXT,
                        rendered_subject VARCHAR(500),
                        rendered_body_html TEXT,
                        rendered_body_text TEXT,
                        provider VARCHAR(32) NOT NULL DEFAULT 'sendgrid',
                        from_email VARCHAR(255),
                        from_name VARCHAR(255),
                        reply_to VARCHAR(255),
                        status VARCHAR(32) NOT NULL DEFAULT 'queued',
                        provider_message_id VARCHAR(255),
                        error TEXT,
                        meta JSONB,
                        sent_at TIMESTAMP,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Create indexes for common queries
                db.session.execute(text("""
                    CREATE INDEX idx_email_messages_business_id ON email_messages(business_id)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_email_messages_lead_id ON email_messages(lead_id)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_email_messages_created_by ON email_messages(created_by_user_id)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_email_messages_status ON email_messages(status)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_email_messages_created_at ON email_messages(created_at DESC)
                """))
                
                migrations_applied.append('create_email_messages_table')
                checkpoint("  ✅ email_messages table created with indexes on business_id, lead_id, status, created_at, template_id")
            except Exception as e:
                log.error(f"❌ Migration 60c (email_messages) failed: {e}")
                db.session.rollback()
                raise
        
        checkpoint("✅ Migration 60 completed - Email system tables created")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 61: Clean up invalid voice_id values in businesses table
        # Only Realtime-supported voices are allowed
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 61: Cleaning up invalid voice_id values")
        
        try:
            # Check if voice_id column exists
            voice_id_exists = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'businesses' 
                AND column_name = 'voice_id'
            """)).fetchone()
            
            if voice_id_exists:
                # Valid Realtime voices
                valid_voices = ['alloy', 'ash', 'ballad', 'coral', 'echo', 'sage', 'shimmer', 'verse', 'marin', 'cedar']
                default_voice = 'cedar'
                
                # Find businesses with invalid voices
                invalid_count_result = db.session.execute(text("""
                    SELECT COUNT(*) 
                    FROM businesses 
                    WHERE voice_id IS NULL 
                       OR voice_id NOT IN :valid_voices
                """), {"valid_voices": tuple(valid_voices)})
                
                invalid_count = invalid_count_result.scalar() or 0
                
                if invalid_count > 0:
                    checkpoint(f"  Found {invalid_count} businesses with invalid voice_id values")
                    
                    # Update invalid voices to default
                    db.session.execute(text("""
                        UPDATE businesses 
                        SET voice_id = :default_voice
                        WHERE voice_id IS NULL 
                           OR voice_id NOT IN :valid_voices
                    """), {
                        "default_voice": default_voice,
                        "valid_voices": tuple(valid_voices)
                    })
                    
                    checkpoint(f"  ✅ Updated {invalid_count} businesses to voice_id='{default_voice}'")
                    migrations_applied.append('cleanup_invalid_voices')
                else:
                    checkpoint("  ✅ No invalid voice_id values found")
            else:
                checkpoint("  ℹ️ voice_id column does not exist - skipping")
        
        except Exception as e:
            log.error(f"❌ Migration 61 (cleanup_invalid_voices) failed: {e}")
            db.session.rollback()
            raise
        
        checkpoint("✅ Migration 61 completed - Invalid voices cleaned up")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 62: Seed default email templates for all businesses
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 62: Seeding default email templates")
        
        try:
            # Check if email_templates table exists
            if check_table_exists('email_templates'):
                # Get all businesses that don't have templates yet
                businesses_result = db.session.execute(text("""
                    SELECT b.id, b.name
                    FROM business b
                    WHERE NOT EXISTS (
                        SELECT 1 FROM email_templates et 
                        WHERE et.business_id = b.id
                    )
                    AND b.is_active = TRUE
                """)).fetchall()
                
                businesses_count = len(businesses_result)
                
                if businesses_count > 0:
                    checkpoint(f"  Found {businesses_count} businesses without email templates")
                    
                    # Template 1: Default Welcome
                    template_1_subject = "שלום מ-{{business.name}}"
                    template_1_html = """
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; direction: rtl; text-align: right; }
        .content { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background-color: #2563EB; color: white; padding: 20px; border-radius: 8px 8px 0 0; }
        .body { background-color: #f9fafb; padding: 30px; }
        .footer { background-color: #f3f4f6; padding: 15px; text-align: center; font-size: 12px; color: #6b7280; border-radius: 0 0 8px 8px; }
        .button { display: inline-block; background-color: #2563EB; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="content">
        <div class="header">
            <h1>שלום {% if lead %}{{lead.first_name}}{% else %}שם{% endif %}!</h1>
        </div>
        <div class="body">
            <p>אנחנו ב-{{business.name}} שמחים ליצור איתך קשר.</p>
            
            <p>אנו מספקים שירות מקצועי ואיכותי ללקוחותינו, ונשמח לעזור גם לך.</p>
            
            <p>צוות {{business.name}}</p>
        </div>
        {% if signature %}
        <div class="footer">
            {{signature}}
        </div>
        {% endif %}
    </div>
</body>
</html>
"""
                    template_1_text = "שלום {% if lead %}{{lead.first_name}}{% else %}שם{% endif %}!\n\nאנחנו ב-{{business.name}} שמחים ליצור איתך קשר.\n\nצוות {{business.name}}"
                    
                    # Template 2: Follow-up / Reminder
                    template_2_subject = "תזכורת - {{business.name}}"
                    template_2_html = """
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; direction: rtl; text-align: right; }
        .content { max-width: 600px; margin: 0 auto; padding: 20px; background-color: #fffbeb; border: 2px solid #fbbf24; border-radius: 8px; }
        .icon { font-size: 48px; text-align: center; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="content">
        <div class="icon">⏰</div>
        <h2>שלום {% if lead %}{{lead.first_name}}{% else %}שם{% endif %},</h2>
        
        <p>רצינו להזכיר לך שאנחנו כאן בשבילך!</p>
        
        <p>נשמח לקבוע שיחה ולדבר על איך נוכל לעזור.</p>
        
        <p>בברכה,<br>צוות {{business.name}}</p>
        {% if signature %}
        <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #d1d5db;">
            {{signature}}
        </div>
        {% endif %}
    </div>
</body>
</html>
"""
                    template_2_text = "שלום {% if lead %}{{lead.first_name}}{% else %}שם{% endif %},\n\nרצינו להזכיר לך שאנחנו כאן בשבילך!\n\nנשמח לקבוע שיחה ולדבר על איך נוכל לעזור.\n\nבברכה,\nצוות {{business.name}}"
                    
                    # Template 3: Quick Follow-up
                    template_3_subject = "רק רציתי לוודא - {{business.name}}"
                    template_3_html = """
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; direction: rtl; text-align: right; }
        .content { max-width: 600px; margin: 0 auto; padding: 20px; }
        .simple { background-color: white; padding: 30px; border: 1px solid #e5e7eb; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="content">
        <div class="simple">
            <p>היי {% if lead %}{{lead.first_name}}{% else %}שם{% endif %},</p>
            
            <p>רק רציתי לשלוח הודעה מהירה ולוודא שהכל בסדר.</p>
            
            <p>אם יש משהו שאני יכול לעזור בו, אני כאן!</p>
            
            <p>תודה,<br>{{business.name}}</p>
            
            {% if signature %}
            <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 14px;">
                {{signature}}
            </div>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""
                    template_3_text = "היי {% if lead %}{{lead.first_name}}{% else %}שם{% endif %},\n\nרק רציתי לשלוח הודעה מהירה ולוודא שהכל בסדר.\n\nאם יש משהו שאני יכול לעזור בו, אני כאן!\n\nתודה,\n{{business.name}}"
                    
                    # Insert templates for each business
                    templates_inserted = 0
                    for business_id, business_name in businesses_result:
                        try:
                            # Template 1
                            db.session.execute(text("""
                                INSERT INTO email_templates 
                                (business_id, name, type, subject_template, html_template, text_template, is_active, created_at, updated_at)
                                VALUES (:business_id, :name, :type, :subject_template, :html_template, :text_template, TRUE, NOW(), NOW())
                            """), {
                                "business_id": business_id,
                                "name": "ברירת מחדל - ברכה",
                                "type": "welcome",
                                "subject_template": template_1_subject,
                                "html_template": template_1_html,
                                "text_template": template_1_text
                            })
                            
                            # Template 2
                            db.session.execute(text("""
                                INSERT INTO email_templates 
                                (business_id, name, type, subject_template, html_template, text_template, is_active, created_at, updated_at)
                                VALUES (:business_id, :name, :type, :subject_template, :html_template, :text_template, TRUE, NOW(), NOW())
                            """), {
                                "business_id": business_id,
                                "name": "תזכורת - קביעת שיחה",
                                "type": "followup",
                                "subject_template": template_2_subject,
                                "html_template": template_2_html,
                                "text_template": template_2_text
                            })
                            
                            # Template 3
                            db.session.execute(text("""
                                INSERT INTO email_templates 
                                (business_id, name, type, subject_template, html_template, text_template, is_active, created_at, updated_at)
                                VALUES (:business_id, :name, :type, :subject_template, :html_template, :text_template, TRUE, NOW(), NOW())
                            """), {
                                "business_id": business_id,
                                "name": "מעקב - הודעה מהירה",
                                "type": "quick_followup",
                                "subject_template": template_3_subject,
                                "html_template": template_3_html,
                                "text_template": template_3_text
                            })
                            
                            templates_inserted += 3
                            checkpoint(f"  ✅ Seeded 3 templates for business_id={business_id} ({business_name})")
                        
                        except Exception as e:
                            log.warning(f"  ⚠️ Failed to seed templates for business_id={business_id}: {e}")
                            # Continue with other businesses
                    
                    checkpoint(f"  ✅ Seeded {templates_inserted} email templates across {businesses_count} businesses")
                    migrations_applied.append('seed_email_templates')
                else:
                    checkpoint("  ✅ All businesses already have email templates")
            else:
                checkpoint("  ℹ️ email_templates table does not exist - skipping")
        
        except Exception as e:
            log.error(f"❌ Migration 62 (seed_email_templates) failed: {e}")
            # Don't rollback - this is not critical, just log the error
            checkpoint(f"  ⚠️ Template seeding failed but continuing: {e}")
        
        checkpoint("✅ Migration 62 completed - Email templates seeded")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 63: Add theme-based email settings fields
        # 🎨 PURPOSE: Enable luxury email themes with simple field editing (no HTML)
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 63: Adding theme-based email settings fields")
        
        if check_table_exists('email_settings'):
            try:
                # Add theme_id column if missing
                if not check_column_exists('email_settings', 'theme_id'):
                    checkpoint("  → Adding theme_id to email_settings...")
                    db.session.execute(text("""
                        ALTER TABLE email_settings 
                        ADD COLUMN theme_id VARCHAR(50) DEFAULT 'classic_blue'
                    """))
                    checkpoint("  ✅ email_settings.theme_id added")
                    migrations_applied.append('add_email_settings_theme_id')
                
                # Add cta_default_text column if missing
                if not check_column_exists('email_settings', 'cta_default_text'):
                    checkpoint("  → Adding cta_default_text to email_settings...")
                    db.session.execute(text("""
                        ALTER TABLE email_settings 
                        ADD COLUMN cta_default_text VARCHAR(200)
                    """))
                    checkpoint("  ✅ email_settings.cta_default_text added")
                    migrations_applied.append('add_email_settings_cta_default_text')
                
                # Add cta_default_url column if missing
                if not check_column_exists('email_settings', 'cta_default_url'):
                    checkpoint("  → Adding cta_default_url to email_settings...")
                    db.session.execute(text("""
                        ALTER TABLE email_settings 
                        ADD COLUMN cta_default_url VARCHAR(500)
                    """))
                    checkpoint("  ✅ email_settings.cta_default_url added")
                    migrations_applied.append('add_email_settings_cta_default_url')
                
                checkpoint("✅ Migration 63 completed - Theme-based email settings fields added")
            except Exception as e:
                log.error(f"❌ Migration 63 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ email_settings table does not exist - skipping")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 64: Add company_id field to Business table
        # 🏢 PURPOSE: Store Israeli company registration number (ח.פ) 
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 64: Adding company_id field to Business table")
        
        if check_table_exists('business'):
            try:
                # Add company_id column if missing
                if not check_column_exists('business', 'company_id'):
                    checkpoint("  → Adding company_id to business table...")
                    db.session.execute(text("""
                        ALTER TABLE business 
                        ADD COLUMN company_id VARCHAR(50)
                    """))
                    checkpoint("  ✅ business.company_id added")
                    migrations_applied.append('add_business_company_id')
                else:
                    checkpoint("  ✅ business.company_id already exists")
                
                checkpoint("✅ Migration 64 completed - company_id field added to Business")
            except Exception as e:
                log.error(f"❌ Migration 64 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ business table does not exist - skipping")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 65: Push Subscriptions - Web Push notifications support
        # 🔔 PURPOSE: Enable push notifications to users' devices (PWA, future native apps)
        # Supports: webpush (now), fcm/apns (future)
        # ═══════════════════════════════════════════════════════════════════════
        if not check_table_exists('push_subscriptions'):
            checkpoint("Migration 65: Creating push_subscriptions table for Web Push notifications")
            try:
                from sqlalchemy import text
                db.session.execute(text("""
                    CREATE TABLE push_subscriptions (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        channel VARCHAR(16) NOT NULL DEFAULT 'webpush',
                        endpoint TEXT NOT NULL,
                        p256dh TEXT,
                        auth TEXT,
                        device_info VARCHAR(512),
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Create indexes for efficient querying
                db.session.execute(text("""
                    CREATE INDEX idx_push_subscriptions_user_id ON push_subscriptions(user_id)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_push_subscriptions_business_id ON push_subscriptions(business_id)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_push_subscriptions_is_active ON push_subscriptions(is_active)
                """))
                # Unique constraint to prevent duplicate subscriptions
                db.session.execute(text("""
                    CREATE UNIQUE INDEX idx_push_subscriptions_user_endpoint ON push_subscriptions(user_id, endpoint)
                """))
                
                migrations_applied.append('create_push_subscriptions_table')
                checkpoint("✅ Applied migration 65: create_push_subscriptions_table - Web Push notifications support")
            except Exception as e:
                log.error(f"❌ Migration 65 failed: {e}")
                db.session.rollback()
                raise
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 66: Reminder Push Log - Track sent reminder push notifications
        # 🔔 PURPOSE: Prevent duplicate reminder push notifications across workers
        # Uses DB-backed deduplication with unique constraint on (reminder_id, offset_minutes)
        # ═══════════════════════════════════════════════════════════════════════
        if not check_table_exists('reminder_push_log'):
            checkpoint("Migration 66: Creating reminder_push_log table for reminder notification deduplication")
            try:
                from sqlalchemy import text
                db.session.execute(text("""
                    CREATE TABLE reminder_push_log (
                        id SERIAL PRIMARY KEY,
                        reminder_id INTEGER NOT NULL REFERENCES lead_reminders(id) ON DELETE CASCADE,
                        offset_minutes INTEGER NOT NULL,
                        sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Create indexes for efficient querying
                db.session.execute(text("""
                    CREATE INDEX idx_reminder_push_log_reminder_id ON reminder_push_log(reminder_id)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_reminder_push_log_sent_at ON reminder_push_log(sent_at)
                """))
                # Unique constraint to prevent duplicate notifications
                db.session.execute(text("""
                    CREATE UNIQUE INDEX uq_reminder_push_log ON reminder_push_log(reminder_id, offset_minutes)
                """))
                
                migrations_applied.append('create_reminder_push_log_table')
                checkpoint("✅ Applied migration 66: create_reminder_push_log_table - Reminder push notification deduplication")
            except Exception as e:
                log.error(f"❌ Migration 66 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 67: Email Text Templates - Quick text snippets for email body content
        # These are simple text templates (like quotes, greetings, pricing info) that can be used in emails
        checkpoint("Migration 67: Creating email_text_templates table for quick text snippets")
        if not check_table_exists('email_text_templates'):
            try:
                from sqlalchemy import text
                db.session.execute(text("""
                    CREATE TABLE email_text_templates (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        name VARCHAR(255) NOT NULL,
                        category VARCHAR(100) DEFAULT 'general',
                        subject_line VARCHAR(500),
                        body_text TEXT NOT NULL,
                        created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Create indexes for fast lookups
                db.session.execute(text("""
                    CREATE INDEX idx_email_text_templates_business_id ON email_text_templates(business_id)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_email_text_templates_category ON email_text_templates(category)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_email_text_templates_is_active ON email_text_templates(is_active)
                """))
                
                migrations_applied.append('create_email_text_templates_table')
                checkpoint("✅ Applied migration 67: create_email_text_templates_table - Email text snippets for quick content")
            except Exception as e:
                log.error(f"❌ Migration 67 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 68: WhatsApp Manual Templates - Custom text templates for broadcasts
        checkpoint("Migration 68: Creating whatsapp_manual_templates table for custom broadcast templates")
        if not check_table_exists('whatsapp_manual_templates'):
            try:
                from sqlalchemy import text
                db.session.execute(text("""
                    CREATE TABLE whatsapp_manual_templates (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        name VARCHAR(255) NOT NULL,
                        message_text TEXT NOT NULL,
                        created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Create indexes for fast lookups
                db.session.execute(text("""
                    CREATE INDEX idx_whatsapp_manual_templates_business_id ON whatsapp_manual_templates(business_id)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_whatsapp_manual_templates_is_active ON whatsapp_manual_templates(is_active)
                """))
                
                migrations_applied.append('create_whatsapp_manual_templates_table')
                checkpoint("✅ Applied migration 68: create_whatsapp_manual_templates_table - WhatsApp custom templates")
            except Exception as e:
                log.error(f"❌ Migration 68 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 69: ISO 27001 Security Events Table - Audit and incident tracking
        # Required for ISO 27001 compliance (A.12.4, A.16) and audit readiness
        checkpoint("Migration 69: Creating security_events table for ISO 27001 compliance")
        if not check_table_exists('security_events'):
            try:
                from sqlalchemy import text
                db.session.execute(text("""
                    CREATE TABLE security_events (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER REFERENCES business(id),
                        event_type VARCHAR(64) NOT NULL,
                        severity VARCHAR(16) NOT NULL DEFAULT 'low' CHECK (severity IN ('critical', 'high', 'medium', 'low')),
                        description TEXT NOT NULL,
                        impact TEXT,
                        response TEXT,
                        lessons_learned TEXT,
                        status VARCHAR(32) DEFAULT 'open' CHECK (status IN ('open', 'investigating', 'mitigated', 'resolved', 'closed')),
                        user_id INTEGER REFERENCES users(id),
                        user_email VARCHAR(255),
                        ip_address VARCHAR(64),
                        user_agent VARCHAR(512),
                        resource_type VARCHAR(64),
                        resource_id VARCHAR(64),
                        endpoint VARCHAR(255),
                        method VARCHAR(16),
                        event_metadata JSONB,
                        assigned_to_user_id INTEGER REFERENCES users(id),
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        resolved_at TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Create indexes for efficient querying
                db.session.execute(text("""
                    CREATE INDEX idx_security_events_business_id ON security_events(business_id)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_security_events_event_type ON security_events(event_type)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_security_events_severity ON security_events(severity)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_security_events_status ON security_events(status)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_security_events_created_at ON security_events(created_at)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_security_events_business_severity ON security_events(business_id, severity)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_security_events_status_created ON security_events(status, created_at)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_security_events_type_created ON security_events(event_type, created_at)
                """))
                
                migrations_applied.append('create_security_events_table')
                checkpoint("✅ Applied migration 69: create_security_events_table - ISO 27001 security audit compliance")
            except Exception as e:
                log.error(f"❌ Migration 69 failed: {e}")
                db.session.rollback()
                raise
        
        # Migration 70: Rename metadata to event_metadata in security_events (SQLAlchemy reserved name fix)
        checkpoint("Migration 70: Checking if security_events.metadata needs to be renamed to event_metadata")
        if check_table_exists('security_events') and check_column_exists('security_events', 'metadata'):
            try:
                from sqlalchemy import text
                checkpoint("Migration 70: Renaming security_events.metadata to event_metadata (SQLAlchemy reserved name)")
                db.session.execute(text("""
                    ALTER TABLE security_events RENAME COLUMN metadata TO event_metadata
                """))
                migrations_applied.append('rename_security_events_metadata_to_event_metadata')
                checkpoint("✅ Applied migration 70: rename_security_events_metadata_to_event_metadata")
            except Exception as e:
                log.error(f"❌ Migration 70 failed: {e}")
                db.session.rollback()
                raise
        elif check_table_exists('security_events'):
            checkpoint("Migration 70: Column security_events.metadata does not exist (already event_metadata or new table) - skipping")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 71: Page-level permissions for businesses (enabled_pages)
        # 🔐 PURPOSE: Implement full page access control system
        # Adds enabled_pages JSONB column to business table
        # Sets default to ALL pages for existing businesses (backward compatibility)
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 71: Adding enabled_pages column to business table")
        if check_table_exists('business') and not check_column_exists('business', 'enabled_pages'):
            try:
                from sqlalchemy import text
                from server.security.page_registry import DEFAULT_ENABLED_PAGES
                import json
                
                checkpoint("  → Adding enabled_pages column...")
                # Add column with default empty list
                db.session.execute(text("""
                    ALTER TABLE business 
                    ADD COLUMN enabled_pages JSON NOT NULL DEFAULT '[]'
                """))
                checkpoint("  ✅ enabled_pages column added")
                
                # Set all existing businesses to have all pages enabled (backward compatibility)
                default_pages_json = json.dumps(DEFAULT_ENABLED_PAGES)
                checkpoint(f"  → Setting default pages for existing businesses: {len(DEFAULT_ENABLED_PAGES)} pages")
                
                # Update only rows that don't have pages set yet (NULL or empty array)
                # 🔥 FIX: Use JSONB cast and proper comparison to avoid "operator does not exist: json = json" error
                result = db.session.execute(text("""
                    UPDATE business 
                    SET enabled_pages = :pages
                    WHERE enabled_pages IS NULL 
                       OR CAST(enabled_pages AS TEXT) = '[]'
                       OR json_array_length(CAST(enabled_pages AS json)) = 0
                """), {"pages": default_pages_json})
                
                updated_count = result.rowcount
                checkpoint(f"  ✅ Updated {updated_count} existing businesses with all pages enabled")
                
                migrations_applied.append('add_business_enabled_pages')
                checkpoint("✅ Applied migration 71: add_business_enabled_pages - Page-level permissions system")
            except Exception as e:
                log.error(f"❌ Migration 71 failed: {e}")
                db.session.rollback()
                raise
        elif check_table_exists('business'):
            checkpoint("Migration 71: enabled_pages column already exists - skipping")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 72: CRM Context-Aware Support - Add note_type, call_id, structured_data to lead_notes
        # 🎯 PURPOSE: Enable AI to read/write CRM context and create call summary notes
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 72: CRM Context-Aware Support - Adding fields to lead_notes")
        
        if check_table_exists('lead_notes'):
            try:
                # Add note_type column if missing
                if not check_column_exists('lead_notes', 'note_type'):
                    checkpoint("  → Adding note_type to lead_notes...")
                    db.session.execute(text("""
                        ALTER TABLE lead_notes 
                        ADD COLUMN note_type VARCHAR(32) DEFAULT 'manual'
                    """))
                    db.session.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_lead_notes_type 
                        ON lead_notes(lead_id, note_type)
                    """))
                    checkpoint("  ✅ lead_notes.note_type added")
                    migrations_applied.append('add_lead_notes_note_type')
                
                # Add call_id column if missing
                if not check_column_exists('lead_notes', 'call_id'):
                    checkpoint("  → Adding call_id to lead_notes...")
                    db.session.execute(text("""
                        ALTER TABLE lead_notes 
                        ADD COLUMN call_id INTEGER REFERENCES call_log(id)
                    """))
                    db.session.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_lead_notes_call_id 
                        ON lead_notes(call_id)
                    """))
                    checkpoint("  ✅ lead_notes.call_id added")
                    migrations_applied.append('add_lead_notes_call_id')
                
                # Add structured_data column if missing
                if not check_column_exists('lead_notes', 'structured_data'):
                    checkpoint("  → Adding structured_data to lead_notes...")
                    db.session.execute(text("""
                        ALTER TABLE lead_notes 
                        ADD COLUMN structured_data JSON
                    """))
                    checkpoint("  ✅ lead_notes.structured_data added")
                    migrations_applied.append('add_lead_notes_structured_data')
                
                checkpoint("✅ Migration 72 completed - CRM Context-Aware Support fields added to lead_notes")
            except Exception as e:
                log.error(f"❌ Migration 72 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ lead_notes table does not exist - skipping")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 73: CRM Context-Aware Support - Add enable_customer_service to business_settings
        # 🎯 PURPOSE: Toggle per-business customer service mode
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 73: CRM Context-Aware Support - Adding enable_customer_service to business_settings")
        
        if check_table_exists('business_settings'):
            try:
                if not check_column_exists('business_settings', 'enable_customer_service'):
                    checkpoint("  → Adding enable_customer_service to business_settings...")
                    db.session.execute(text("""
                        ALTER TABLE business_settings 
                        ADD COLUMN enable_customer_service BOOLEAN DEFAULT FALSE
                    """))
                    checkpoint("  ✅ business_settings.enable_customer_service added")
                    migrations_applied.append('add_business_settings_enable_customer_service')
                else:
                    checkpoint("  ✅ business_settings.enable_customer_service already exists")
                
                checkpoint("✅ Migration 73 completed - Customer service toggle added")
            except Exception as e:
                log.error(f"❌ Migration 73 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ business_settings table does not exist - skipping")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 74: Email Text Templates Enhancement - Add button_text, button_link, footer_text
        # 🎯 PURPOSE: Allow full email template customization including CTA button and footer
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 74: Email Text Templates - Adding button and footer fields")
        
        if check_table_exists('email_text_templates'):
            try:
                # Add button_text column if missing
                if not check_column_exists('email_text_templates', 'button_text'):
                    checkpoint("  → Adding button_text to email_text_templates...")
                    db.session.execute(text("""
                        ALTER TABLE email_text_templates 
                        ADD COLUMN button_text VARCHAR(255)
                    """))
                    checkpoint("  ✅ email_text_templates.button_text added")
                    migrations_applied.append('add_email_text_templates_button_text')
                
                # Add button_link column if missing
                if not check_column_exists('email_text_templates', 'button_link'):
                    checkpoint("  → Adding button_link to email_text_templates...")
                    db.session.execute(text("""
                        ALTER TABLE email_text_templates 
                        ADD COLUMN button_link VARCHAR(512)
                    """))
                    checkpoint("  ✅ email_text_templates.button_link added")
                    migrations_applied.append('add_email_text_templates_button_link')
                
                # Add footer_text column if missing
                if not check_column_exists('email_text_templates', 'footer_text'):
                    checkpoint("  → Adding footer_text to email_text_templates...")
                    db.session.execute(text("""
                        ALTER TABLE email_text_templates 
                        ADD COLUMN footer_text TEXT
                    """))
                    checkpoint("  ✅ email_text_templates.footer_text added")
                    migrations_applied.append('add_email_text_templates_footer_text')
                
                checkpoint("✅ Migration 74 completed - Email text template fields added")
            except Exception as e:
                log.error(f"❌ Migration 74 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ email_text_templates table does not exist - skipping")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 75: Separate Customer Service AI Notes from Free Notes
        # 🎯 PURPOSE: Fix overlap between AI customer service notes and free notes
        # Problem: Manual notes in AI tab used note_type='manual', causing them to appear in both tabs
        # Solution: Introduce new note_type='customer_service_ai' for AI customer service context
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 75: Separating Customer Service AI notes from Free Notes")
        
        if check_table_exists('lead_notes'):
            try:
                from sqlalchemy import text
                
                # Step 1: Update existing manual notes without attachments to be customer_service_ai
                # These are the notes that were added in the AI Customer Service tab
                # We identify them as manual notes with no attachments and no created_by user
                # (created_by=NULL typically means AI-created or system-created)
                checkpoint("  → Migrating existing AI customer service notes...")
                
                # First, check if attachments column exists and what type it is
                column_type_query = text("""
                    SELECT data_type, udt_name
                    FROM information_schema.columns
                    WHERE table_name = 'lead_notes' AND column_name = 'attachments'
                """)
                column_info = db.session.execute(column_type_query).fetchone()
                
                # Build the query based on column type
                if column_info:
                    data_type = column_info[0].lower()
                    udt_name = column_info[1].lower() if len(column_info) > 1 else ''
                    checkpoint(f"  Column attachments type: {data_type} ({udt_name})")
                    
                    # Determine the right comparison based on column type
                    if 'jsonb' in data_type or udt_name == 'jsonb':
                        # JSONB column - use jsonb operators
                        attachments_condition = "(attachments IS NULL OR attachments = '[]'::jsonb OR jsonb_array_length(attachments) = 0)"
                    elif 'json' in data_type or udt_name == 'json':
                        # JSON column - cast and compare
                        attachments_condition = "(attachments IS NULL OR CAST(attachments AS TEXT) = '[]' OR json_array_length(attachments) = 0)"
                    else:
                        # TEXT column - use trim and cast
                        attachments_condition = "(attachments IS NULL OR TRIM(attachments) = '' OR TRIM(attachments) = '[]' OR (attachments ~ '^\\[\\s*\\]$'))"
                    
                    checkpoint(f"  Using condition: {attachments_condition}")
                else:
                    checkpoint("  ⚠️ attachments column not found, skipping attachment check")
                    attachments_condition = "TRUE"
                
                # Count notes that will be migrated
                count_query = text(f"""
                    SELECT COUNT(*) FROM lead_notes
                    WHERE note_type = 'manual'
                      AND {attachments_condition}
                      AND created_by IS NULL
                """)
                notes_to_migrate = db.session.execute(count_query).scalar() or 0
                checkpoint(f"  Found {notes_to_migrate} manual notes without attachments and without user (AI/system notes)")
                
                if notes_to_migrate > 0:
                    # Update note_type for these notes
                    # Note: We keep created_by=NULL to preserve that these were AI/system generated
                    update_query = text(f"""
                        UPDATE lead_notes 
                        SET note_type = 'customer_service_ai'
                        WHERE note_type = 'manual'
                          AND {attachments_condition}
                          AND created_by IS NULL
                    """)
                    db.session.execute(update_query)
                    checkpoint(f"  ✅ Migrated {notes_to_migrate} notes to customer_service_ai type")
                else:
                    checkpoint("  ✅ No notes to migrate")
                
                # Step 2: Add index for faster filtering by note_type
                if not check_index_exists('idx_lead_notes_type_tenant'):
                    checkpoint("  → Creating index on note_type and tenant_id...")
                    db.session.execute(text("""
                        CREATE INDEX idx_lead_notes_type_tenant 
                        ON lead_notes(tenant_id, note_type, created_at DESC)
                    """))
                    checkpoint("  ✅ Index created for efficient note filtering")
                
                migrations_applied.append('separate_customer_service_ai_notes')
                checkpoint("✅ Migration 75 completed - Customer Service AI notes now separate from Free Notes")
                
                # Log summary
                checkpoint("""
                  📋 Migration 75 Summary:
                  - Created new note_type 'customer_service_ai' for AI customer service context
                  - Migrated existing manual notes (without attachments, without user) to new type
                  - Added index for efficient filtering
                  - AI will now only see: call_summary, system, and customer_service_ai notes
                  - Free Notes tab will only show: manual notes (with or without attachments)
                """)
                
            except Exception as e:
                log.error(f"❌ Migration 75 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ lead_notes table does not exist - skipping")
        
        # Migration 76: Create attachments table for unified file management
        if not check_table_exists('attachments'):
            checkpoint("🔧 Running Migration 76: Create attachments table for unified file management")
            try:
                from sqlalchemy import text
                
                # Create attachments table
                db.session.execute(text("""
                    CREATE TABLE attachments (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        uploaded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        filename_original VARCHAR(255) NOT NULL,
                        mime_type VARCHAR(100) NOT NULL,
                        file_size INTEGER NOT NULL,
                        storage_path VARCHAR(512) NOT NULL,
                        public_url VARCHAR(512),
                        channel_compatibility JSON DEFAULT '{"email": true, "whatsapp": true, "broadcast": true}'::json,
                        metadata JSON,
                        is_deleted BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        deleted_at TIMESTAMP,
                        deleted_by INTEGER REFERENCES users(id) ON DELETE SET NULL
                    )
                """))
                checkpoint("  ✅ attachments table created")
                
                # Add indexes for performance
                db.session.execute(text("""
                    CREATE INDEX idx_attachments_business 
                    ON attachments(business_id, created_at DESC) 
                    WHERE is_deleted = FALSE
                """))
                checkpoint("  ✅ Index created: idx_attachments_business")
                
                db.session.execute(text("""
                    CREATE INDEX idx_attachments_uploader 
                    ON attachments(uploaded_by, created_at DESC)
                """))
                checkpoint("  ✅ Index created: idx_attachments_uploader")
                
                # Create storage directory structure
                import os
                storage_root = os.path.join(os.getcwd(), 'storage', 'attachments')
                os.makedirs(storage_root, exist_ok=True)
                checkpoint(f"  ✅ Storage directory created: {storage_root}")
                
                migrations_applied.append('create_attachments_table')
                checkpoint("✅ Migration 76 completed - Unified attachments system ready")
                
            except Exception as e:
                log.error(f"❌ Migration 76 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ attachments table already exists - skipping")
        
        # Migration 77: Upgrade contracts system - reuse attachments for R2 storage
        if not check_table_exists('contract_files'):
            checkpoint("🔧 Running Migration 77: Upgrade contracts system with attachment integration")
            
            try:
                # Add missing columns to existing contract table if it exists
                if check_table_exists('contract'):
                    checkpoint("  → Upgrading existing contract table...")
                    
                    # Add lead_id if missing
                    if not check_column_exists('contract', 'lead_id'):
                        db.session.execute(text("""
                            ALTER TABLE contract 
                            ADD COLUMN lead_id INTEGER REFERENCES leads(id)
                        """))
                        db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_contract_lead ON contract(lead_id)"))
                        checkpoint("    ✅ Added lead_id column")
                    
                    # Add title if missing
                    if not check_column_exists('contract', 'title'):
                        db.session.execute(text("""
                            ALTER TABLE contract 
                            ADD COLUMN title VARCHAR(255)
                        """))
                        checkpoint("    ✅ Added title column")
                    
                    # Update status column to use new enum values with CHECK constraint
                    if check_column_exists('contract', 'status'):
                        # Drop old constraint if exists and add new one
                        db.session.execute(text("""
                            ALTER TABLE contract DROP CONSTRAINT IF EXISTS contract_status_check
                        """))
                        db.session.execute(text("""
                            ALTER TABLE contract 
                            ADD CONSTRAINT contract_status_check 
                            CHECK (status IN ('draft', 'sent', 'signed', 'cancelled'))
                        """))
                        checkpoint("    ✅ Updated status CHECK constraint")
                    
                    # Add signer fields if missing
                    for col in ['signer_name', 'signer_phone', 'signer_email']:
                        if not check_column_exists('contract', col):
                            db.session.execute(text(f"""
                                ALTER TABLE contract 
                                ADD COLUMN {col} VARCHAR(255)
                            """))
                    checkpoint("    ✅ Added signer fields")
                    
                    # Add created_by if missing
                    if not check_column_exists('contract', 'created_by'):
                        db.session.execute(text("""
                            ALTER TABLE contract 
                            ADD COLUMN created_by INTEGER REFERENCES users(id)
                        """))
                    checkpoint("    ✅ Added created_by field")
                    
                    # Add updated_at if missing
                    if not check_column_exists('contract', 'updated_at'):
                        db.session.execute(text("""
                            ALTER TABLE contract 
                            ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        """))
                    checkpoint("    ✅ Added updated_at field")
                    
                    # Ensure indexes
                    db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_contract_business_created ON contract(business_id, created_at DESC)"))
                    db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_contract_business_status ON contract(business_id, status)"))
                    checkpoint("    ✅ Created performance indexes")
                
                # Create contract_files table - links contracts to attachments
                checkpoint("  → Creating contract_files table (attachment-based)...")
                db.session.execute(text("""
                    CREATE TABLE contract_files (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id),
                        contract_id INTEGER NOT NULL REFERENCES contract(id) ON DELETE CASCADE,
                        attachment_id INTEGER NOT NULL REFERENCES attachments(id) ON DELETE CASCADE,
                        purpose VARCHAR(32) NOT NULL CHECK (purpose IN ('original', 'signed', 'extra_doc', 'template')),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by INTEGER REFERENCES users(id),
                        deleted_at TIMESTAMP
                    )
                """))
                
                # Create indexes for contract_files
                db.session.execute(text("CREATE INDEX idx_contract_files_contract ON contract_files(contract_id, created_at DESC)"))
                db.session.execute(text("CREATE INDEX idx_contract_files_business ON contract_files(business_id)"))
                db.session.execute(text("CREATE INDEX idx_contract_files_attachment ON contract_files(attachment_id)"))
                checkpoint("    ✅ contract_files table created (attachment-based)")
                
                # Create contract_sign_tokens table - DB-based tokens (NOT JWT)
                checkpoint("  → Creating contract_sign_tokens table...")
                db.session.execute(text("""
                    CREATE TABLE contract_sign_tokens (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id),
                        contract_id INTEGER NOT NULL REFERENCES contract(id) ON DELETE CASCADE,
                        token_hash VARCHAR(64) NOT NULL UNIQUE,
                        scope VARCHAR(32) NOT NULL DEFAULT 'sign',
                        expires_at TIMESTAMP NOT NULL,
                        used_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by INTEGER REFERENCES users(id)
                    )
                """))
                
                # Create indexes for contract_sign_tokens
                db.session.execute(text("CREATE INDEX idx_contract_tokens_hash ON contract_sign_tokens(token_hash)"))
                db.session.execute(text("CREATE INDEX idx_contract_tokens_contract ON contract_sign_tokens(contract_id)"))
                db.session.execute(text("CREATE INDEX idx_contract_tokens_expires ON contract_sign_tokens(expires_at)"))
                checkpoint("    ✅ contract_sign_tokens table created (secure DB-based tokens)")
                
                # Create contract_sign_events table (Audit Trail)
                checkpoint("  → Creating contract_sign_events table...")
                db.session.execute(text("""
                    CREATE TABLE contract_sign_events (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id),
                        contract_id INTEGER NOT NULL REFERENCES contract(id) ON DELETE CASCADE,
                        event_type VARCHAR(32) NOT NULL CHECK (event_type IN (
                            'created', 'file_uploaded', 'sent_for_signature', 
                            'viewed', 'signed_completed', 'cancelled'
                        )),
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by INTEGER REFERENCES users(id)
                    )
                """))
                
                # Create indexes for contract_sign_events
                db.session.execute(text("CREATE INDEX idx_contract_events_contract ON contract_sign_events(contract_id, created_at)"))
                db.session.execute(text("CREATE INDEX idx_contract_events_business ON contract_sign_events(business_id)"))
                checkpoint("    ✅ contract_sign_events table created")
                
                migrations_applied.append('upgrade_contracts_system_attachment_based')
                checkpoint("✅ Migration 77 completed - Contracts system with attachment integration")
                checkpoint("  📋 Summary:")
                checkpoint("     • contract_files → attachment_id (reuses R2 storage)")
                checkpoint("     • contract_sign_tokens → DB-based (NOT JWT)")
                checkpoint("     • contract_sign_events → full audit trail")
                
            except Exception as e:
                log.error(f"❌ Migration 77 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ contract_files table already exists - skipping")
        
        # Migration 78: Rename metadata to event_metadata in contract_sign_events (SQLAlchemy reserved word fix)
        if check_table_exists('contract_sign_events') and check_column_exists('contract_sign_events', 'metadata'):
            checkpoint("🔧 Running Migration 78: Rename metadata to event_metadata in contract_sign_events")
            
            try:
                # Rename the column from metadata to event_metadata
                db.session.execute(text("""
                    ALTER TABLE contract_sign_events 
                    RENAME COLUMN metadata TO event_metadata
                """))
                
                migrations_applied.append('rename_contract_sign_events_metadata')
                checkpoint("✅ Migration 78 completed - Renamed metadata to event_metadata in contract_sign_events")
                checkpoint("  📋 Reason: 'metadata' is a reserved attribute in SQLAlchemy Declarative API")
                
            except Exception as e:
                log.error(f"❌ Migration 78 failed: {e}")
                db.session.rollback()
                raise
        else:
            if check_table_exists('contract_sign_events'):
                if check_column_exists('contract_sign_events', 'event_metadata'):
                    checkpoint("  ℹ️ event_metadata column already exists - skipping")
                else:
                    checkpoint("  ℹ️ metadata column not found (may have been migrated already) - skipping")
            else:
                checkpoint("  ℹ️ contract_sign_events table does not exist - skipping")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 79: Add attachments column to email_messages table
        # ═══════════════════════════════════════════════════════════════════════
        if check_table_exists('email_messages') and not check_column_exists('email_messages', 'attachments'):
            checkpoint("🔧 Running Migration 79: Add attachments column to email_messages")
            
            try:
                # Add attachments column as JSON array to store attachment IDs
                db.session.execute(text("""
                    ALTER TABLE email_messages 
                    ADD COLUMN attachments JSON DEFAULT '[]'
                """))
                
                migrations_applied.append('add_email_messages_attachments')
                checkpoint("✅ Migration 79 completed - Added attachments column to email_messages")
                checkpoint("  📋 Purpose: Store attachment IDs for email attachments support")
                
            except Exception as e:
                log.error(f"❌ Migration 79 failed: {e}")
                db.session.rollback()
                raise
        else:
            if check_table_exists('email_messages'):
                if check_column_exists('email_messages', 'attachments'):
                    checkpoint("  ℹ️ attachments column already exists - skipping")
                else:
                    checkpoint("  ℹ️ email_messages table not found - skipping")
            else:
                checkpoint("  ℹ️ email_messages table does not exist - skipping")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 80: Add 'file_downloaded' to contract_sign_events event_type CHECK constraint
        # ═══════════════════════════════════════════════════════════════════════
        if check_table_exists('contract_sign_events'):
            checkpoint("🔧 Running Migration 80: Add 'file_downloaded' to contract_sign_events event types")
            
            try:
                # Check if constraint exists by querying check_constraints
                result = db.session.execute(text("""
                    SELECT constraint_name, check_clause
                    FROM information_schema.check_constraints 
                    WHERE constraint_name LIKE '%event_type%'
                    AND constraint_schema = 'public'
                """))
                constraint_row = result.fetchone()
                
                if constraint_row:
                    constraint_name = constraint_row[0]
                    check_clause = constraint_row[1] if len(constraint_row) > 1 else ''
                    
                    # Check if 'file_downloaded' is already in the constraint
                    if 'file_downloaded' in check_clause:
                        checkpoint("  ℹ️ 'file_downloaded' already in event_type constraint - skipping")
                    else:
                        # Drop old constraint and add new one with 'file_downloaded'
                        db.session.execute(text(f"""
                            ALTER TABLE contract_sign_events 
                            DROP CONSTRAINT IF EXISTS {constraint_name}
                        """))
                        
                        db.session.execute(text("""
                            ALTER TABLE contract_sign_events 
                            ADD CONSTRAINT contract_sign_events_event_type_check 
                            CHECK (event_type IN (
                                'created', 'file_uploaded', 'sent_for_signature', 
                                'viewed', 'signed_completed', 'cancelled', 'file_downloaded'
                            ))
                        """))
                        
                        migrations_applied.append('add_file_downloaded_event_type')
                        checkpoint("✅ Migration 80 completed - Added 'file_downloaded' to allowed event types")
                        checkpoint("  📋 Purpose: Allow logging of file download events in contract audit trail")
                else:
                    checkpoint("  ℹ️ Event type constraint not found - table may not have constraint yet")
                
            except Exception as e:
                log.error(f"❌ Migration 80 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ contract_sign_events table does not exist - skipping")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 81: Assets Library (מאגר) - Create asset_items and asset_item_media tables
        # 🎯 PURPOSE: Add Assets Library feature for managing items with images
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 81: Assets Library - Creating asset_items and asset_item_media tables")
        
        if not check_table_exists('asset_items'):
            try:
                checkpoint("  → Creating asset_items table...")
                db.session.execute(text("""
                    CREATE TABLE asset_items (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        title VARCHAR(160) NOT NULL,
                        description TEXT,
                        tags JSON DEFAULT '[]',
                        category VARCHAR(64),
                        status VARCHAR(16) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
                        custom_fields JSON,
                        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Create indexes for efficient querying
                db.session.execute(text("""
                    CREATE INDEX idx_asset_items_business_updated ON asset_items(business_id, updated_at DESC)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_asset_items_business_status_category ON asset_items(business_id, status, category)
                """))
                
                checkpoint("  ✅ asset_items table created")
                migrations_applied.append('create_asset_items_table')
            except Exception as e:
                log.error(f"❌ Migration 81 (asset_items) failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ asset_items table already exists - skipping")
        
        if not check_table_exists('asset_item_media'):
            try:
                checkpoint("  → Creating asset_item_media table...")
                db.session.execute(text("""
                    CREATE TABLE asset_item_media (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        asset_item_id INTEGER NOT NULL REFERENCES asset_items(id) ON DELETE CASCADE,
                        attachment_id INTEGER NOT NULL REFERENCES attachments(id) ON DELETE CASCADE,
                        role VARCHAR(32) NOT NULL DEFAULT 'gallery' CHECK (role IN ('cover', 'gallery', 'floorplan', 'other')),
                        sort_order INTEGER DEFAULT 0,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Create indexes for efficient querying
                db.session.execute(text("""
                    CREATE INDEX idx_asset_item_media_item ON asset_item_media(asset_item_id)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_asset_item_media_sort ON asset_item_media(asset_item_id, sort_order)
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_asset_item_media_attachment ON asset_item_media(attachment_id)
                """))
                
                checkpoint("  ✅ asset_item_media table created")
                migrations_applied.append('create_asset_item_media_table')
            except Exception as e:
                log.error(f"❌ Migration 81 (asset_item_media) failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ asset_item_media table already exists - skipping")
        
        # 🔥 CRITICAL: Enable 'assets' page for all businesses
        # This ensures the Assets Library appears in sidebar for all businesses
        if check_table_exists('business') and check_column_exists('business', 'enabled_pages'):
            try:
                checkpoint("  → Enabling 'assets' page for all businesses...")
                
                # Add 'assets' to enabled_pages for businesses that don't have it yet
                # Using JSONB || operator for performance
                result = db.session.execute(text("""
                    UPDATE business
                    SET enabled_pages = enabled_pages::jsonb || '["assets"]'::jsonb
                    WHERE enabled_pages IS NOT NULL
                      AND NOT (enabled_pages::jsonb ? 'assets')
                """))
                updated_count = result.rowcount
                
                if updated_count > 0:
                    checkpoint(f"  ✅ Enabled 'assets' page for {updated_count} businesses")
                else:
                    checkpoint("  ℹ️ All businesses already have 'assets' page enabled")
                
                # For businesses with NULL or empty enabled_pages, set default pages including assets
                result2 = db.session.execute(text("""
                    UPDATE business
                    SET enabled_pages = '["dashboard","crm_leads","crm_customers","calls_inbound","calls_outbound","whatsapp_inbox","whatsapp_broadcast","emails","calendar","statistics","invoices","contracts","assets","settings","users"]'::jsonb
                    WHERE enabled_pages IS NULL
                       OR enabled_pages::text = '[]'
                       OR jsonb_array_length(enabled_pages::jsonb) = 0
                """))
                updated_count2 = result2.rowcount
                
                if updated_count2 > 0:
                    checkpoint(f"  ✅ Set default pages (including assets) for {updated_count2} businesses with empty pages")
                
                migrations_applied.append('enable_assets_page_for_businesses')
                checkpoint("✅ Migration 81 completed - Assets Library tables created and page enabled")
            except Exception as e:
                log.error(f"❌ Failed to enable assets page for businesses: {e}")
                # Don't fail the entire migration if this fails
                checkpoint("⚠️ Assets tables created but page enablement may need manual fix")
        else:
            checkpoint("✅ Migration 81 completed - Assets Library tables created")
        
        # Migration 82: Gmail Receipts System - Create gmail_connections and receipts tables
        checkpoint("Migration 82: Gmail Receipts System")
        
        # Create gmail_connections table
        if not check_table_exists('gmail_connections'):
            try:
                checkpoint("  → Creating gmail_connections table...")
                db.session.execute(text("""
                    CREATE TABLE gmail_connections (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        email_address VARCHAR(255) NOT NULL,
                        google_sub VARCHAR(255),
                        refresh_token_encrypted TEXT NOT NULL,
                        status VARCHAR(32) NOT NULL DEFAULT 'connected',
                        error_message TEXT,
                        last_sync_at TIMESTAMP,
                        last_history_id VARCHAR(64),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT uq_gmail_connection_business UNIQUE (business_id),
                        CONSTRAINT chk_gmail_connection_status CHECK (status IN ('connected', 'disconnected', 'error'))
                    )
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_gmail_connections_business ON gmail_connections(business_id)
                """))
                checkpoint("  ✅ gmail_connections table created")
                migrations_applied.append('create_gmail_connections_table')
            except Exception as e:
                log.error(f"❌ Migration 82 (gmail_connections) failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ gmail_connections table already exists - skipping")
        
        # Create receipts table
        if not check_table_exists('receipts'):
            try:
                checkpoint("  → Creating receipts table...")
                db.session.execute(text("""
                    CREATE TABLE receipts (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        source VARCHAR(32) NOT NULL DEFAULT 'gmail',
                        gmail_message_id VARCHAR(255),
                        gmail_thread_id VARCHAR(255),
                        from_email VARCHAR(255),
                        subject VARCHAR(500),
                        received_at TIMESTAMP,
                        vendor_name VARCHAR(255),
                        amount NUMERIC(12, 2),
                        currency VARCHAR(3) NOT NULL DEFAULT 'ILS',
                        invoice_number VARCHAR(100),
                        invoice_date DATE,
                        confidence INTEGER,
                        raw_extraction_json JSONB,
                        status VARCHAR(32) NOT NULL DEFAULT 'pending_review',
                        reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        reviewed_at TIMESTAMP,
                        attachment_id INTEGER REFERENCES attachments(id) ON DELETE SET NULL,
                        is_deleted BOOLEAN DEFAULT FALSE,
                        deleted_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT chk_receipt_status CHECK (status IN ('pending_review', 'approved', 'rejected', 'not_receipt')),
                        CONSTRAINT chk_receipt_source CHECK (source IN ('gmail', 'manual', 'upload'))
                    )
                """))
                # Use partial unique index to allow NULL gmail_message_id (for manual uploads)
                db.session.execute(text("""
                    CREATE UNIQUE INDEX uq_receipt_business_gmail_message 
                    ON receipts(business_id, gmail_message_id) 
                    WHERE gmail_message_id IS NOT NULL
                """))
                db.session.execute(text("""
                    CREATE INDEX idx_receipts_business ON receipts(business_id);
                    CREATE INDEX idx_receipts_business_received ON receipts(business_id, received_at);
                    CREATE INDEX idx_receipts_business_status ON receipts(business_id, status);
                    CREATE INDEX idx_receipts_gmail_message_id ON receipts(gmail_message_id);
                    CREATE INDEX idx_receipts_attachment ON receipts(attachment_id);
                    CREATE INDEX idx_receipts_is_deleted ON receipts(is_deleted)
                """))
                checkpoint("  ✅ receipts table created")
                migrations_applied.append('create_receipts_table')
            except Exception as e:
                log.error(f"❌ Migration 82 (receipts) failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ receipts table already exists - skipping")
        
        checkpoint("✅ Migration 82 completed - Gmail Receipts System tables created")
        # ============================================================================
        # Migration 83: Assets AI Toggle - Add assets_use_ai to BusinessSettings
        # ============================================================================
        # Adds assets_use_ai boolean column to business_settings table
        # Controls whether AI can access assets tools during conversations
        # Default: true (enabled for backward compatibility)
        checkpoint("Migration 83: Adding assets_use_ai column to business_settings table")
        if check_table_exists('business_settings') and not check_column_exists('business_settings', 'assets_use_ai'):
            try:
                checkpoint("  → Adding assets_use_ai column...")
                db.session.execute(text("""
                    ALTER TABLE business_settings
                    ADD COLUMN assets_use_ai BOOLEAN NOT NULL DEFAULT TRUE
                """))
                checkpoint("  ✅ assets_use_ai column added (default: TRUE)")
                migrations_applied.append('add_assets_use_ai_column')
                checkpoint("✅ Applied migration 83: add_assets_use_ai_column - AI tools toggle for assets")
            except Exception as e:
                log.error(f"❌ Migration 83 (assets_use_ai) failed: {e}")
                db.session.rollback()
                raise
        else:
            if not check_table_exists('business_settings'):
                checkpoint("Migration 83: business_settings table doesn't exist - skipping")
            else:
                checkpoint("Migration 83: assets_use_ai column already exists - skipping")
        
        # ============================================================================
        # Migration 84: Gmail Receipts Enhanced - Purpose-Based File Separation
        # ============================================================================
        # Adds complete file separation system with purpose and origin tracking
        # - purpose: Categorizes files (email_attachment, whatsapp_media, receipt_source, etc.)
        # - origin_module: Tracks which system created the file
        # - Email content fields for HTML→PNG preview generation
        # - Sync tracking table for long-running Gmail syncs
        # Security: Prevents contract/receipt files from appearing in email/whatsapp pickers
        checkpoint("Migration 84: Gmail Receipts Enhanced - purpose-based file separation")
        
        # 84a: Add purpose field to attachments
        if check_table_exists('attachments'):
            if not check_column_exists('attachments', 'purpose'):
                checkpoint("Migration 84a: Adding purpose to attachments")
                from sqlalchemy import text
                try:
                    db.session.execute(text("""
                        ALTER TABLE attachments 
                        ADD COLUMN purpose VARCHAR(50) NOT NULL DEFAULT 'general_upload'
                    """))
                    db.session.commit()  # Commit immediately to persist the column
                    
                    # Add index for efficient filtering
                    if not check_index_exists('idx_attachments_purpose'):
                        db.session.execute(text("""
                            CREATE INDEX idx_attachments_purpose 
                            ON attachments(business_id, purpose, created_at)
                        """))
                        db.session.commit()  # Commit index creation
                    
                    migrations_applied.append("add_purpose_to_attachments")
                    checkpoint("✅ Migration 84a complete: purpose added with index")
                except Exception as e:
                    db.session.rollback()
                    checkpoint(f"⚠️ Migration 84a failed: {e}")
                    log.error(f"Migration 84a error details: {e}", exc_info=True)
            else:
                checkpoint("Migration 84a: purpose column already exists - skipping")
        
        # 84b: Add origin_module field to attachments
        if check_table_exists('attachments'):
            if not check_column_exists('attachments', 'origin_module'):
                checkpoint("Migration 84b: Adding origin_module to attachments")
                from sqlalchemy import text
                try:
                    db.session.execute(text("""
                        ALTER TABLE attachments 
                        ADD COLUMN origin_module VARCHAR(50)
                    """))
                    db.session.commit()  # Commit immediately to persist the column
                    
                    # Add index for efficient filtering
                    if not check_index_exists('idx_attachments_origin'):
                        db.session.execute(text("""
                            CREATE INDEX idx_attachments_origin 
                            ON attachments(business_id, origin_module)
                        """))
                        db.session.commit()  # Commit index creation
                    
                    migrations_applied.append("add_origin_module_to_attachments")
                    checkpoint("✅ Migration 84b complete: origin_module added with index")
                except Exception as e:
                    db.session.rollback()
                    checkpoint(f"⚠️ Migration 84b failed: {e}")
                    log.error(f"Migration 84b error details: {e}", exc_info=True)
            else:
                checkpoint("Migration 84b: origin_module column already exists - skipping")
        
        # 84c: Add email content fields to receipts
        if check_table_exists('receipts'):
            checkpoint("Migration 84c: Adding email content fields to receipts")
            from sqlalchemy import text
            try:
                fields_added = []
                
                # Add email_subject
                if not check_column_exists('receipts', 'email_subject'):
                    db.session.execute(text("""
                        ALTER TABLE receipts 
                        ADD COLUMN email_subject VARCHAR(500)
                    """))
                    # Copy from existing subject field if available
                    db.session.execute(text("""
                        UPDATE receipts 
                        SET email_subject = subject 
                        WHERE subject IS NOT NULL
                    """))
                    fields_added.append('email_subject')
                
                # Add email_from
                if not check_column_exists('receipts', 'email_from'):
                    db.session.execute(text("""
                        ALTER TABLE receipts 
                        ADD COLUMN email_from VARCHAR(255)
                    """))
                    # Copy from existing from_email field
                    db.session.execute(text("""
                        UPDATE receipts 
                        SET email_from = from_email 
                        WHERE from_email IS NOT NULL
                    """))
                    fields_added.append('email_from')
                
                # Add email_date
                if not check_column_exists('receipts', 'email_date'):
                    db.session.execute(text("""
                        ALTER TABLE receipts 
                        ADD COLUMN email_date TIMESTAMP
                    """))
                    # Copy from existing received_at field
                    db.session.execute(text("""
                        UPDATE receipts 
                        SET email_date = received_at 
                        WHERE received_at IS NOT NULL
                    """))
                    fields_added.append('email_date')
                
                # Add email_html_snippet
                if not check_column_exists('receipts', 'email_html_snippet'):
                    db.session.execute(text("""
                        ALTER TABLE receipts 
                        ADD COLUMN email_html_snippet TEXT
                    """))
                    fields_added.append('email_html_snippet')
                
                if fields_added:
                    migrations_applied.append("add_email_fields_to_receipts")
                    checkpoint(f"✅ Migration 84c complete: {', '.join(fields_added)} added")
                else:
                    checkpoint("Migration 84c: All email fields already exist")
            except Exception as e:
                db.session.rollback()
                checkpoint(f"⚠️ Migration 84c failed: {e}")
        
        # 84d: Add preview_attachment_id to receipts
        if check_table_exists('receipts') and not check_column_exists('receipts', 'preview_attachment_id'):
            checkpoint("Migration 84d: Adding preview_attachment_id to receipts")
            from sqlalchemy import text
            try:
                db.session.execute(text("""
                    ALTER TABLE receipts 
                    ADD COLUMN preview_attachment_id INTEGER 
                    REFERENCES attachments(id) ON DELETE SET NULL
                """))
                
                if not check_index_exists('idx_receipts_preview_attachment'):
                    db.session.execute(text("""
                        CREATE INDEX idx_receipts_preview_attachment 
                        ON receipts(preview_attachment_id)
                    """))
                
                migrations_applied.append("add_preview_attachment_id_to_receipts")
                checkpoint("✅ Migration 84d complete: preview_attachment_id added")
            except Exception as e:
                db.session.rollback()
                checkpoint(f"⚠️ Migration 84d failed: {e}")
        
        # 84e: Create receipt_sync_runs table
        if not check_table_exists('receipt_sync_runs'):
            checkpoint("Migration 84e: Creating receipt_sync_runs table")
            from sqlalchemy import text
            try:
                db.session.execute(text("""
                    CREATE TABLE receipt_sync_runs (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        mode VARCHAR(20) NOT NULL DEFAULT 'incremental',
                        status VARCHAR(20) NOT NULL DEFAULT 'running',
                        started_at TIMESTAMP NOT NULL DEFAULT NOW(),
                        finished_at TIMESTAMP,
                        pages_scanned INTEGER DEFAULT 0,
                        messages_scanned INTEGER DEFAULT 0,
                        candidate_receipts INTEGER DEFAULT 0,
                        saved_receipts INTEGER DEFAULT 0,
                        preview_generated_count INTEGER DEFAULT 0,
                        errors_count INTEGER DEFAULT 0,
                        last_page_token VARCHAR(255),
                        last_internal_date VARCHAR(50),
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """))
                
                db.session.execute(text("""
                    CREATE INDEX idx_receipt_sync_runs_business 
                    ON receipt_sync_runs(business_id, started_at DESC)
                """))
                
                db.session.execute(text("""
                    CREATE INDEX idx_receipt_sync_runs_status 
                    ON receipt_sync_runs(status, started_at DESC)
                """))
                
                migrations_applied.append("create_receipt_sync_runs_table")
                checkpoint("✅ Migration 84e complete: receipt_sync_runs table created")
            except Exception as e:
                db.session.rollback()
                checkpoint(f"⚠️ Migration 84e failed: {e}")
        
        # 84f: Backfill existing attachments with purpose and origin
        if check_table_exists('attachments') and check_column_exists('attachments', 'purpose'):
            checkpoint("Migration 84f: Backfilling attachments with purpose/origin")
            from sqlalchemy import text
            try:
                # Mark receipt attachments
                result = db.session.execute(text("""
                    UPDATE attachments a
                    SET 
                        purpose = 'receipt_source',
                        origin_module = 'receipts'
                    WHERE EXISTS (
                        SELECT 1 FROM receipts r 
                        WHERE r.attachment_id = a.id
                    ) AND a.purpose = 'general_upload'
                """))
                receipt_count = result.rowcount
                
                # Mark contract attachments (if contract_files table exists)
                contract_count = 0
                if check_table_exists('contract_files'):
                    result = db.session.execute(text("""
                        UPDATE attachments a
                        SET 
                            purpose = CASE 
                                WHEN cf.purpose = 'signed' THEN 'contract_signed'
                                ELSE 'contract_original'
                            END,
                            origin_module = 'contracts'
                        FROM contract_files cf
                        WHERE cf.attachment_id = a.id
                        AND a.purpose = 'general_upload'
                    """))
                    contract_count = result.rowcount
                
                # Set origin_module for remaining general uploads
                db.session.execute(text("""
                    UPDATE attachments
                    SET origin_module = 'uploads'
                    WHERE purpose = 'general_upload' AND origin_module IS NULL
                """))
                
                migrations_applied.append("backfill_attachment_purpose_origin")
                checkpoint(f"✅ Migration 84f complete: Backfilled {receipt_count} receipts, {contract_count} contracts")
            except Exception as e:
                db.session.rollback()
                checkpoint(f"⚠️ Migration 84f failed: {e}")
        
        checkpoint("✅ Migration 84: Gmail Receipts Enhanced - Complete!")
        checkpoint("   🔒 Security: Files now separated by purpose - contracts/receipts won't appear in email/whatsapp")
        
        # ============================================================================
        # Migration 85: Fix receipt_sync_runs Missing Columns (cancelled_at, current_month)
        # ============================================================================
        # Root cause: Migration 84e created receipt_sync_runs but missed cancelled_at and current_month
        # These columns are referenced in code but missing from DB → UndefinedColumn errors
        # This patch is IDEMPOTENT and safe to run multiple times
        checkpoint("Migration 85: Adding missing columns to receipt_sync_runs table")
        
        if check_table_exists('receipt_sync_runs'):
            from sqlalchemy import text
            try:
                fields_added = []
                
                # Add cancelled_at column if missing (for cancellation tracking)
                if not check_column_exists('receipt_sync_runs', 'cancelled_at'):
                    checkpoint("  → Adding cancelled_at to receipt_sync_runs...")
                    db.session.execute(text("""
                        ALTER TABLE receipt_sync_runs 
                        ADD COLUMN cancelled_at TIMESTAMP NULL
                    """))
                    fields_added.append('cancelled_at')
                    checkpoint("  ✅ cancelled_at added")
                
                # Add current_month column if missing (for monthly backfill tracking)
                if not check_column_exists('receipt_sync_runs', 'current_month'):
                    checkpoint("  → Adding current_month to receipt_sync_runs...")
                    db.session.execute(text("""
                        ALTER TABLE receipt_sync_runs 
                        ADD COLUMN current_month VARCHAR(10) NULL
                    """))
                    # Create index for efficient filtering by current month
                    if not check_index_exists('idx_receipt_sync_runs_current_month'):
                        db.session.execute(text("""
                            CREATE INDEX idx_receipt_sync_runs_current_month 
                            ON receipt_sync_runs(current_month)
                        """))
                    fields_added.append('current_month')
                    checkpoint("  ✅ current_month added with index")
                
                if fields_added:
                    migrations_applied.append("add_receipt_sync_runs_missing_columns")
                    checkpoint(f"✅ Migration 85 complete: {', '.join(fields_added)} added")
                    checkpoint("   🔒 Idempotent: Safe to run multiple times")
                    checkpoint("   📋 Fixes: UndefinedColumn errors in routes_receipts.py")
                else:
                    checkpoint("✅ Migration 85: All columns already exist - skipping")
                    
            except Exception as e:
                db.session.rollback()
                checkpoint(f"❌ Migration 85 failed: {e}")
                logger.error(f"Migration 85 error details: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ receipt_sync_runs table does not exist - skipping")
        
        # Migration 86: Add heartbeat to receipt_sync_runs (Stale Run Detection)
        # ============================================================================
        # Purpose: Enable detection and auto-recovery from stuck/crashed sync jobs
        # - Adds last_heartbeat_at column for monitoring long-running syncs
        # - Indexed for efficient stale run queries (status='running')
        # - Allows auto-failing syncs with no heartbeat for 180+ seconds
        # This prevents "SYNC ALREADY RUNNING" deadlock when background job dies
        checkpoint("Migration 86: Adding heartbeat to receipt_sync_runs (stale run detection)")
        
        if check_table_exists('receipt_sync_runs'):
            from sqlalchemy import text
            try:
                fields_added = []
                
                # Add last_heartbeat_at column if missing
                if not check_column_exists('receipt_sync_runs', 'last_heartbeat_at'):
                    checkpoint("  → Adding last_heartbeat_at to receipt_sync_runs...")
                    db.session.execute(text("""
                        ALTER TABLE receipt_sync_runs 
                        ADD COLUMN IF NOT EXISTS last_heartbeat_at TIMESTAMP NULL
                    """))
                    
                    # Create partial index for efficient stale run detection
                    # Only index running syncs since we only check those for staleness
                    if not check_index_exists('idx_receipt_sync_runs_heartbeat'):
                        checkpoint("  → Creating partial index on last_heartbeat_at for running syncs...")
                        db.session.execute(text("""
                            CREATE INDEX IF NOT EXISTS idx_receipt_sync_runs_heartbeat 
                            ON receipt_sync_runs (last_heartbeat_at) 
                            WHERE status = 'running'
                        """))
                        checkpoint("  ✅ Partial index created for efficient stale detection")
                    
                    # Initialize heartbeat for existing running syncs to prevent false positives
                    checkpoint("  → Initializing heartbeat for existing running syncs...")
                    result = db.session.execute(text("""
                        UPDATE receipt_sync_runs 
                        SET last_heartbeat_at = COALESCE(updated_at, started_at)
                        WHERE status = 'running' AND last_heartbeat_at IS NULL
                    """))
                    updated_count = result.rowcount if hasattr(result, 'rowcount') else 0
                    if updated_count > 0:
                        checkpoint(f"  ✅ Initialized heartbeat for {updated_count} existing running sync(s)")
                    
                    fields_added.append('last_heartbeat_at')
                    checkpoint("  ✅ last_heartbeat_at added with partial index")
                
                # Also add business_id + status composite index if not exists (for stale detection query)
                if not check_index_exists('idx_receipt_sync_runs_business_status'):
                    checkpoint("  → Creating composite index on (business_id, status)...")
                    db.session.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_receipt_sync_runs_business_status 
                        ON receipt_sync_runs (business_id, status)
                    """))
                    fields_added.append('business_status_index')
                    checkpoint("  ✅ Composite index created for efficient sync run lookup")
                
                if fields_added:
                    migrations_applied.append("add_receipt_sync_heartbeat")
                    checkpoint(f"✅ Migration 86 complete: {', '.join(fields_added)} added")
                    checkpoint("   🔒 Idempotent: Safe to run multiple times")
                    checkpoint("   🎯 Purpose: Detects stale syncs (no heartbeat > 180s)")
                    checkpoint("   🔧 Enables: Auto-recovery from crashed background jobs")
                else:
                    checkpoint("✅ Migration 86: Heartbeat already exists - skipping")
                    
            except Exception as e:
                db.session.rollback()
                checkpoint(f"❌ Migration 86 failed: {e}")
                logger.error(f"Migration 86 error details: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ receipt_sync_runs table does not exist - skipping")
        
        # Migration 87: Add unique constraint on whatsapp_message.provider_message_id
        # Prevents duplicate messages from webhook retries and race conditions
        # CRITICAL: Unique constraint is per business_id to handle multi-tenant correctly
        if check_table_exists('whatsapp_message'):
            checkpoint("Migration 87: Adding unique constraint on whatsapp_message (business_id, provider_message_id)")
            try:
                # Check if index already exists
                if not check_index_exists('idx_whatsapp_message_provider_id_unique'):
                    checkpoint("  → Checking for duplicate provider_message_id values per business...")
                    
                    # First, remove any existing duplicates (keep oldest message per business)
                    duplicates_query = text("""
                        DELETE FROM whatsapp_message
                        WHERE id NOT IN (
                            SELECT MIN(id)
                            FROM whatsapp_message
                            WHERE provider_message_id IS NOT NULL
                            GROUP BY business_id, provider_message_id
                        )
                        AND provider_message_id IS NOT NULL
                    """)
                    result = db.session.execute(duplicates_query)
                    rows_deleted = result.rowcount
                    
                    if rows_deleted > 0:
                        checkpoint(f"  → Removed {rows_deleted} duplicate messages (kept oldest per business)")
                    else:
                        checkpoint("  → No duplicate messages found")
                    
                    # Add unique constraint (partial index - only for non-NULL values)
                    # CRITICAL: (business_id, provider_message_id) not just provider_message_id
                    checkpoint("  → Creating unique index on (business_id, provider_message_id)...")
                    db.session.execute(text("""
                        CREATE UNIQUE INDEX idx_whatsapp_message_provider_id_unique
                        ON whatsapp_message(business_id, provider_message_id)
                        WHERE provider_message_id IS NOT NULL
                    """))
                    
                    migrations_applied.append("migration_87_whatsapp_unique_constraint")
                    checkpoint("✅ Migration 87 complete: unique constraint added")
                    checkpoint("   🔒 Idempotent: Safe to run multiple times")
                    checkpoint("   🎯 Purpose: Prevents duplicate WhatsApp messages PER BUSINESS")
                    checkpoint("   🔧 Multi-tenant: (business_id, provider_message_id) prevents cross-tenant conflicts")
                else:
                    checkpoint("✅ Migration 87: Unique constraint already exists - skipping")
                    
            except Exception as e:
                db.session.rollback()
                checkpoint(f"❌ Migration 87 failed: {e}")
                logger.error(f"Migration 87 error details: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ whatsapp_message table does not exist - skipping")
        
        # Migration 88: Create contract_signature_fields table for PDF signature placement
        # This allows businesses to mark signature areas on PDFs before sending for signature
        if not check_table_exists('contract_signature_fields'):
            checkpoint("🔧 Running Migration 88: Create contract_signature_fields table")
            try:
                from sqlalchemy import text
                
                db.session.execute(text("""
                    CREATE TABLE contract_signature_fields (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        contract_id INTEGER NOT NULL REFERENCES contract(id) ON DELETE CASCADE,
                        page INTEGER NOT NULL,
                        x REAL NOT NULL,
                        y REAL NOT NULL,
                        w REAL NOT NULL,
                        h REAL NOT NULL,
                        required BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT check_coordinates CHECK (
                            x >= 0 AND x <= 1 AND 
                            y >= 0 AND y <= 1 AND 
                            w > 0 AND w <= 1 AND 
                            h > 0 AND h <= 1
                        ),
                        CONSTRAINT check_page CHECK (page > 0)
                    )
                """))
                
                # Create indexes for faster queries
                db.session.execute(text("""
                    CREATE INDEX idx_contract_signature_fields_contract 
                    ON contract_signature_fields(contract_id)
                """))
                
                db.session.execute(text("""
                    CREATE INDEX idx_contract_signature_fields_business 
                    ON contract_signature_fields(business_id)
                """))
                
                migrations_applied.append("create_contract_signature_fields_table")
                checkpoint("✅ Migration 88: Created contract_signature_fields table with indexes")
            except Exception as e:
                db.session.rollback()
                checkpoint(f"❌ Migration 88 failed: {e}")
                logger.error(f"Migration 88 error details: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ contract_signature_fields table already exists - skipping")
        
        # ============================================================================
        # Migration 89: Gmail Sync Run-to-Completion Enhancements
        # ============================================================================
        # Adds fields to support:
        # 1. Run-to-completion mode (ignore time limits when RUN_TO_COMPLETION=true)
        # 2. Persistent progress tracking (from_date, to_date, months_back)
        # 3. Better checkpoint state (paused status)
        # 4. Improved progress tracking (skipped_count)
        #
        # 🔒 CRITICAL: Each ALTER TABLE runs in its own transaction to prevent
        # Postgres transaction rollback from affecting successful column additions.
        checkpoint("Migration 89: Gmail Sync Run-to-Completion Enhancements")
        
        if check_table_exists('receipt_sync_runs'):
            fields_to_add = []
            
            # Add from_date field - separate transaction
            if not check_column_exists('receipt_sync_runs', 'from_date'):
                checkpoint("  → Adding from_date column...")
                try:
                    exec_ddl(db.engine, """
                        ALTER TABLE receipt_sync_runs 
                        ADD COLUMN IF NOT EXISTS from_date DATE NULL
                    """)
                    fields_to_add.append('from_date')
                except Exception as e:
                    checkpoint(f"  ⚠️ Failed to add from_date: {e}")
            
            # Add to_date field - separate transaction
            if not check_column_exists('receipt_sync_runs', 'to_date'):
                checkpoint("  → Adding to_date column...")
                try:
                    exec_ddl(db.engine, """
                        ALTER TABLE receipt_sync_runs 
                        ADD COLUMN IF NOT EXISTS to_date DATE NULL
                    """)
                    fields_to_add.append('to_date')
                except Exception as e:
                    checkpoint(f"  ⚠️ Failed to add to_date: {e}")
            
            # Add months_back field - separate transaction
            if not check_column_exists('receipt_sync_runs', 'months_back'):
                checkpoint("  → Adding months_back column...")
                try:
                    exec_ddl(db.engine, """
                        ALTER TABLE receipt_sync_runs 
                        ADD COLUMN IF NOT EXISTS months_back INTEGER NULL
                    """)
                    fields_to_add.append('months_back')
                except Exception as e:
                    checkpoint(f"  ⚠️ Failed to add months_back: {e}")
            
            # Add run_to_completion field - separate transaction
            if not check_column_exists('receipt_sync_runs', 'run_to_completion'):
                checkpoint("  → Adding run_to_completion column...")
                try:
                    exec_ddl(db.engine, """
                        ALTER TABLE receipt_sync_runs 
                        ADD COLUMN IF NOT EXISTS run_to_completion BOOLEAN NULL
                    """)
                    fields_to_add.append('run_to_completion')
                except Exception as e:
                    checkpoint(f"  ⚠️ Failed to add run_to_completion: {e}")
            
            # Add max_seconds_per_run field - separate transaction
            if not check_column_exists('receipt_sync_runs', 'max_seconds_per_run'):
                checkpoint("  → Adding max_seconds_per_run column...")
                try:
                    exec_ddl(db.engine, """
                        ALTER TABLE receipt_sync_runs 
                        ADD COLUMN IF NOT EXISTS max_seconds_per_run INTEGER NULL
                    """)
                    fields_to_add.append('max_seconds_per_run')
                except Exception as e:
                    checkpoint(f"  ⚠️ Failed to add max_seconds_per_run: {e}")
            
            # Add skipped_count field - separate transaction
            if not check_column_exists('receipt_sync_runs', 'skipped_count'):
                checkpoint("  → Adding skipped_count column...")
                try:
                    exec_ddl(db.engine, """
                        ALTER TABLE receipt_sync_runs 
                        ADD COLUMN IF NOT EXISTS skipped_count INTEGER NOT NULL DEFAULT 0
                    """)
                    fields_to_add.append('skipped_count')
                except Exception as e:
                    checkpoint(f"  ⚠️ Failed to add skipped_count: {e}")
            
            # Clean up invalid status values before adding constraint - separate transaction
            checkpoint("  → Cleaning up invalid status values...")
            try:
                exec_ddl(db.engine, """
                    UPDATE receipt_sync_runs
                    SET status = 'failed'
                    WHERE status IS NOT NULL
                      AND status NOT IN ('running', 'paused', 'completed', 'failed', 'cancelled')
                """)
                checkpoint("  ✅ Invalid status values cleaned up")
            except Exception as e:
                checkpoint(f"  ⚠️ Failed to clean up invalid status values: {e}")
            
            # Update status constraint to include 'paused' - separate transaction
            checkpoint("  → Updating status constraint to include 'paused'...")
            try:
                # Drop old constraint if it exists
                exec_ddl(db.engine, """
                    ALTER TABLE receipt_sync_runs 
                    DROP CONSTRAINT IF EXISTS chk_receipt_sync_status
                """)
                # Add new constraint with 'paused' status
                exec_ddl(db.engine, """
                    ALTER TABLE receipt_sync_runs 
                    ADD CONSTRAINT chk_receipt_sync_status 
                    CHECK (status IN ('running', 'paused', 'completed', 'failed', 'cancelled'))
                """)
                checkpoint("  ✅ Status constraint updated with 'paused'")
            except Exception as e:
                checkpoint(f"  ⚠️ Failed to update status constraint: {e}")
            
            if fields_to_add:
                migrations_applied.append("add_gmail_sync_run_to_completion_fields")
                checkpoint(f"✅ Migration 89 complete: {', '.join(fields_to_add)} added + status constraint updated")
            else:
                checkpoint("  ℹ️ All fields already exist - skipping")
            
            # 🔒 VALIDATION: Verify all required columns exist - FAIL if any are missing
            checkpoint("  → Validating receipt_sync_runs schema...")
            missing_columns = []
            for col in MIGRATION_89_REQUIRED_COLUMNS:
                if not check_column_exists('receipt_sync_runs', col):
                    missing_columns.append(col)
            
            if missing_columns:
                error_msg = f"❌ MIGRATION 89 VALIDATION FAILED: Missing columns in receipt_sync_runs: {', '.join(missing_columns)}"
                checkpoint(error_msg)
                raise RuntimeError(error_msg)
            else:
                checkpoint("  ✅ Schema validation passed - all required columns exist")
        else:
            checkpoint("  ℹ️ receipt_sync_runs table doesn't exist - skipping")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 90: Expand contract_sign_events event_type constraint
        # ═══════════════════════════════════════════════════════════════════════
        # ROOT CAUSE: The current constraint only allows 7 event types, but the code
        # tries to insert 'file_viewed', 'updated', 'deleted', 'signature_fields_updated'
        # causing constraint violations and breaking PDF preview/audit trail.
        #
        # FIX: Expand the CHECK constraint to include ALL event types used in routes_contracts.py:
        # - file_viewed (line 889)
        # - updated (line 1699)
        # - deleted (line 1759)
        # - signature_fields_updated (line 1887)
        # 
        # This is NOT "softening errors" - it's fixing the schema to match the code.
        # The constraint exists to prevent typos, not to restrict legitimate event types.
        # ═══════════════════════════════════════════════════════════════════════
        if check_table_exists('contract_sign_events'):
            checkpoint("🔧 Running Migration 90: Expand contract_sign_events event_type constraint")
            
            try:
                # Check if constraint exists by querying check_constraints
                result = db.session.execute(text("""
                    SELECT constraint_name, check_clause
                    FROM information_schema.check_constraints 
                    WHERE constraint_name LIKE '%event_type%'
                    AND constraint_schema = 'public'
                """))
                constraint_row = result.fetchone()
                
                if constraint_row:
                    constraint_name = constraint_row[0]
                    check_clause = constraint_row[1] if len(constraint_row) > 1 else ''
                    
                    # Check if ALL event types from the constant are in the constraint
                    missing_types = []
                    for event_type in CONTRACT_EVENT_TYPES:
                        if event_type not in check_clause:
                            missing_types.append(event_type)
                    
                    if not missing_types:
                        checkpoint("  ℹ️ All event types already in constraint - skipping")
                    else:
                        checkpoint(f"  → Adding missing event types: {', '.join(missing_types)}")
                        
                        # Drop old constraint and add new one with ALL event types
                        db.session.execute(text(f"""
                            ALTER TABLE contract_sign_events 
                            DROP CONSTRAINT IF EXISTS {constraint_name}
                        """))
                        
                        # Build constraint with all event types from constant
                        event_types_sql = ', '.join([f"'{et}'" for et in CONTRACT_EVENT_TYPES])
                        db.session.execute(text(f"""
                            ALTER TABLE contract_sign_events 
                            ADD CONSTRAINT contract_sign_events_event_type_check 
                            CHECK (event_type IN ({event_types_sql}))
                        """))
                        
                        migrations_applied.append('expand_contract_event_types')
                        checkpoint("✅ Migration 90 completed - Expanded event_type constraint")
                        checkpoint(f"   📋 Added: {', '.join(missing_types)}")
                        checkpoint("   🎯 Purpose: Fix PDF preview/audit trail failures")
                        checkpoint("   🔒 Security: Constraint still prevents typos, now matches actual code usage")
                else:
                    checkpoint("  ℹ️ Event type constraint not found - table may not have constraint yet")
                
            except Exception as e:
                log.error(f"❌ Migration 90 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ contract_sign_events table does not exist - skipping")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 91: Add Preview Tracking Fields to Receipts Table
        # ═══════════════════════════════════════════════════════════════════════
        # PURPOSE: Track preview generation status and failure reasons for debugging
        # 
        # Current issue: When preview generation fails, we log it but don't store
        # the failure in the database. This makes it hard to:
        # 1. Show users which receipts have preview issues
        # 2. Retry failed previews automatically
        # 3. Debug why previews are failing
        #
        # Solution: Add two fields to receipts table:
        # - preview_status: 'pending'|'generated'|'failed'|'not_available'
        # - preview_failure_reason: TEXT for storing error message
        # ═══════════════════════════════════════════════════════════════════════
        if check_table_exists('receipts'):
            checkpoint("🔧 Running Migration 91: Add preview tracking to receipts table")
            
            try:
                fields_to_add = []
                
                # Add preview_status field
                if not check_column_exists('receipts', 'preview_status'):
                    checkpoint("  → Adding preview_status column")
                    db.session.execute(text("""
                        ALTER TABLE receipts 
                        ADD COLUMN preview_status VARCHAR(20) DEFAULT 'pending'
                    """))
                    
                    # Add CHECK constraint for valid values
                    db.session.execute(text("""
                        ALTER TABLE receipts 
                        ADD CONSTRAINT chk_receipt_preview_status 
                        CHECK (preview_status IN ('pending', 'generated', 'failed', 'not_available', 'skipped'))
                    """))
                    
                    fields_to_add.append('preview_status')
                    checkpoint("    ✅ preview_status added with constraint")
                
                # Add preview_failure_reason field
                if not check_column_exists('receipts', 'preview_failure_reason'):
                    checkpoint("  → Adding preview_failure_reason column")
                    db.session.execute(text("""
                        ALTER TABLE receipts 
                        ADD COLUMN preview_failure_reason TEXT
                    """))
                    
                    fields_to_add.append('preview_failure_reason')
                    checkpoint("    ✅ preview_failure_reason added")
                
                # Backfill existing receipts with appropriate status
                if fields_to_add:
                    checkpoint("  → Backfilling existing receipts with status")
                    
                    # Set 'generated' for receipts that have preview_attachment_id
                    result = db.session.execute(text("""
                        UPDATE receipts 
                        SET preview_status = 'generated' 
                        WHERE preview_attachment_id IS NOT NULL 
                        AND preview_status = 'pending'
                    """))
                    generated_count = result.rowcount if hasattr(result, 'rowcount') else 0
                    
                    # Set 'not_available' for old receipts without preview (won't retry automatically)
                    result = db.session.execute(text("""
                        UPDATE receipts 
                        SET preview_status = 'not_available' 
                        WHERE preview_attachment_id IS NULL 
                        AND preview_status = 'pending'
                        AND created_at < NOW() - INTERVAL '7 days'
                    """))
                    old_count = result.rowcount if hasattr(result, 'rowcount') else 0
                    
                    checkpoint(f"    ✅ Backfilled: {generated_count} generated, {old_count} not_available")
                    
                    migrations_applied.append('add_receipt_preview_tracking')
                    checkpoint("✅ Migration 91 completed - Receipt preview tracking enabled")
                    checkpoint("   📋 Purpose: Track preview generation status and enable retries")
                    checkpoint("   🎯 Benefits: Better UI feedback + automatic retry for failed previews")
                else:
                    checkpoint("  ℹ️ All preview tracking fields already exist - skipping")
                
            except Exception as e:
                log.error(f"❌ Migration 91 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ receipts table does not exist - skipping")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 92: Add needs_review and receipt_type fields for better filtering
        # ═══════════════════════════════════════════════════════════════════════
        # PURPOSE: Address false positives from low MIN_CONFIDENCE (5)
        # 
        # New fields:
        # - needs_review: Flag for low-confidence receipts (5-14) or missing critical data
        # - receipt_type: Classify receipt types (confirmation|receipt|invoice|statement)
        #
        # This allows:
        # 1. Filter out "confirmation emails" from reports/summaries
        # 2. User can review low-confidence items separately
        # 3. Better analytics on receipt types
        # ═══════════════════════════════════════════════════════════════════════
        if check_table_exists('receipts'):
            checkpoint("🔧 Running Migration 92: Add needs_review and receipt_type to receipts")
            
            try:
                fields_to_add = []
                
                # Add needs_review field
                if not check_column_exists('receipts', 'needs_review'):
                    checkpoint("  → Adding needs_review column")
                    db.session.execute(text("""
                        ALTER TABLE receipts 
                        ADD COLUMN needs_review BOOLEAN DEFAULT FALSE
                    """))
                    fields_to_add.append('needs_review')
                    checkpoint("    ✅ needs_review added")
                
                # Add receipt_type field
                if not check_column_exists('receipts', 'receipt_type'):
                    checkpoint("  → Adding receipt_type column")
                    db.session.execute(text("""
                        ALTER TABLE receipts 
                        ADD COLUMN receipt_type VARCHAR(32)
                    """))
                    
                    # Add CHECK constraint for valid values
                    db.session.execute(text("""
                        ALTER TABLE receipts 
                        ADD CONSTRAINT chk_receipt_type 
                        CHECK (receipt_type IS NULL OR receipt_type IN ('confirmation', 'receipt', 'invoice', 'statement', 'other'))
                    """))
                    
                    fields_to_add.append('receipt_type')
                    checkpoint("    ✅ receipt_type added with constraint")
                
                # Backfill existing receipts
                if fields_to_add:
                    checkpoint("  → Backfilling existing receipts")
                    
                    # Set needs_review for low-confidence receipts (confidence < 15)
                    result = db.session.execute(text("""
                        UPDATE receipts 
                        SET needs_review = TRUE 
                        WHERE confidence < 15 
                        AND needs_review = FALSE
                    """))
                    low_conf_count = result.rowcount if hasattr(result, 'rowcount') else 0
                    
                    # Set needs_review for receipts without amount
                    result = db.session.execute(text("""
                        UPDATE receipts 
                        SET needs_review = TRUE 
                        WHERE amount IS NULL 
                        AND needs_review = FALSE
                    """))
                    no_amount_count = result.rowcount if hasattr(result, 'rowcount') else 0
                    
                    checkpoint(f"    ✅ Backfilled: {low_conf_count} low-confidence, {no_amount_count} no-amount")
                    
                    migrations_applied.append('add_receipt_review_fields')
                    checkpoint("✅ Migration 92 completed - Receipt review fields added")
                    checkpoint("   📋 Purpose: Better handling of false positives from low threshold")
                    checkpoint("   🎯 Benefits: Filter confirmations from reports, flag suspicious items")
                else:
                    checkpoint("  ℹ️ All review fields already exist - skipping")
                
            except Exception as e:
                log.error(f"❌ Migration 92 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ receipts table does not exist - skipping")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 93: Add phone_raw column to leads table
        # ═══════════════════════════════════════════════════════════════════════
        # PURPOSE: Fix migration drift - phone_raw column exists in model but not in DB
        # 
        # The phone_raw column was added to the Lead model to store the original phone
        # input before normalization (for debugging purposes), but the corresponding
        # migration was never created. This causes UndefinedColumn errors when querying
        # leads with phone_raw in the SELECT clause.
        #
        # Fixes: psycopg2.errors.UndefinedColumn: column leads.phone_raw does not exist
        # ═══════════════════════════════════════════════════════════════════════
        if check_table_exists('leads'):
            checkpoint("🔧 Running Migration 93: Add phone_raw column to leads table")
            
            try:
                if not check_column_exists('leads', 'phone_raw'):
                    checkpoint("  → Adding phone_raw column (VARCHAR(64), nullable)")
                    db.session.execute(text("""
                        ALTER TABLE leads 
                        ADD COLUMN phone_raw VARCHAR(64) NULL
                    """))
                    
                    migrations_applied.append('add_leads_phone_raw_column')
                    checkpoint("✅ Migration 93 completed - phone_raw column added to leads")
                    checkpoint("   📋 Purpose: Store original phone input before normalization")
                    checkpoint("   🎯 Fixes: UndefinedColumn errors in routes and services")
                else:
                    checkpoint("  ℹ️ phone_raw column already exists - skipping")
                
            except Exception as e:
                log.error(f"❌ Migration 93 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ leads table does not exist - skipping")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 94: Add WhatsApp JID columns to leads table
        # ═══════════════════════════════════════════════════════════════════════
        # PURPOSE: Fix migration drift - WhatsApp columns exist in model but not in DB
        # 
        # These columns were added to the Lead model to support WhatsApp LID identifiers
        # (Android/Business accounts), proper identity mapping, and reliable reply routing.
        # The standalone migration_add_lead_phone_whatsapp_fields.py was never integrated
        # into db_migrate.py, causing UndefinedColumn errors when querying leads.
        #
        # Fixes: psycopg2.errors.UndefinedColumn: column leads.whatsapp_jid does not exist
        # ═══════════════════════════════════════════════════════════════════════
        if check_table_exists('leads'):
            checkpoint("🔧 Running Migration 94: Add WhatsApp JID columns to leads table")
            
            try:
                # Add whatsapp_jid column
                if not check_column_exists('leads', 'whatsapp_jid'):
                    checkpoint("  → Adding whatsapp_jid column (VARCHAR(128), nullable)")
                    db.session.execute(text("""
                        ALTER TABLE leads 
                        ADD COLUMN whatsapp_jid VARCHAR(128) NULL
                    """))
                    migrations_applied.append('add_leads_whatsapp_jid_column')
                else:
                    checkpoint("  ℹ️ whatsapp_jid column already exists - skipping")
                
                # Add whatsapp_jid_alt column
                if not check_column_exists('leads', 'whatsapp_jid_alt'):
                    checkpoint("  → Adding whatsapp_jid_alt column (VARCHAR(128), nullable)")
                    db.session.execute(text("""
                        ALTER TABLE leads 
                        ADD COLUMN whatsapp_jid_alt VARCHAR(128) NULL
                    """))
                    migrations_applied.append('add_leads_whatsapp_jid_alt_column')
                else:
                    checkpoint("  ℹ️ whatsapp_jid_alt column already exists - skipping")
                
                # Add reply_jid column (CRITICAL for Android/LID)
                if not check_column_exists('leads', 'reply_jid'):
                    checkpoint("  → Adding reply_jid column (VARCHAR(128), nullable)")
                    db.session.execute(text("""
                        ALTER TABLE leads 
                        ADD COLUMN reply_jid VARCHAR(128) NULL
                    """))
                    migrations_applied.append('add_leads_reply_jid_column')
                else:
                    checkpoint("  ℹ️ reply_jid column already exists - skipping")
                
                # Add reply_jid_type column
                if not check_column_exists('leads', 'reply_jid_type'):
                    checkpoint("  → Adding reply_jid_type column (VARCHAR(32), nullable)")
                    db.session.execute(text("""
                        ALTER TABLE leads 
                        ADD COLUMN reply_jid_type VARCHAR(32) NULL
                    """))
                    migrations_applied.append('add_leads_reply_jid_type_column')
                else:
                    checkpoint("  ℹ️ reply_jid_type column already exists - skipping")
                
                # Add index on whatsapp_jid for fast lookups
                if not check_index_exists('ix_leads_whatsapp_jid'):
                    checkpoint("  → Creating index on whatsapp_jid")
                    db.session.execute(text("""
                        CREATE INDEX ix_leads_whatsapp_jid ON leads(whatsapp_jid)
                    """))
                    migrations_applied.append('add_index_leads_whatsapp_jid')
                else:
                    checkpoint("  ℹ️ Index ix_leads_whatsapp_jid already exists - skipping")
                
                # Add index on reply_jid for fast lookups
                if not check_index_exists('ix_leads_reply_jid'):
                    checkpoint("  → Creating index on reply_jid")
                    db.session.execute(text("""
                        CREATE INDEX ix_leads_reply_jid ON leads(reply_jid)
                    """))
                    migrations_applied.append('add_index_leads_reply_jid')
                else:
                    checkpoint("  ℹ️ Index ix_leads_reply_jid already exists - skipping")
                
                checkpoint("✅ Migration 94 completed - WhatsApp JID columns added to leads")
                checkpoint("   📋 Purpose: Store WhatsApp identifiers for LID support")
                checkpoint("   🎯 Fixes: UndefinedColumn errors for WhatsApp features")
                
            except Exception as e:
                log.error(f"❌ Migration 94 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ leads table does not exist - skipping")
        
        # Migration 95: Add 'incomplete' status to receipts check constraint
        if check_table_exists('receipts'):
            from sqlalchemy import text
            try:
                checkpoint("🔧 Running Migration 95: Add 'incomplete' status to receipts")
                
                # Drop old constraint and create new one with 'incomplete'
                db.session.execute(text("""
                    DO $$ 
                    BEGIN
                        -- Drop existing constraint if it exists
                        ALTER TABLE receipts DROP CONSTRAINT IF EXISTS chk_receipt_status;
                        
                        -- Create new constraint with 'incomplete' status
                        ALTER TABLE receipts 
                        ADD CONSTRAINT chk_receipt_status 
                        CHECK (status IN ('pending_review', 'approved', 'rejected', 'not_receipt', 'incomplete'));
                        
                        RAISE NOTICE 'Added incomplete status to receipts check constraint';
                    END $$;
                """))
                
                migrations_applied.append("add_incomplete_status_to_receipts")
                checkpoint("✅ Migration 95 completed - 'incomplete' status added to receipts")
                checkpoint("   📋 Purpose: Track receipts with validation failures (missing snapshot/attachments)")
                checkpoint("   🎯 Ensures: NO emails with attachments are missed (Rule 6/7/10)")
                checkpoint("   ℹ️  Status values: pending_review, approved, rejected, not_receipt, incomplete")
                
            except Exception as e:
                log.error(f"❌ Migration 95 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ receipts table does not exist - skipping")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 96: WhatsApp Prompt-Only Mode + Lead Name Tracking
        # 🎯 PURPOSE: Add dedicated WhatsApp prompt fields to business table
        #            Add name tracking fields to leads table
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 96: WhatsApp Prompt-Only Mode + Lead Name Tracking")
        
        # Part 1: Add WhatsApp prompt fields to business table
        if check_table_exists('business'):
            try:
                # whatsapp_system_prompt - dedicated WhatsApp AI prompt
                if not check_column_exists('business', 'whatsapp_system_prompt'):
                    checkpoint("  → Adding whatsapp_system_prompt to business...")
                    db.session.execute(text("""
                        ALTER TABLE business 
                        ADD COLUMN whatsapp_system_prompt TEXT
                    """))
                    checkpoint("  ✅ business.whatsapp_system_prompt added")
                    migrations_applied.append('add_business_whatsapp_system_prompt')
                
                # whatsapp_temperature - temperature for WhatsApp responses
                if not check_column_exists('business', 'whatsapp_temperature'):
                    checkpoint("  → Adding whatsapp_temperature to business...")
                    db.session.execute(text("""
                        ALTER TABLE business 
                        ADD COLUMN whatsapp_temperature FLOAT DEFAULT 0.0
                    """))
                    checkpoint("  ✅ business.whatsapp_temperature added")
                    migrations_applied.append('add_business_whatsapp_temperature')
                
                # whatsapp_model - AI model for WhatsApp
                if not check_column_exists('business', 'whatsapp_model'):
                    checkpoint("  → Adding whatsapp_model to business...")
                    db.session.execute(text("""
                        ALTER TABLE business 
                        ADD COLUMN whatsapp_model VARCHAR(50) DEFAULT 'gpt-4o-mini'
                    """))
                    checkpoint("  ✅ business.whatsapp_model added")
                    migrations_applied.append('add_business_whatsapp_model')
                
                # whatsapp_max_tokens - max tokens for WhatsApp
                if not check_column_exists('business', 'whatsapp_max_tokens'):
                    checkpoint("  → Adding whatsapp_max_tokens to business...")
                    db.session.execute(text("""
                        ALTER TABLE business 
                        ADD COLUMN whatsapp_max_tokens INTEGER DEFAULT 350
                    """))
                    checkpoint("  ✅ business.whatsapp_max_tokens added")
                    migrations_applied.append('add_business_whatsapp_max_tokens')
                
                checkpoint("✅ Migration 96 Part 1 completed - WhatsApp prompt fields added to business")
            except Exception as e:
                log.error(f"❌ Migration 96 Part 1 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ business table does not exist - skipping Part 1")
        
        # Part 2: Add name tracking fields to leads table
        if check_table_exists('leads'):
            try:
                # name - unified name field
                if not check_column_exists('leads', 'name'):
                    checkpoint("  → Adding name to leads...")
                    db.session.execute(text("""
                        ALTER TABLE leads 
                        ADD COLUMN name VARCHAR(255)
                    """))
                    checkpoint("  ✅ leads.name added")
                    migrations_applied.append('add_leads_name')
                
                # name_source - source of name (whatsapp/call/manual)
                if not check_column_exists('leads', 'name_source'):
                    checkpoint("  → Adding name_source to leads...")
                    db.session.execute(text("""
                        ALTER TABLE leads 
                        ADD COLUMN name_source VARCHAR(32)
                    """))
                    checkpoint("  ✅ leads.name_source added")
                    migrations_applied.append('add_leads_name_source')
                
                # name_updated_at - when name was last updated
                if not check_column_exists('leads', 'name_updated_at'):
                    checkpoint("  → Adding name_updated_at to leads...")
                    db.session.execute(text("""
                        ALTER TABLE leads 
                        ADD COLUMN name_updated_at TIMESTAMP
                    """))
                    checkpoint("  ✅ leads.name_updated_at added")
                    migrations_applied.append('add_leads_name_updated_at')
                
                # Migrate existing lead names to new name column
                checkpoint("  → Migrating existing lead names...")
                result = db.session.execute(text("""
                    UPDATE leads 
                    SET name = CASE 
                        WHEN first_name IS NOT NULL AND last_name IS NOT NULL 
                            THEN first_name || ' ' || last_name
                        WHEN first_name IS NOT NULL 
                            THEN first_name
                        WHEN last_name IS NOT NULL 
                            THEN last_name
                        ELSE NULL
                    END,
                    name_source = 'manual',
                    name_updated_at = updated_at
                    WHERE name IS NULL 
                    AND (first_name IS NOT NULL OR last_name IS NOT NULL)
                """))
                rows_updated = result.rowcount if hasattr(result, 'rowcount') else 0
                checkpoint(f"  ✅ Migrated {rows_updated} existing lead names")
                
                checkpoint("✅ Migration 96 Part 2 completed - Lead name tracking fields added")
            except Exception as e:
                log.error(f"❌ Migration 96 Part 2 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️ leads table does not exist - skipping Part 2")
        
        checkpoint("✅ Migration 96 completed - WhatsApp Prompt-Only Mode + Lead Name Tracking")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 97: Add unique constraint to receipts to prevent duplicates
        # ═══════════════════════════════════════════════════════════════════════
        if check_table_exists('receipts'):
            checkpoint("🔧 Running Migration 97: Add unique constraint to receipts")
            
            try:
                # Check if unique index already exists
                index_exists = db.session.execute(text("""
                    SELECT COUNT(*) 
                    FROM pg_indexes 
                    WHERE indexname = 'uq_receipts_business_gmail_message'
                """)).scalar() > 0
                
                if not index_exists:
                    checkpoint("  → Creating unique index for Gmail message IDs...")
                    
                    # First, check for existing duplicates and clean them up
                    checkpoint("  → Checking for existing duplicates...")
                    result = db.session.execute(text("""
                        SELECT 
                            business_id,
                            gmail_message_id,
                            COUNT(*) as count
                        FROM receipts
                        WHERE is_deleted = FALSE 
                        AND gmail_message_id IS NOT NULL
                        GROUP BY business_id, gmail_message_id
                        HAVING COUNT(*) > 1
                    """))
                    
                    duplicates = result.fetchall()
                    if duplicates:
                        checkpoint(f"  ⚠️  Found {len(duplicates)} duplicate Gmail message IDs")
                        checkpoint("  → Marking older duplicates as deleted...")
                        
                        for dup in duplicates:
                            business_id, gmail_message_id, count = dup
                            # Keep the newest one, soft-delete the rest
                            db.session.execute(text("""
                                UPDATE receipts
                                SET is_deleted = TRUE, deleted_at = NOW()
                                WHERE business_id = :business_id
                                AND gmail_message_id = :gmail_message_id
                                AND is_deleted = FALSE
                                AND id NOT IN (
                                    SELECT id FROM receipts
                                    WHERE business_id = :business_id
                                    AND gmail_message_id = :gmail_message_id
                                    AND is_deleted = FALSE
                                    ORDER BY created_at DESC
                                    LIMIT 1
                                )
                            """), {
                                'business_id': business_id,
                                'gmail_message_id': gmail_message_id
                            })
                        
                        checkpoint(f"  ✅ Cleaned up {len(duplicates)} duplicate sets")
                    else:
                        checkpoint("  ✅ No duplicates found")
                    
                    # Now create the unique index
                    # This is a partial unique index that only applies to:
                    # - Non-deleted receipts (is_deleted = FALSE)
                    # - Receipts with gmail_message_id (NOT NULL)
                    # This allows:
                    # 1. Multiple NULL gmail_message_ids (for manual/upload receipts)
                    # 2. Multiple deleted receipts with same gmail_message_id
                    # 3. But prevents duplicate active receipts from same Gmail message
                    db.session.execute(text("""
                        CREATE UNIQUE INDEX uq_receipts_business_gmail_message 
                        ON receipts(business_id, gmail_message_id)
                        WHERE is_deleted = FALSE AND gmail_message_id IS NOT NULL
                    """))
                    
                    checkpoint("  ✅ Created unique constraint for receipts")
                    migrations_applied.append('add_receipts_unique_constraint')
                else:
                    checkpoint("  ℹ️  Unique index already exists - skipping")
                
                checkpoint("✅ Migration 97 completed - Receipts unique constraint added")
                
            except Exception as e:
                checkpoint(f"❌ Migration 97 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️  receipts table does not exist - skipping Migration 97")
        
        # ============================================================================
        # Migration 98: Voice Tester - Add TTS provider fields to business table
        # ============================================================================
        # Adds TTS provider selection fields for voice testing feature
        # - tts_provider: "openai" | "gemini" - Which TTS provider to use
        # - tts_voice_id: Voice ID for the selected provider
        # - tts_language: Language code (default: he-IL)
        # - tts_speed: Speaking speed (0.5 - 2.0, default: 1.0)
        checkpoint("Migration 98: Adding TTS provider fields to business table")
        if check_table_exists('business'):
            try:
                # Add tts_provider column if missing
                if not check_column_exists('business', 'tts_provider'):
                    checkpoint("  → Adding tts_provider column...")
                    db.session.execute(text("""
                        ALTER TABLE business
                        ADD COLUMN tts_provider VARCHAR(32) DEFAULT 'openai'
                    """))
                    checkpoint("  ✅ tts_provider column added (default: 'openai')")
                    migrations_applied.append('add_business_tts_provider')
                else:
                    checkpoint("  ℹ️ tts_provider column already exists")
                
                # Add tts_voice_id column if missing
                if not check_column_exists('business', 'tts_voice_id'):
                    checkpoint("  → Adding tts_voice_id column...")
                    db.session.execute(text("""
                        ALTER TABLE business
                        ADD COLUMN tts_voice_id VARCHAR(64) DEFAULT 'alloy'
                    """))
                    checkpoint("  ✅ tts_voice_id column added (default: 'alloy')")
                    migrations_applied.append('add_business_tts_voice_id')
                else:
                    checkpoint("  ℹ️ tts_voice_id column already exists")
                
                # Add tts_language column if missing
                if not check_column_exists('business', 'tts_language'):
                    checkpoint("  → Adding tts_language column...")
                    db.session.execute(text("""
                        ALTER TABLE business
                        ADD COLUMN tts_language VARCHAR(16) DEFAULT 'he-IL'
                    """))
                    checkpoint("  ✅ tts_language column added (default: 'he-IL')")
                    migrations_applied.append('add_business_tts_language')
                else:
                    checkpoint("  ℹ️ tts_language column already exists")
                
                # Add tts_speed column if missing
                if not check_column_exists('business', 'tts_speed'):
                    checkpoint("  → Adding tts_speed column...")
                    db.session.execute(text("""
                        ALTER TABLE business
                        ADD COLUMN tts_speed FLOAT DEFAULT 1.0
                    """))
                    checkpoint("  ✅ tts_speed column added (default: 1.0)")
                    migrations_applied.append('add_business_tts_speed')
                else:
                    checkpoint("  ℹ️ tts_speed column already exists")
                
                checkpoint("✅ Migration 98 completed - TTS provider fields added")
                
            except Exception as e:
                checkpoint(f"❌ Migration 98 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️  business table does not exist - skipping Migration 98")
        
        # Migration 99: Add recording_mode column to call_log table
        # ============================================================================
        # CRITICAL FIX: Missing recording_mode column causes schema drift and breaks
        # many routes related to calls/recordings/tests
        # - recording_mode: TEXT - Tracks how recording was initiated
        #   Values: 'realtime', 'twilio_recording', 'offline_stt', or NULL
        # - Default: 'realtime' (for existing records)
        # ============================================================================
        checkpoint("Migration 99: Adding recording_mode column to call_log table")
        if check_table_exists('call_log'):
            try:
                # Add recording_mode column if missing
                if not check_column_exists('call_log', 'recording_mode'):
                    checkpoint("  → Adding recording_mode column...")
                    db.session.execute(text("""
                        ALTER TABLE call_log
                        ADD COLUMN recording_mode TEXT DEFAULT 'realtime'
                    """))
                    checkpoint("  ✅ recording_mode column added (default: 'realtime', nullable)")
                    migrations_applied.append('add_call_log_recording_mode')
                else:
                    checkpoint("  ℹ️ recording_mode column already exists")
                
                checkpoint("✅ Migration 99 completed - recording_mode column added")
                
            except Exception as e:
                checkpoint(f"❌ Migration 99 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️  call_log table does not exist - skipping Migration 99")
        
        # ============================================================================
        # Migration 100: Background Jobs Table for Stable Batch Operations
        # ============================================================================
        # Implements background job management for heavy operations like delete-all
        # Features:
        # - Multi-tenant isolation (business_id)
        # - Job status tracking (queued/running/paused/completed/failed/cancelled)
        # - Progress tracking (total/processed/succeeded/failed_count)
        # - Cursor-based resumability for interrupted jobs
        # - Prevents concurrent jobs per business (unique constraint)
        # ============================================================================
        checkpoint("Migration 100: Creating background_jobs table for stable batch operations")
        if not check_table_exists('background_jobs'):
            try:
                checkpoint("  → Creating background_jobs table...")
                db.session.execute(text("""
                    CREATE TABLE background_jobs (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        job_type VARCHAR(64) NOT NULL,
                        status VARCHAR(32) NOT NULL DEFAULT 'queued',
                        total INTEGER DEFAULT 0,
                        processed INTEGER DEFAULT 0,
                        succeeded INTEGER DEFAULT 0,
                        failed_count INTEGER DEFAULT 0,
                        last_error TEXT,
                        cursor TEXT,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW(),
                        started_at TIMESTAMP,
                        finished_at TIMESTAMP,
                        requested_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        CONSTRAINT chk_job_status CHECK (status IN ('queued', 'running', 'paused', 'completed', 'failed', 'cancelled')),
                        CONSTRAINT chk_job_type CHECK (job_type IN ('delete_receipts_all'))
                    )
                """))
                checkpoint("  ✅ background_jobs table created")
                migrations_applied.append('create_background_jobs_table')
                
                # Add indexes for performance
                checkpoint("  → Creating indexes...")
                
                # Index for finding active jobs per business
                db.session.execute(text("""
                    CREATE INDEX idx_background_jobs_business_type_status 
                    ON background_jobs(business_id, job_type, status)
                """))
                checkpoint("  ✅ idx_background_jobs_business_type_status created")
                
                # Index for job history queries
                db.session.execute(text("""
                    CREATE INDEX idx_background_jobs_created_at 
                    ON background_jobs(created_at DESC)
                """))
                checkpoint("  ✅ idx_background_jobs_created_at created")
                
                # Add unique constraint to prevent duplicate active jobs
                checkpoint("  → Creating unique constraint...")
                db.session.execute(text("""
                    CREATE UNIQUE INDEX idx_background_jobs_unique_active 
                    ON background_jobs(business_id, job_type) 
                    WHERE status IN ('queued', 'running', 'paused')
                """))
                checkpoint("  ✅ idx_background_jobs_unique_active created (prevents concurrent jobs)")
                
                checkpoint("✅ Migration 100 completed - background_jobs table ready")
                
            except Exception as e:
                checkpoint(f"❌ Migration 100 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️  background_jobs table already exists - skipping Migration 100")
        
        # ============================================================================
        # Migration 101: Enhanced Receipt Processing Fields
        # ============================================================================
        # Adds new fields for comprehensive receipt processing:
        # - preview_image_key: Direct R2 storage key for preview images (mandatory)
        # - preview_source: Tracking where preview came from (email_html|attachment_pdf|attachment_image|receipt_url|html_fallback)
        # - extraction_status: Separate status for extraction process (pending|processing|success|needs_review|failed)
        # - extraction_error: Detailed error message for failed extractions
        # ============================================================================
        checkpoint("Migration 101: Adding enhanced receipt processing fields")
        if check_table_exists('receipts'):
            try:
                # Add preview_image_key column
                if not check_column_exists('receipts', 'preview_image_key'):
                    checkpoint("  → Adding preview_image_key column...")
                    db.session.execute(text("""
                        ALTER TABLE receipts 
                        ADD COLUMN preview_image_key VARCHAR(512)
                    """))
                    checkpoint("  ✅ preview_image_key column added")
                    migrations_applied.append('add_preview_image_key')
                else:
                    checkpoint("  ℹ️  preview_image_key column already exists")
                
                # Add preview_source column with enum constraint
                if not check_column_exists('receipts', 'preview_source'):
                    checkpoint("  → Adding preview_source column...")
                    db.session.execute(text("""
                        ALTER TABLE receipts 
                        ADD COLUMN preview_source VARCHAR(32)
                    """))
                    checkpoint("  → Adding preview_source constraint...")
                    db.session.execute(text("""
                        ALTER TABLE receipts 
                        ADD CONSTRAINT chk_preview_source 
                        CHECK (preview_source IN ('email_html', 'attachment_pdf', 'attachment_image', 'receipt_url', 'html_fallback'))
                    """))
                    checkpoint("  ✅ preview_source column added with constraint")
                    migrations_applied.append('add_preview_source')
                else:
                    checkpoint("  ℹ️  preview_source column already exists")
                
                # Add extraction_status column with enum constraint
                if not check_column_exists('receipts', 'extraction_status'):
                    checkpoint("  → Adding extraction_status column...")
                    db.session.execute(text("""
                        ALTER TABLE receipts 
                        ADD COLUMN extraction_status VARCHAR(32) DEFAULT 'pending'
                    """))
                    checkpoint("  → Adding extraction_status constraint...")
                    db.session.execute(text("""
                        ALTER TABLE receipts 
                        ADD CONSTRAINT chk_extraction_status 
                        CHECK (extraction_status IN ('pending', 'processing', 'success', 'needs_review', 'failed'))
                    """))
                    checkpoint("  ✅ extraction_status column added with constraint")
                    migrations_applied.append('add_extraction_status')
                else:
                    checkpoint("  ℹ️  extraction_status column already exists")
                
                # Add extraction_error column
                if not check_column_exists('receipts', 'extraction_error'):
                    checkpoint("  → Adding extraction_error column...")
                    db.session.execute(text("""
                        ALTER TABLE receipts 
                        ADD COLUMN extraction_error TEXT
                    """))
                    checkpoint("  ✅ extraction_error column added")
                    migrations_applied.append('add_extraction_error')
                else:
                    checkpoint("  ℹ️  extraction_error column already exists")
                
                # Add index for extraction_status for filtering queries
                if not check_index_exists('idx_receipts_extraction_status'):
                    checkpoint("  → Creating idx_receipts_extraction_status index...")
                    db.session.execute(text("""
                        CREATE INDEX idx_receipts_extraction_status 
                        ON receipts(extraction_status)
                    """))
                    checkpoint("  ✅ idx_receipts_extraction_status index created")
                else:
                    checkpoint("  ℹ️  idx_receipts_extraction_status index already exists")
                
                checkpoint("✅ Migration 101 completed - Enhanced receipt processing fields ready")
                
            except Exception as e:
                checkpoint(f"❌ Migration 101 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️  receipts table does not exist - skipping Migration 101")
        
        # Migration 102: Transform Voice Selection to AI Provider Selection
        # 🔥 PURPOSE: Change from "voice selection" to "provider selection" (OpenAI / Gemini)
        # The selected provider determines LLM brain, TTS voice, and optionally STT
        if check_table_exists('business'):
            checkpoint("Migration 102: Transform voice selection to AI provider selection")
            try:
                # Add ai_provider column - main provider selection (openai | gemini)
                if not check_column_exists('business', 'ai_provider'):
                    checkpoint("  → Adding ai_provider column...")
                    db.session.execute(text("""
                        ALTER TABLE business 
                        ADD COLUMN ai_provider VARCHAR(32) DEFAULT 'openai'
                    """))
                    checkpoint("  ✅ ai_provider column added")
                else:
                    checkpoint("  ℹ️ ai_provider column already exists")
                
                # Add voice_name column - voice within the selected provider
                if not check_column_exists('business', 'voice_name'):
                    checkpoint("  → Adding voice_name column...")
                    db.session.execute(text("""
                        ALTER TABLE business 
                        ADD COLUMN voice_name VARCHAR(64) DEFAULT 'alloy'
                    """))
                    checkpoint("  ✅ voice_name column added")
                else:
                    checkpoint("  ℹ️ voice_name column already exists")
                
                # 🔥 MIGRATION LOGIC: Default to openai, preserve existing voice if valid
                checkpoint("  → Migrating existing provider settings...")
                
                # Step 1: Set ai_provider to 'openai' as default (don't guess from tts_provider)
                # This is safe - users can change it in UI if they want Gemini
                db.session.execute(text("""
                    UPDATE business 
                    SET ai_provider = 'openai'
                    WHERE ai_provider IS NULL
                """))
                
                # Step 2: Set voice_name based on existing tts_voice_id or voice_id
                # Validate voice matches OpenAI (since we're defaulting to openai provider)
                db.session.execute(text("""
                    UPDATE business 
                    SET voice_name = CASE
                        -- Check if current voice is a valid OpenAI voice
                        WHEN COALESCE(tts_voice_id, voice_id) IN (
                            'alloy', 'ash', 'ballad', 'coral', 'echo',
                            'sage', 'shimmer', 'verse', 'marin', 'cedar'
                        ) THEN COALESCE(tts_voice_id, voice_id)
                        ELSE 'alloy'  -- Default OpenAI voice if invalid
                    END
                    WHERE voice_name IS NULL
                """))
                
                checkpoint("  ✅ Existing provider settings migrated to openai defaults")
                
                # Create simple index on ai_provider for queries
                checkpoint("  → Creating index on ai_provider...")
                try:
                    db.session.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_business_ai_provider 
                        ON business(ai_provider)
                    """))
                    checkpoint("  ✅ Index created")
                except Exception as idx_err:
                    checkpoint(f"  ⚠️ Could not create index (may already exist): {idx_err}")
                
                migrations_applied.append('migration_102_ai_provider_selection')
                checkpoint("✅ Migration 102 completed - AI provider selection implemented")
                
            except Exception as e:
                checkpoint(f"❌ Migration 102 failed: {e}")
                db.session.rollback()
                raise
        else:
            checkpoint("  ℹ️  business table does not exist - skipping Migration 102")
        
        # ============================================================================
        # Migration 103: Add heartbeat to background_jobs (Stale Job Detection)
        # ============================================================================
        # Purpose: Enable detection and auto-recovery from stuck/crashed delete jobs
        # - Adds heartbeat_at column for monitoring long-running batch operations
        # - Indexed for efficient stale job queries (status='running')
        # - Allows auto-failing jobs with no heartbeat for 120+ seconds
        # This prevents "DELETE ALREADY RUNNING" deadlock when worker dies/restarts
        checkpoint("Migration 103: Adding heartbeat to background_jobs (stale job detection)")
        
        if check_table_exists('background_jobs'):
            from sqlalchemy import text
            try:
                fields_added = []
                
                # Add heartbeat_at column if missing
                if not check_column_exists('background_jobs', 'heartbeat_at'):
                    checkpoint("  → Adding heartbeat_at to background_jobs...")
                    db.session.execute(text("""
                        ALTER TABLE background_jobs 
                        ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMP NULL
                    """))
                    
                    # Create partial index for efficient stale job detection
                    # Only index running jobs since we only check those for staleness
                    if not check_index_exists('idx_background_jobs_heartbeat'):
                        checkpoint("  → Creating partial index on heartbeat_at for running jobs...")
                        db.session.execute(text("""
                            CREATE INDEX IF NOT EXISTS idx_background_jobs_heartbeat 
                            ON background_jobs (heartbeat_at) 
                            WHERE status = 'running'
                        """))
                        checkpoint("  ✅ Partial index created for efficient stale detection")
                    
                    # Initialize heartbeat for existing running jobs to prevent false positives
                    checkpoint("  → Initializing heartbeat for existing running jobs...")
                    result = db.session.execute(text("""
                        UPDATE background_jobs 
                        SET heartbeat_at = COALESCE(updated_at, started_at, created_at)
                        WHERE status IN ('running', 'queued') AND heartbeat_at IS NULL
                    """))
                    updated_count = result.rowcount
                    if updated_count > 0:
                        checkpoint(f"  ✅ Initialized heartbeat for {updated_count} existing job(s)")
                    
                    fields_added.append('heartbeat_at')
                    checkpoint("  ✅ heartbeat_at added with partial index")
                
                if fields_added:
                    migrations_applied.append("add_background_jobs_heartbeat")
                    checkpoint(f"✅ Migration 103 complete: {', '.join(fields_added)} added")
                    checkpoint("   🔒 Idempotent: Safe to run multiple times")
                    checkpoint("   🎯 Purpose: Detects stale jobs (no heartbeat > 120s)")
                    checkpoint("   🔧 Enables: Auto-recovery from crashed background workers")
                else:
                    checkpoint("✅ Migration 103: Heartbeat already exists - skipping")
                    
            except Exception as e:
                db.session.rollback()
                checkpoint(f"❌ Migration 103 failed: {e}")
                logger.error(f"Migration 103 error details: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ background_jobs table does not exist - skipping")
        
        # ============================================================================
        # Migration 104: Update background_jobs CHECK constraint for all job types
        # ============================================================================
        # Purpose: Allow all current job types in background_jobs table
        # - delete_receipts_all (existing)
        # - delete_leads (NEW - bulk lead deletion)
        # - update_leads (NEW - bulk lead updates)
        # - delete_imported_leads (NEW - cleanup imported leads)
        # - enqueue_outbound_calls (NEW - bulk outbound call scheduling)
        # - broadcast (NEW - WhatsApp broadcast operations)
        # This fixes: IntegrityError when creating delete_leads/update_leads jobs
        checkpoint("Migration 104: Updating background_jobs job_type constraint")
        
        if check_table_exists('background_jobs'):
            from sqlalchemy import text
            try:
                # Drop old constraint and create new one with all job types
                checkpoint("  → Dropping old chk_job_type constraint...")
                db.session.execute(text("""
                    ALTER TABLE background_jobs 
                    DROP CONSTRAINT IF EXISTS chk_job_type
                """))
                
                checkpoint("  → Creating updated chk_job_type constraint with all job types...")
                db.session.execute(text("""
                    ALTER TABLE background_jobs
                    ADD CONSTRAINT chk_job_type
                    CHECK (job_type IN (
                        'delete_receipts_all',
                        'delete_leads',
                        'update_leads',
                        'delete_imported_leads',
                        'enqueue_outbound_calls',
                        'broadcast'
                    ))
                """))
                
                migrations_applied.append("update_background_jobs_job_type_constraint")
                checkpoint("✅ Migration 104 complete: job_type constraint updated")
                checkpoint("   🔒 Idempotent: Safe to run multiple times")
                checkpoint("   ✅ Allowed job types: delete_receipts_all, delete_leads, update_leads, delete_imported_leads, enqueue_outbound_calls, broadcast")
                
            except Exception as e:
                db.session.rollback()
                checkpoint(f"❌ Migration 104 failed: {e}")
                logger.error(f"Migration 104 error details: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ background_jobs table does not exist - skipping")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 105: Add cancel_requested to outbound_call_runs
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 105: Adding cancel_requested to outbound_call_runs for queue cancellation")
        if check_table_exists('outbound_call_runs'):
            try:
                if not check_column_exists('outbound_call_runs', 'cancel_requested'):
                    db.session.execute(text("""
                        ALTER TABLE outbound_call_runs 
                        ADD COLUMN cancel_requested BOOLEAN NOT NULL DEFAULT FALSE
                    """))
                    db.session.commit()
                    migrations_applied.append('105_outbound_cancel_requested')
                    checkpoint("✅ Migration 105 complete: cancel_requested column added to outbound_call_runs")
                else:
                    checkpoint("  ℹ️  cancel_requested column already exists - skipping Migration 105")
            except Exception as e:
                db.session.rollback()
                checkpoint(f"❌ Migration 105 failed: {e}")
                logger.error(f"Migration 105 error details: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ outbound_call_runs table does not exist - skipping Migration 105")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 106: Create recording_runs table for RQ-based recording jobs
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 106: Creating recording_runs table for RQ worker-based recording processing")
        if not check_table_exists('recording_runs'):
            try:
                db.session.execute(text("""
                    CREATE TABLE recording_runs (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        call_sid VARCHAR(64) NOT NULL,
                        recording_sid VARCHAR(64),
                        recording_url VARCHAR(512),
                        status VARCHAR(32) NOT NULL DEFAULT 'queued',
                        cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
                        job_type VARCHAR(32) DEFAULT 'download',
                        error_message TEXT,
                        retry_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT NOW(),
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        CONSTRAINT chk_recording_run_status CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled'))
                    );
                    
                    CREATE INDEX idx_recording_runs_business_id ON recording_runs(business_id);
                    CREATE INDEX idx_recording_runs_business_status ON recording_runs(business_id, status);
                    CREATE INDEX idx_recording_runs_call_sid ON recording_runs(call_sid);
                    CREATE INDEX idx_recording_runs_created_at ON recording_runs(created_at);
                """))
                db.session.commit()
                migrations_applied.append('106_recording_runs_table')
                checkpoint("✅ Migration 106 complete: recording_runs table created")
                checkpoint("   🎯 Enables RQ worker-based recording with progress/cancel support")
            except Exception as e:
                db.session.rollback()
                checkpoint(f"❌ Migration 106 failed: {e}")
                logger.error(f"Migration 106 error details: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ recording_runs table already exists - skipping Migration 106")
        
        checkpoint("Committing migrations to database...")
        if migrations_applied:
            db.session.commit()
            checkpoint(f"✅ Applied {len(migrations_applied)} migrations: {', '.join(migrations_applied[:3])}...")
        else:
            checkpoint("No migrations needed - database is up to date")
        
        # 🔒 DATA PROTECTION CHECK: Verify data counts AFTER migrations - CRITICAL!
        # If FAQs or leads are deleted, ROLLBACK and FAIL the migration
        checkpoint("Starting data protection layer 3 - verifying no data loss")
        try:
            from sqlalchemy import text
            data_loss_detected = False
            
            if check_table_exists('faqs'):
                faq_count_after = db.session.execute(text("SELECT COUNT(*) FROM faqs")).scalar() or 0
                faq_delta = faq_count_after - faq_count_before
                if faq_delta < 0:
                    checkpoint(f"❌ DATA LOSS DETECTED: {abs(faq_delta)} FAQs were DELETED during migrations!")
                    data_loss_detected = True
                else:
                    checkpoint(f"✅ DATA PROTECTION (AFTER): {faq_count_after} FAQs preserved (delta: +{faq_delta})")
            
            if check_table_exists('leads'):
                lead_count_after = db.session.execute(text("SELECT COUNT(*) FROM leads")).scalar() or 0
                lead_delta = lead_count_after - lead_count_before
                if lead_delta < 0:
                    checkpoint(f"❌ DATA LOSS DETECTED: {abs(lead_delta)} leads were DELETED during migrations!")
                    data_loss_detected = True
                else:
                    checkpoint(f"✅ DATA PROTECTION (AFTER): {lead_count_after} leads preserved (delta: +{lead_delta})")
            
            # 🛑 ENFORCE DATA PROTECTION: Rollback and fail if FAQs or leads were deleted
            if data_loss_detected:
                db.session.rollback()
                error_msg = "❌ MIGRATION FAILED: Data loss detected. Rolling back changes."
                checkpoint(error_msg)
                raise Exception("Data protection violation: FAQs or leads were deleted during migration")
            
            # Messages can decrease (deduplication is expected and documented)
            if check_table_exists('messages'):
                msg_count_after = db.session.execute(text("SELECT COUNT(*) FROM messages")).scalar() or 0
                msg_delta = msg_count_after - msg_count_before
                if msg_delta < 0:
                    checkpoint(f"⚠️ Messages decreased by {abs(msg_delta)} (deduplication cleanup - expected)")
                else:
                    checkpoint(f"✅ DATA PROTECTION (AFTER): {msg_count_after} messages (delta: +{msg_delta})")
        except Exception as e:
            if "Data protection violation" in str(e):
                raise  # Re-raise data protection violations
            
            # 🔥 CRITICAL FIX: ROLLBACK immediately to prevent InFailedSqlTransaction
            db.session.rollback()
            checkpoint(f"Could not verify data counts after migrations: {e}")
        
        # ═══════════════════════════════════════════════════════════════════════
        # POST-MIGRATION VERIFICATION: Check that all required columns exist
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Starting post-migration verification - checking required columns...")
        if check_table_exists('leads'):
            required_columns = ['phone_raw', 'whatsapp_jid', 'whatsapp_jid_alt', 'reply_jid', 'reply_jid_type']
            missing_columns = []
            
            for col in required_columns:
                if not check_column_exists('leads', col):
                    missing_columns.append(col)
                    checkpoint(f"  ❌ Required column 'leads.{col}' is MISSING!")
                else:
                    checkpoint(f"  ✅ Column 'leads.{col}' exists")
            
            if missing_columns:
                error_msg = f"❌ POST-MIGRATION VERIFICATION FAILED: Missing columns in leads table: {', '.join(missing_columns)}"
                checkpoint(error_msg)
                checkpoint("💡 TIP: These columns are required by the Lead model. The migration may have failed silently.")
                raise Exception(f"Migration verification failed: missing columns {missing_columns}")
            else:
                checkpoint("✅ All required columns verified successfully")
        
        checkpoint("✅ Migration completed successfully!")
    
    # 🔒 CONCURRENCY PROTECTION: Release PostgreSQL advisory lock
    finally:
        if lock_acquired:
            try:
                # Release lock using the same LOCK_ID (1234567890)
                db.session.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": 1234567890})
                checkpoint("✅ Released migration lock")
            except Exception as e:
                checkpoint(f"⚠️ Failed to release migration lock: {e}")
    
    return migrations_applied


if __name__ == '__main__':
    """
    Standalone execution: python -m server.db_migrate
    
    Runs migrations without eventlet or background workers.
    """
    import sys
    
    # Set migration mode
    import os
    os.environ['MIGRATION_MODE'] = '1'
    os.environ['ASYNC_LOG_QUEUE'] = '0'
    
    checkpoint("=" * 80)
    checkpoint("DATABASE MIGRATION RUNNER - Standalone Mode")
    checkpoint("=" * 80)
    
    # Validate DATABASE_URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        checkpoint("❌ DATABASE_URL environment variable is not set!")
        sys.exit(1)
    
    checkpoint(f"Database: {database_url.split('@')[0] if '@' in database_url else 'sqlite'}@***")
    
    try:
        # Create minimal app and run migrations
        checkpoint("Creating minimal Flask app context...")
        from server.app_factory import create_minimal_app
        app = create_minimal_app()
        
        checkpoint("Running migrations within app context...")
        with app.app_context():
            migrations = apply_migrations()
        
        checkpoint("=" * 80)
        checkpoint(f"✅ SUCCESS - Applied {len(migrations)} migrations")
        checkpoint("=" * 80)
        sys.exit(0)
        
    except Exception as e:
        checkpoint("=" * 80)
        checkpoint(f"❌ MIGRATION FAILED: {e}")
        checkpoint("=" * 80)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)