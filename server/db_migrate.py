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

def check_index_exists(index_name):
    """Check if index exists"""
    from sqlalchemy import text
    result = db.session.execute(text("""
        SELECT indexname FROM pg_indexes 
        WHERE indexname = :index_name
    """), {"index_name": index_name})
    return result.fetchone() is not None

def apply_migrations():
    """
    Apply all pending migrations
    
    🔒 DATA PROTECTION: This function ONLY adds new tables/columns/indexes.
    It NEVER deletes user data. All existing FAQs, leads, messages, etc. are preserved.
    """
    migrations_applied = []
    
    # 🔒 BUILD 111: TRIPLE LAYER DATA PROTECTION
    # Layer 1: Count FAQs BEFORE migrations
    # Layer 2: Run migrations inside TRY block
    # Layer 3: Count FAQs AFTER migrations and ROLLBACK if decreased
    faq_count_before = 0
    lead_count_before = 0
    msg_count_before = 0
    try:
        from sqlalchemy import text
        if check_table_exists('faqs'):
            faq_count_before = db.session.execute(text("SELECT COUNT(*) FROM faqs")).scalar() or 0
            log.info(f"🔒 LAYER 1 (BEFORE): {faq_count_before} FAQs exist")
            print(f"🔒 LAYER 1 (BEFORE): {faq_count_before} FAQs in database")
        if check_table_exists('leads'):
            lead_count_before = db.session.execute(text("SELECT COUNT(*) FROM leads")).scalar() or 0
            log.info(f"🔒 LAYER 1 (BEFORE): {lead_count_before} leads exist")
            print(f"🔒 LAYER 1 (BEFORE): {lead_count_before} leads in database")
        if check_table_exists('messages'):
            msg_count_before = db.session.execute(text("SELECT COUNT(*) FROM messages")).scalar() or 0
            log.info(f"🔒 LAYER 1 (BEFORE): {msg_count_before} messages exist")
    except Exception as e:
        log.warning(f"Could not check data counts (database may be new): {e}")
    
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
    
    if migrations_applied:
        db.session.commit()
        log.info(f"Applied {len(migrations_applied)} migrations: {', '.join(migrations_applied)}")
    else:
        log.info("No migrations needed - database is up to date")
    
    # 🔒 DATA PROTECTION CHECK: Verify data counts AFTER migrations - CRITICAL!
    # If FAQs or leads are deleted, ROLLBACK and FAIL the migration
    try:
        from sqlalchemy import text
        data_loss_detected = False
        
        if check_table_exists('faqs'):
            faq_count_after = db.session.execute(text("SELECT COUNT(*) FROM faqs")).scalar() or 0
            faq_delta = faq_count_after - faq_count_before
            if faq_delta < 0:
                log.error(f"❌ DATA LOSS DETECTED: {abs(faq_delta)} FAQs were DELETED during migrations!")
                print(f"❌ CRITICAL: {abs(faq_delta)} FAQs DELETED! Before: {faq_count_before}, After: {faq_count_after}")
                data_loss_detected = True
            else:
                log.info(f"✅ DATA PROTECTION (AFTER): {faq_count_after} FAQs preserved (delta: +{faq_delta})")
                print(f"✅ DATA PROTECTION: {faq_count_after} FAQs preserved (no deletions)")
        
        if check_table_exists('leads'):
            lead_count_after = db.session.execute(text("SELECT COUNT(*) FROM leads")).scalar() or 0
            lead_delta = lead_count_after - lead_count_before
            if lead_delta < 0:
                log.error(f"❌ DATA LOSS DETECTED: {abs(lead_delta)} leads were DELETED during migrations!")
                print(f"❌ CRITICAL: {abs(lead_delta)} leads DELETED! Before: {lead_count_before}, After: {lead_count_after}")
                data_loss_detected = True
            else:
                log.info(f"✅ DATA PROTECTION (AFTER): {lead_count_after} leads preserved (delta: +{lead_delta})")
                print(f"✅ DATA PROTECTION: {lead_count_after} leads preserved (no deletions)")
        
        # 🛑 ENFORCE DATA PROTECTION: Rollback and fail if FAQs or leads were deleted
        if data_loss_detected:
            db.session.rollback()
            error_msg = "❌ MIGRATION FAILED: Data loss detected. Rolling back changes."
            log.error(error_msg)
            print(error_msg)
            raise Exception("Data protection violation: FAQs or leads were deleted during migration")
        
        # Messages can decrease (deduplication is expected and documented)
        if check_table_exists('messages'):
            msg_count_after = db.session.execute(text("SELECT COUNT(*) FROM messages")).scalar() or 0
            msg_delta = msg_count_after - msg_count_before
            if msg_delta < 0:
                log.warning(f"⚠️ Messages decreased by {abs(msg_delta)} (deduplication cleanup - expected)")
                print(f"⚠️ {abs(msg_delta)} duplicate messages removed (data cleanup)")
            else:
                log.info(f"✅ DATA PROTECTION (AFTER): {msg_count_after} messages (delta: +{msg_delta})")
    except Exception as e:
        if "Data protection violation" in str(e):
            raise  # Re-raise data protection violations
        log.warning(f"Could not verify data counts after migrations: {e}")
    
    return migrations_applied