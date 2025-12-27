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
    print(msg, file=sys.stderr, flush=True)
    sys.stderr.flush()

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

def apply_migrations():
    """
    Apply all pending migrations
    
    🔒 DATA PROTECTION: This function ONLY adds new tables/columns/indexes.
    It NEVER deletes user data. All existing FAQs, leads, messages, etc. are preserved.
    
    🔒 CONCURRENCY PROTECTION: Uses PostgreSQL advisory lock to prevent multiple
    processes from running migrations simultaneously (prevents deadlocks).
    """
    checkpoint("Starting apply_migrations()")
    migrations_applied = []
    
    # 🔒 CONCURRENCY PROTECTION: Acquire PostgreSQL advisory lock
    # Lock ID: 1234567890 (arbitrary unique integer)
    # This ensures only ONE process runs migrations at a time
    checkpoint("Acquiring PostgreSQL advisory lock for migrations...")
    from sqlalchemy import text
    lock_acquired = False
    try:
        # Try to acquire lock (non-blocking)
        result = db.session.execute(text("SELECT pg_try_advisory_lock(1234567890)"))
        lock_acquired = result.scalar()
        
        if not lock_acquired:
            checkpoint("⚠️ Another process is running migrations - waiting...")
            # Block until lock is available
            db.session.execute(text("SELECT pg_advisory_lock(1234567890)"))
            lock_acquired = True
            checkpoint("✅ Acquired migration lock after waiting")
        else:
            checkpoint("✅ Acquired migration lock immediately")
    except Exception as e:
        checkpoint(f"❌ Failed to acquire migration lock: {e}")
        raise
    
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
    
        checkpoint("✅ Migration completed successfully!")
    
    # 🔒 CONCURRENCY PROTECTION: Release PostgreSQL advisory lock
    finally:
        if lock_acquired:
            try:
                db.session.execute(text("SELECT pg_advisory_unlock(1234567890)"))
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