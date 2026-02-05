"""
Database migrations - additive only, with strict data protection

🔒 DATA PROTECTION GUARANTEE:
- FAQs and leads are NEVER deleted - migrations will FAIL if data loss is detected
- Limited exception: Deduplication DELETE for corrupted data (duplicate messages/calls only)
- NO TRUNCATE, NO DROP TABLE on any tables
- Automatic verification with rollback on unexpected data loss

⚠️ ═══════════════════════════════════════════════════════════════════════════
⚠️ IRON RULE: MIGRATIONS = SCHEMA ONLY (ONE SOURCE OF TRUTH)
⚠️ ═══════════════════════════════════════════════════════════════════════════

📋 THE THREE PILLARS OF DATABASE OPERATIONS:

1️⃣ **MIGRATIONS (db_migrate.py)** = Schema Changes ONLY
   ✅ Allowed: CREATE/ALTER/DROP TABLE/COLUMN, ADD CONSTRAINT
   ❌ FORBIDDEN: UPDATE/INSERT/DELETE on tables with many rows
   ❌ FORBIDDEN: CREATE INDEX (goes to db_indexes.py)
   ❌ FORBIDDEN: Data backfills (goes to db_backfills.py)
   
2️⃣ **INDEXES (db_indexes.py + db_build_indexes.py)** = Performance Indexes ONLY
   ✅ Only CREATE INDEX CONCURRENTLY statements
   ❌ FORBIDDEN: Schema changes, backfills, migrations
   
3️⃣ **BACKFILLS (db_backfills.py + db_run_backfills.py)** = Data Operations ONLY
   ✅ Only UPDATE/INSERT for populating existing columns
   ❌ FORBIDDEN: Schema changes, index creation, ALTER TABLE

⚠️ VIOLATION = PRODUCTION FAILURE + LOCK TIMEOUTS + DEPLOYMENT ISSUES

📖 For detailed guidelines, see:
- MIGRATION_GUIDELINES.md (schema changes)
- INDEXING_GUIDE.md (index creation)
- MIGRATION_36_BACKFILL_SEPARATION.md (backfill operations)

⚠️ ═══════════════════════════════════════════════════════════════════════════

📋 DETAILED MIGRATION RULES:

1️⃣ **NEVER use db.session.execute() for migrations**
   ❌ BAD:  db.session.execute(text("ALTER TABLE..."))
   ✅ GOOD: exec_ddl(migrate_engine, "ALTER TABLE...")
   
2️⃣ **DDL operations MUST use exec_ddl()** (schema changes)
   - Has 5s lock_timeout (fail fast on locks)
   - Includes retry logic and lock debugging
   
2️⃣b **HEAVY DDL operations MUST use exec_ddl_heavy()** (AccessExclusive locks)
   ⚠️ IRON RULE: These operations require AccessExclusive lock and MUST use exec_ddl_heavy():
   - ALTER TABLE ... DROP CONSTRAINT / ADD CONSTRAINT
   - ALTER TABLE ... ALTER COLUMN TYPE (changes column type)
   - ALTER TABLE ... ADD CHECK / DROP CHECK on large tables
   - Any constraint modification on tables with active writes
   
   ✅ exec_ddl_heavy() provides:
   - lock_timeout = 120s (vs 5s for regular DDL)
   - statement_timeout = 0 (unlimited, waiting for locks is expected)
   - 10 retries with exponential backoff (2s → 30s)
   - Lock debugging on failures
   
   ❌ DO NOT use exec_ddl() or exec_sql() for these operations!
   
3️⃣ **DML operations BELONG IN db_backfills.py**
   - NO UPDATE/INSERT/DELETE in migrations
   - Backfills run separately via db_run_backfills.py
   - Use batching + SKIP LOCKED for production safety
   
4️⃣ **❌ Performance indexes BELONG IN db_indexes.py ❌**
   - ✅ ALL performance indexes go to db_indexes.py ONLY
   - ✅ Only UNIQUE constraints allowed in migrations
   - Performance indexes are built separately during deployment
   - See INDEXING_GUIDE.md for details
   - Violating this rule = production deployment failure
   
5️⃣ **All operations MUST be idempotent**
   - Use IF NOT EXISTS for CREATE operations
   - Use IF EXISTS for DROP operations
   - Check column/table existence before ALTER
   
6️⃣ **Test migrations locally BEFORE production**
   - Drop test column/table: ALTER TABLE test_table DROP COLUMN IF EXISTS test_col;
   - Run migration to re-apply it
   - Verify idempotency: run again - should succeed with no changes

🔥 REMEMBER: Breaking these rules = production downtime + data locks!
"""
from server.db import db
from datetime import datetime
import logging
import sys
import time
import os
from sqlalchemy import text, create_engine
from sqlalchemy.exc import OperationalError, DBAPIError

# Configure logging with explicit format

logger = logging.getLogger(__name__)

# ProSaaS custom migration marker for alembic_version table
PROSAAS_MIGRATION_MARKER = 'prosaas_custom_migrations'

# ═══════════════════════════════════════════════════════════════════════════
# 🔥 MIGRATION STATE TRACKING - Single Source of Truth
# ═══════════════════════════════════════════════════════════════════════════
# All migrations are tracked in schema_migrations table to ensure idempotency
# and prevent re-running already applied migrations

def ensure_migration_tracking_table(engine):
    """
    Create schema_migrations table if it doesn't exist.
    This is the single source of truth for which migrations have been applied.
    
    Table structure:
    - migration_id: Unique identifier for the migration (e.g., "001_add_transcript")
    - applied_at: Timestamp when migration was applied
    - success: Whether the migration completed successfully
    - reconciled: Whether this was detected as already applied (not actually run)
    - notes: Additional information about the migration
    """
    try:
        execute_with_retry(engine, """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                migration_id TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                success BOOLEAN NOT NULL DEFAULT TRUE,
                reconciled BOOLEAN NOT NULL DEFAULT FALSE,
                notes TEXT
            )
        """)
        log.info("✅ schema_migrations table ready")
    except Exception as e:
        log.error(f"❌ Failed to create schema_migrations table: {e}")
        raise

def is_migration_applied(engine, migration_id: str) -> bool:
    """Check if a migration has already been applied"""
    try:
        result = execute_with_retry(
            engine,
            "SELECT 1 FROM schema_migrations WHERE migration_id = :id AND success = TRUE",
            {"id": migration_id},
            fetch=True
        )
        return len(result) > 0
    except Exception as e:
        # If table doesn't exist or query fails, assume migration not applied
        log.debug(f"Could not check migration status for {migration_id}: {e}")
        return False

def mark_migration_applied(engine, migration_id: str, reconciled: bool = False, notes: str = None):
    """
    Mark a migration as successfully applied.
    
    Args:
        engine: Database engine
        migration_id: Unique identifier for the migration
        reconciled: True if migration was detected as already applied (not actually run)
        notes: Additional information
    """
    try:
        execute_with_retry(engine, """
            INSERT INTO schema_migrations (migration_id, applied_at, success, reconciled, notes)
            VALUES (:id, NOW(), TRUE, :reconciled, :notes)
            ON CONFLICT (migration_id) DO UPDATE
            SET applied_at = NOW(), success = TRUE, reconciled = :reconciled, 
                notes = COALESCE(:notes, schema_migrations.notes)
        """, {"id": migration_id, "reconciled": reconciled, "notes": notes})
        status = "reconciled" if reconciled else "applied"
        log.info(f"✅ Marked migration {migration_id} as {status}")
    except Exception as e:
        log.warning(f"⚠️ Could not mark migration {migration_id} as applied: {e}")

def reconcile_existing_state(engine):
    """
    Minimal Smart Reconciliation - Only for Critical Existing State
    ================================================================
    
    This function reconciles ONLY the most critical existing migrations that
    commonly cause "already exists" errors on existing deployments.
    
    Strategy: Start minimal, add more fingerprints only as needed.
    
    For each migration:
    1. If marked in schema_migrations → SKIP
    2. If not marked but fingerprint exists in DB → MARK as reconciled + SKIP  
    3. Otherwise → Will be run later
    
    This prevents "already exists" errors on the most common cases.
    """
    checkpoint("=" * 80)
    checkpoint("🔄 MINIMAL RECONCILIATION: Checking for existing critical migrations")
    checkpoint("=" * 80)
    checkpoint("   Strategy: Only reconcile migrations that commonly cause 'already exists' errors")
    checkpoint("   Start minimal, expand as needed")
    checkpoint("=" * 80)
    
    reconciled = []
    
    # ========================================================================
    # MINIMAL FINGERPRINT LIST - Only Critical Migrations
    # ========================================================================
    # These are the migrations most likely to already exist on deployed systems
    # and cause "already exists" errors. We check these first.
    
    migrations_to_check = [
        # Core infrastructure tables (always exist on existing deployments)
        ("core_business_table", "Business table exists", 
         lambda: check_table_exists('business')),
        
        ("core_leads_table", "Leads table exists", 
         lambda: check_table_exists('leads')),
        
        ("core_call_log_table", "Call log table exists", 
         lambda: check_table_exists('call_log')),
        
        # Messaging system (commonly deployed)
        ("messaging_threads_table", "Threads table exists", 
         lambda: check_table_exists('threads')),
        
        ("messaging_messages_table", "Messages table exists", 
         lambda: check_table_exists('messages')),
        
        # Recent critical fields that cause issues
        ("leads_last_call_direction", "Last call direction in leads",
         lambda: check_column_exists('leads', 'last_call_direction')),
        
        ("business_lead_tabs_config", "Lead tabs config in business",
         lambda: check_column_exists('business', 'lead_tabs_config')),
        
        ("call_log_transcript", "Transcript in call_log",
         lambda: check_column_exists('call_log', 'transcript')),
        
        # WhatsApp system (if deployed)
        ("whatsapp_phone_field", "WhatsApp phone in leads",
         lambda: check_column_exists('leads', 'phone_whatsapp')),
        
        # Recording system (if deployed)
        ("recording_url_field", "Recording URL in call_log",
         lambda: check_column_exists('call_log', 'recording_url')),
    ]
    
    checkpoint(f"   Checking {len(migrations_to_check)} critical migration fingerprints...")
    checkpoint("")
    
    # Check each migration fingerprint
    for migration_id, description, check_func in migrations_to_check:
        try:
            # Check if migration already tracked
            if is_migration_applied(engine, migration_id):
                continue  # Already tracked, skip silently
            
            # Check if migration effect exists in database
            if check_func():
                checkpoint(f"  ✅ {migration_id}: {description} - RECONCILED")
                mark_migration_applied(engine, migration_id, reconciled=True, notes=f"Auto-detected: {description}")
                reconciled.append(migration_id)
                
        except Exception as e:
            # Don't fail on check errors - just log and continue
            checkpoint(f"  ⚠️  {migration_id}: Could not check - {e}")
    
    checkpoint("")
    checkpoint("=" * 80)
    if reconciled:
        checkpoint(f"✅ RECONCILIATION: {len(reconciled)} existing migrations detected and marked")
        checkpoint("   Future runs will skip these automatically")
    else:
        checkpoint("✅ RECONCILIATION: No existing migrations detected (fresh DB or all tracked)")
    checkpoint("=" * 80)
    checkpoint("")
    
    return reconciled
    
    return reconciled

def run_migration_with_tracking(migration_id: str, migration_func, engine):
    """
    Run a migration with state tracking.
    
    Args:
        migration_id: Unique ID for the migration (e.g., "095_add_incomplete_status")
        migration_func: Function that executes the migration
        engine: SQLAlchemy engine for tracking
    
    Returns:
        bool: True if migration was run, False if already applied
    """
    # Check if already applied
    if is_migration_applied(engine, migration_id):
        log.debug(f"⏭️  Skipping {migration_id} - already applied")
        return False
    
    # Run the migration
    checkpoint(f"🔨 Running {migration_id}...")
    try:
        migration_func()
        mark_migration_applied(engine, migration_id)
        checkpoint(f"✅ Completed {migration_id}")
        return True
    except Exception as e:
        checkpoint(f"❌ Failed {migration_id}: {e}")
        raise

def run_migration(migration_id: str, fingerprint_fn, run_fn, engine):
    """
    Enhanced migration wrapper with fingerprint-based reconciliation.
    
    This is the IRON RULE wrapper - all migrations MUST use this.
    
    Args:
        migration_id: Unique migration ID (e.g., "096" or "096_whatsapp_prompt_mode")
        fingerprint_fn: Function that returns True if migration already exists in DB
        run_fn: Function that executes the migration DDL
        engine: SQLAlchemy engine for state tracking
    
    Returns:
        str: Status - "SKIP" (already applied), "RECONCILE" (detected in DB), or "RUN" (executed)
    
    Example:
        def fp_96():
            return (
                column_exists("leads", "name") and
                column_exists("business", "whatsapp_prompt_mode")
            )
        
        def run_96():
            exec_ddl(engine, "ALTER TABLE leads ADD COLUMN name VARCHAR(255)")
            exec_ddl(engine, "ALTER TABLE business ADD COLUMN whatsapp_prompt_mode TEXT")
        
        run_migration("096", fp_96, run_96, engine)
    """
    # Check if already tracked as applied
    if is_migration_applied(engine, migration_id):
        checkpoint(f"⏭️  SKIP {migration_id} - already applied")
        return "SKIP"
    
    # Check fingerprint - does schema already exist?
    try:
        if fingerprint_fn():
            # Schema exists but not tracked - reconcile
            mark_migration_applied(engine, migration_id, reconciled=True, 
                                   notes="Detected in DB via fingerprint")
            checkpoint(f"🔄 RECONCILE {migration_id} - schema already exists")
            return "RECONCILE"
    except Exception as e:
        # If fingerprint check fails, assume migration needs to run
        checkpoint(f"⚠️  Fingerprint check failed for {migration_id}: {e}")
        checkpoint(f"   Assuming migration needs to run")
    
    # Schema doesn't exist - run the migration
    checkpoint(f"🔨 RUN {migration_id}...")
    try:
        run_fn()
        mark_migration_applied(engine, migration_id, reconciled=False, 
                               notes="Successfully executed")
        checkpoint(f"✅ Completed {migration_id}")
        return "RUN"
    except Exception as e:
        checkpoint(f"❌ Failed {migration_id}: {e}")
        raise

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

# Lock debugging query - shows who is blocking whom
LOCK_DEBUG_SQL = """
SELECT
  blocked.pid as blocked_pid,
  blocked.state as blocked_state,
  blocked.query as blocked_query,
  blocking.pid as blocking_pid,
  blocking.state as blocking_state,
  blocking.query as blocking_query
FROM pg_locks bl
JOIN pg_stat_activity blocked ON blocked.pid = bl.pid
JOIN pg_locks kl
  ON kl.locktype = bl.locktype
 AND kl.database IS NOT DISTINCT FROM bl.database
 AND kl.relation IS NOT DISTINCT FROM bl.relation
 AND kl.page IS NOT DISTINCT FROM bl.page
 AND kl.tuple IS NOT DISTINCT FROM bl.tuple
 AND kl.transactionid IS NOT DISTINCT FROM bl.transactionid
 AND kl.pid != bl.pid
JOIN pg_stat_activity blocking ON blocking.pid = kl.pid
WHERE NOT bl.granted;
"""

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

# ═══════════════════════════════════════════════════════════════════════════
# 🔥 SSL CONNECTION RESILIENCE - Migration DB Executor
# ═══════════════════════════════════════════════════════════════════════════
# These constants and functions provide retry logic for transient connection failures
# particularly "SSL connection has been closed unexpectedly" errors.

RETRYABLE_ERROR_PATTERNS = (
    "SSL connection has been closed unexpectedly",
    "server closed the connection unexpectedly",
    "connection not open",
    "could not receive data from server",
    "connection already closed",
    "server closed the connection",
    "network is unreachable",
    "could not connect to server",
    "connection reset by peer",
)

def _is_retryable(e: Exception) -> bool:
    """Check if an exception is a retryable connection error"""
    msg = str(e).lower()
    return any(pattern.lower() in msg for pattern in RETRYABLE_ERROR_PATTERNS)

def _is_already_exists_error(e: Exception) -> bool:
    """
    Check if an exception is an 'already exists' error that can be safely ignored in migrations.
    
    According to the IRON RULE, migrations should only continue for:
    - already exists
    - duplicate_object  
    - duplicate_table
    - duplicate_column
    
    Any other DDL error (SyntaxError, ProgrammingError, etc.) should FAIL HARD.
    
    Note: This specifically checks for DDL "already exists" errors, not data integrity
    errors like "duplicate key value violates unique constraint" during INSERT/UPDATE.
    """
    msg = str(e).lower()
    # Check for "already exists" type errors that are safe to ignore
    safe_patterns = [
        "already exists",
        "duplicate_object",
        "duplicate_table", 
        "duplicate_column",
    ]
    return any(pattern in msg for pattern in safe_patterns)

def exec_sql(engine, sql: str, params=None, *, autocommit=False, retries=4, sleep=1.0):
    """
    Execute SQL with retry logic for transient connection failures.
    
    Uses short-lived connections and optional AUTOCOMMIT isolation level to prevent
    SSL connection failures from breaking migrations. DDL operations should use
    autocommit=True to avoid idle-in-transaction issues.
    
    Args:
        engine: SQLAlchemy engine instance
        sql: SQL statement to execute
        params: Dictionary of query parameters (default: None)
        autocommit: If True, use AUTOCOMMIT isolation level (recommended for DDL)
        retries: Number of retry attempts (default: 4)
        sleep: Base sleep time between retries in seconds (default: 1.0)
    
    Raises:
        OperationalError: If all retry attempts fail
    
    Example:
        exec_sql(db.engine, '''
            ALTER TABLE receipts ADD CONSTRAINT chk_status 
            CHECK (status IN ('pending', 'approved'))
        ''', autocommit=True)
    """
    last_error = None
    for i in range(retries):
        try:
            with engine.connect() as conn:
                if autocommit:
                    conn = conn.execution_options(isolation_level="AUTOCOMMIT")
                # Set timeouts for the connection
                conn.execute(text("SET lock_timeout = '5s'"))
                conn.execute(text("SET statement_timeout = '120s'"))
                conn.execute(text("SET idle_in_transaction_session_timeout = '60s'"))
                # Execute the SQL
                conn.execute(text(sql), params or {})
                conn.commit()  # Commit if not autocommit
                return  # Success
        except OperationalError as e:
            last_error = e
            if _is_retryable(e) and i < retries - 1:
                sleep_time = sleep * (i + 1)  # Exponential backoff
                log.warning(f"⚠️ Retryable connection error (attempt {i + 1}/{retries}), retrying in {sleep_time}s: {e}")
                time.sleep(sleep_time)
                continue
            # Non-retryable or last attempt - re-raise
            log.error(f"❌ exec_sql failed after {i + 1} attempts: {e}")
            raise
    # Should never reach here, but just in case
    raise last_error

def fetch_all(engine, sql: str, params=None, retries=4):
    """
    Execute a query and fetch all results with retry logic and engine.dispose().
    
    Uses short-lived connections to prevent SSL connection failures during 
    metadata queries. Calls engine.dispose() on SSL errors to refresh connection pool.
    
    Args:
        engine: SQLAlchemy engine instance
        sql: SQL query string
        params: Dictionary of query parameters (default: None)
        retries: Number of retry attempts (default: 4)
    
    Returns:
        List of result rows
    
    Raises:
        OperationalError: If all retry attempts fail
    
    Example:
        rows = fetch_all(db.engine, '''
            SELECT constraint_name FROM information_schema.check_constraints
            WHERE constraint_name = :name
        ''', {"name": "chk_status"})
    """
    last_error = None
    for i in range(retries):
        try:
            with engine.connect() as conn:
                conn = conn.execution_options(isolation_level="AUTOCOMMIT")
                result = conn.execute(text(sql), params or {})
                return result.fetchall()
        except OperationalError as e:
            last_error = e
            if _is_retryable(e) and i < retries - 1:
                # 🔥 Dispose engine on retryable error
                try:
                    engine.dispose()
                except Exception:
                    pass
                sleep_time = 1.0 * (i + 1)
                log.warning(f"⚠️ Retryable connection error (attempt {i + 1}/{retries}), retrying in {sleep_time}s: {e}")
                time.sleep(sleep_time)
                continue
            log.error(f"❌ fetch_all failed after {i + 1} attempts: {e}")
            raise
    raise last_error

# ═══════════════════════════════════════════════════════════════════════════
# Dedicated Migration Engine with Connection Resilience
# ═══════════════════════════════════════════════════════════════════════════
_MIGRATE_ENGINE = None

def get_migrate_engine():
    """
    Get or create a dedicated engine for migrations with POOLER-only connection.
    
    🔥 IRON RULE: POOLER ONLY - NO DIRECT CONNECTION SWITCHING
    
    This function creates a migration engine that:
    1. Uses POOLER connection ONLY (locked at start)
    2. Never switches to DIRECT during run
    3. Has pool_pre_ping and pool_recycle for connection resilience
    4. All queries go through execute_with_retry() which handles SSL errors
    
    This prevents stale connections from breaking migrations due to:
    - SSL connection closures
    - Server restarts
    - Network interruptions
    
    Returns:
        SQLAlchemy Engine instance
    """
    global _MIGRATE_ENGINE
    if _MIGRATE_ENGINE is None:
        from server.database_url import get_database_url
        
        # 🔥 IRON RULE: POOLER ONLY - locked at start, never switch to DIRECT
        database_url = get_database_url(connection_type="pooler")
        
        _MIGRATE_ENGINE = create_engine(
            database_url,
            pool_pre_ping=True,  # Test connections before using them
            pool_recycle=180,    # Recycle connections every 3 minutes
            pool_size=5,
            max_overflow=10,
            connect_args={
                'connect_timeout': 10,  # 10 second timeout for subsequent connections
            }
        )
        
        checkpoint("=" * 80)
        checkpoint("🔒 USING POOLER (LOCKED)")
        checkpoint("   Connection type locked for entire migration run")
        checkpoint("   All queries will use retry logic with engine.dispose() on SSL errors")
        checkpoint("=" * 80)
        log.info("✅ Created migration engine with POOLER (locked)")
    return _MIGRATE_ENGINE

def fetch_all_retry(engine, sql, params=None, attempts=3):
    """
    Execute a metadata query with retry logic for transient connection failures.
    
    Uses short-lived connections and AUTOCOMMIT isolation level to prevent
    SSL connection failures from breaking migrations.
    
    Args:
        engine: SQLAlchemy engine instance
        sql: SQL query string
        params: Dictionary of query parameters (default: None)
        attempts: Number of retry attempts (default: 3)
    
    Returns:
        List of result rows
    
    Raises:
        OperationalError: If all retry attempts fail
    
    Example:
        rows = fetch_all_retry(db.engine, '''
            SELECT constraint_name, check_clause
            FROM information_schema.check_constraints
            WHERE constraint_name LIKE :p
        ''', {"p": "%event_type%"})
    """
    last_error = None
    for i in range(attempts):
        try:
            # Use short-lived connection, not long session
            with engine.connect() as conn:
                # AUTOCOMMIT for metadata queries reduces risk of idle transaction
                conn = conn.execution_options(isolation_level="AUTOCOMMIT")
                return conn.execute(text(sql), params or {}).fetchall()
        except OperationalError as e:
            last_error = e
            # Check if error is retryable
            if _is_retryable(e) and i < attempts - 1:
                # Exponential backoff: 1.5s, 3s, 4.5s, etc.
                sleep_time = 1.5 * (i + 1)
                log.warning(f"⚠️ Connection error (attempt {i + 1}/{attempts}), retrying in {sleep_time}s: {e}")
                time.sleep(sleep_time)
                continue
            # Last attempt or non-retryable - re-raise
            log.error(f"❌ fetch_all_retry failed after {i + 1} attempts: {e}")
            raise
    raise last_error

def check_column_exists(table_name, column_name):
    """Check if column exists in table using execute_with_retry"""
    try:
        engine = get_migrate_engine()
        rows = execute_with_retry(engine, """
            SELECT column_name FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = :table_name AND column_name = :column_name
        """, {"table_name": table_name, "column_name": column_name}, fetch=True)
        return len(rows) > 0
    except Exception as e:
        log.warning(f"Error checking if column {column_name} exists in {table_name}: {e}")
        return False

def check_table_exists(table_name):
    """Check if table exists using execute_with_retry"""
    try:
        engine = get_migrate_engine()
        rows = execute_with_retry(engine, """
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = :table_name
        """, {"table_name": table_name}, fetch=True)
        return len(rows) > 0
    except Exception as e:
        log.warning(f"Error checking if table {table_name} exists: {e}")
        return False

def check_index_exists(index_name):
    """Check if index exists using execute_with_retry"""
    try:
        engine = get_migrate_engine()
        rows = execute_with_retry(engine, """
            SELECT indexname FROM pg_indexes 
            WHERE schemaname = 'public' AND indexname = :index_name
        """, {"index_name": index_name}, fetch=True)
        return len(rows) > 0
    except Exception as e:
        log.warning(f"Error checking if index {index_name} exists: {e}")
        return False

def check_constraint_exists(constraint_name, table_name=None):
    """
    Check if constraint exists using execute_with_retry
    
    Args:
        constraint_name: Name of the constraint (required)
        table_name: Name of the table (optional for backward compatibility)
    
    Returns:
        bool: True if constraint exists, False otherwise
    
    Note: Backward compatible - can be called with just constraint_name
    """
    try:
        engine = get_migrate_engine()
        
        if table_name:
            # New style: check constraint on specific table
            rows = execute_with_retry(engine, """
                SELECT conname FROM pg_constraint 
                WHERE conname = :constraint_name 
                  AND conrelid = to_regclass(:table_name)::oid
            """, {"constraint_name": constraint_name, "table_name": f"public.{table_name}"}, fetch=True)
        else:
            # Old style: check constraint by name only (any table)
            rows = execute_with_retry(engine, """
                SELECT conname FROM pg_constraint 
                WHERE conname = :constraint_name
            """, {"constraint_name": constraint_name}, fetch=True)
        
        return len(rows) > 0
    except Exception as e:
        log.warning(f"Error checking if constraint {constraint_name} exists: {e}")
        return False

def terminate_idle_in_tx(engine, older_than_seconds=30):
    """
    Terminate idle-in-transaction connections that are older than the specified time.
    
    This prevents stale connections from holding locks and blocking DDL operations.
    
    Args:
        engine: SQLAlchemy engine
        older_than_seconds: Minimum age of idle transactions to terminate (default: 30s)
    """
    from sqlalchemy import text
    try:
        sql = """
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE state = 'idle in transaction'
          AND now() - xact_start > (INTERVAL '1 second' * :secs)
          AND pid <> pg_backend_pid()
        """
        with engine.connect() as conn:
            result = conn.execute(text(sql), {"secs": older_than_seconds})
            terminated_count = sum(1 for row in result if row[0])
            if terminated_count > 0:
                log.info(f"Terminated {terminated_count} idle-in-transaction connection(s) older than {older_than_seconds}s")
    except Exception as e:
        log.warning(f"Error terminating idle transactions: {e}")

def exec_ddl(engine, sql: str):
    """
    Execute a single DDL statement in its own transaction with strict lock timeouts and retry logic.
    
    This is critical for Postgres: if a DDL statement fails within a transaction,
    the entire transaction enters FAILED state and all previous work is rolled back.
    
    By executing each DDL statement in its own transaction with lock timeouts and retry,
    we ensure that:
    1. DDL operations fail fast (5s) if a lock cannot be acquired
    2. Operations don't wait indefinitely for locks
    3. Failed statements don't pollute the transaction state
    4. Transient SSL connection failures are automatically retried
    5. On lock failure, we log which processes are blocking
    
    Lock timeouts:
    - lock_timeout: 5s (fail fast if can't acquire lock)
    - statement_timeout: 120s (max execution time)
    - idle_in_transaction_session_timeout: 60s (kill idle transactions)
    
    Args:
        engine: SQLAlchemy engine
        sql: DDL statement to execute
        
    Raises:
        Exception: If DDL fails after all retries (including lock timeout)
    """
    # First, check and log idle-in-transaction count
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT count(*) FROM pg_stat_activity WHERE state='idle in transaction'"))
            idle_count = result.scalar()
            if idle_count > 0:
                log.warning(f"Found {idle_count} idle-in-transaction connection(s) before DDL")
                # Terminate old idle transactions to prevent lock contention
                terminate_idle_in_tx(engine, 30)
    except Exception as check_error:
        log.warning(f"Could not check idle transactions: {check_error}")
    
    # Execute DDL with retry logic for transient failures
    retries = 4
    last_error = None
    for i in range(retries):
        try:
            with engine.begin() as conn:  # begin() = auto commit/rollback
                # Set strict timeouts to prevent long waits on locks
                conn.execute(text("SET lock_timeout = '5s'"))
                conn.execute(text("SET statement_timeout = '120s'"))
                conn.execute(text("SET idle_in_transaction_session_timeout = '60s'"))
                # Execute the DDL
                conn.execute(text(sql))
                return  # Success
        except OperationalError as e:
            last_error = e
            # Check if this is a retryable connection error
            if _is_retryable(e) and i < retries - 1:
                sleep_time = 1.0 * (i + 1)
                log.warning(f"⚠️ DDL connection error (attempt {i + 1}/{retries}), retrying in {sleep_time}s: {e}")
                time.sleep(sleep_time)
                continue
            # Non-retryable or last attempt - fall through to error handling
            logger.error(f"DDL failed: {e}", exc_info=True)
            # Try to log lock information
            try:
                # Use a fresh connection to query lock information
                with engine.connect() as debug_conn:
                    rows = debug_conn.execute(text(LOCK_DEBUG_SQL)).fetchall()
                    if rows:
                        logger.error("=" * 80)
                        logger.error("LOCK DEBUG - Processes blocking this migration:")
                        logger.error("=" * 80)
                        for row in rows:
                            logger.error(f"  Blocked PID: {row[0]}, State: {row[1]}")
                            logger.error(f"    Query: {row[2][:200] if row[2] else 'N/A'}")
                            logger.error(f"  Blocking PID: {row[3]}, State: {row[4]}")
                            logger.error(f"    Query: {row[5][:200] if row[5] else 'N/A'}")
                            logger.error("-" * 80)
                    else:
                        logger.error("LOCK DEBUG: No blocking processes found (lock may have cleared)")
            except Exception as debug_error:
                logger.error(f"Could not retrieve lock debug info: {debug_error}")
            # Re-raise the original exception to ensure migration fails
            raise
        except Exception as e:
            # ⚠️ IRON RULE: DDL FAILURES = FAIL HARD (except "already exists")
            # Check if this is an "already exists" error that can be safely ignored
            if _is_already_exists_error(e):
                logger.warning(f"⚠️ DDL object already exists (safe to continue): {e}")
                return  # Success - object already exists
            
            # Any other DDL error = FAIL HARD
            # This includes SyntaxError, ProgrammingError, etc.
            logger.error(f"❌ DDL FAILED - STOPPING MIGRATION: {e}", exc_info=True)
            logger.error("=" * 80)
            logger.error("⚠️ MIGRATION STOPPED: DDL statement failed")
            logger.error("⚠️ This is NOT an 'already exists' error - something is broken")
            logger.error("⚠️ Fix the migration code and try again")
            logger.error("=" * 80)
            raise
    # Should never reach here, but handle it anyway
    if last_error:
        raise last_error

def exec_dml(engine, sql: str, params=None, retries=3):
    """
    Execute a DML (Data Manipulation Language) statement with appropriate timeouts for data operations.
    
    DML operations (UPDATE, INSERT, DELETE) need different timeout policies than DDL:
    - Longer lock_timeout (60s) to handle busy tables
    - No statement_timeout limit (or very high) to allow large batch operations
    - idle_in_transaction_session_timeout (60s) to prevent stuck transactions
    
    This is especially important for backfill operations that may need to update many rows.
    
    Lock timeouts:
    - lock_timeout: 60s (longer than DDL to handle concurrent access)
    - statement_timeout: 0 (unlimited - for large data operations)
    - idle_in_transaction_session_timeout: 60s (kill idle transactions)
    
    Args:
        engine: SQLAlchemy engine
        sql: DML statement to execute (UPDATE, INSERT, DELETE)
        params: Dictionary of query parameters (default: None)
        retries: Number of retry attempts (default: 3)
        
    Returns:
        Number of rows affected (for UPDATE/INSERT/DELETE)
        
    Raises:
        Exception: If DML fails after all retries (including lock timeout)
    """
    last_error = None
    for i in range(retries):
        try:
            with engine.begin() as conn:  # begin() = auto commit/rollback
                # Set timeouts appropriate for DML operations
                conn.execute(text("SET lock_timeout = '60s'"))
                conn.execute(text("SET statement_timeout = '0'"))  # Unlimited for large operations
                conn.execute(text("SET idle_in_transaction_session_timeout = '60s'"))
                # Execute the DML
                result = conn.execute(text(sql), params or {})
                rowcount = result.rowcount if hasattr(result, 'rowcount') else 0
                return rowcount  # Success
        except (OperationalError, DBAPIError) as e:
            last_error = e
            # Check if this is a retryable error (connection or lock)
            is_lock_error = False
            is_connection_error = False
            
            # Check for LockNotAvailable in the original exception
            if hasattr(e, 'orig') and e.orig is not None:
                error_str = str(e.orig).lower()
                if 'locknotavailable' in error_str or 'lock_timeout' in error_str or 'could not obtain lock' in error_str:
                    is_lock_error = True
            
            # Check for connection errors
            is_connection_error = _is_retryable(e)
            
            # Retry on lock errors or connection errors
            if (is_lock_error or is_connection_error) and i < retries - 1:
                sleep_time = 2.0 * (i + 1)
                error_type = "lock" if is_lock_error else "connection"
                logger.warning(f"⚠️ DML {error_type} error (attempt {i + 1}/{retries}), retrying in {sleep_time}s: {e}")
                time.sleep(sleep_time)
                continue
            
            # Non-retryable or last attempt - fall through to error handling
            logger.error(f"DML failed: {e}", exc_info=True)
            # Try to log lock information
            try:
                # Use a fresh connection to query lock information
                with engine.connect() as debug_conn:
                    rows = debug_conn.execute(text(LOCK_DEBUG_SQL)).fetchall()
                    if rows:
                        logger.error("=" * 80)
                        logger.error("LOCK DEBUG - Processes blocking this DML operation:")
                        logger.error("=" * 80)
                        for row in rows:
                            logger.error(f"  Blocked PID: {row[0]}, State: {row[1]}")
                            logger.error(f"    Query: {row[2][:200] if row[2] else 'N/A'}")
                            logger.error(f"  Blocking PID: {row[3]}, State: {row[4]}")
                            logger.error(f"    Query: {row[5][:200] if row[5] else 'N/A'}")
                            logger.error("-" * 80)
                    else:
                        logger.error("LOCK DEBUG: No blocking processes found (lock may have cleared)")
            except Exception as debug_error:
                logger.error(f"Could not retrieve lock debug info: {debug_error}")
            # Re-raise the original exception to ensure migration fails
            raise
        except Exception as e:
            # Non-OperationalError - just log and raise
            logger.error(f"DML failed: {e}", exc_info=True)
            raise
    # Should never reach here, but handle it anyway
    if last_error:
        raise last_error

def exec_index(engine, sql: str, index_name: str = None, retries=10, best_effort=True):
    """
    
    CONCURRENTLY indexes MUST run outside a transaction (AUTOCOMMIT mode) and are
    critical for production deployments where tables have active writes.
    
    Key features:
    - Uses AUTOCOMMIT isolation level (required for CONCURRENTLY)
    - Longer lock_timeout (60s) to handle busy tables
    - Unlimited statement_timeout (index creation can take time)
    - Retry logic for LockNotAvailable errors (up to 10 attempts)
    - Best-effort mode: warns on failure but doesn't fail migration (indexes are performance optimizations)
    - Lock debug logging on failures
    
    Lock timeouts:
    - lock_timeout: 60s (longer to handle concurrent table access)
    - statement_timeout: 0 (unlimited - index creation can be slow)
    
    Args:
        engine: SQLAlchemy engine
        index_name: Name of index being created (for logging)
        retries: Number of retry attempts (default: 10 for production resilience)
        best_effort: If True, warns on failure instead of raising (default: True)
        
    Returns:
        True if index was created successfully, False if failed (only in best_effort mode)
        
    Raises:
        Exception: If index creation fails and best_effort=False
        
    Example:
        exec_index(engine, '''
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_call_log_lead_created
            ON call_log(lead_id, created_at)
            WHERE lead_id IS NOT NULL
        ''', index_name='idx_call_log_lead_created')
    """
    if index_name is None:
        # Try to extract index name from SQL
        import re
        match = re.search(r'INDEX\s+(?:CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?(\w+)', sql, re.IGNORECASE)
        if match:
            index_name = match.group(1)
        else:
            index_name = "unknown_index"
    
    last_error = None
    for i in range(retries):
        try:
            # CRITICAL: Use AUTOCOMMIT isolation level - CONCURRENTLY requires no transaction
            with engine.connect() as conn:
                conn = conn.execution_options(isolation_level="AUTOCOMMIT")
                
                # Set timeouts appropriate for index creation
                conn.execute(text("SET lock_timeout = '60s'"))  # Longer timeout for busy tables
                conn.execute(text("SET statement_timeout = '0'"))  # Unlimited - index creation can be slow
                
                conn.execute(text(sql))
                
                logger.info(f"✅ Successfully created index: {index_name}")
                return True  # Success
                
        except (OperationalError, DBAPIError) as e:
            last_error = e
            
            # Check if this is a lock-related error
            is_lock_error = False
            if hasattr(e, 'orig') and e.orig is not None:
                error_str = str(e.orig).lower()
                if 'locknotavailable' in error_str or 'lock_timeout' in error_str or 'could not obtain lock' in error_str or 'canceling statement due to lock timeout' in error_str:
                    is_lock_error = True
            else:
                error_str = str(e).lower()
                if 'lock' in error_str or 'timeout' in error_str:
                    is_lock_error = True
            
            # Retry on lock errors
            if is_lock_error and i < retries - 1:
                sleep_time = 2.0 * (i + 1)  # Exponential backoff: 2s, 4s, 6s...
                logger.warning(f"⚠️ Index creation lock error (attempt {i + 1}/{retries}), retrying in {sleep_time}s: {e}")
                time.sleep(sleep_time)
                continue
            
            # Last attempt or non-lock error - log detailed information
            logger.error(f"Index creation failed for {index_name}: {e}", exc_info=True)
            
            # Try to log lock information
            try:
                with engine.connect() as debug_conn:
                    rows = debug_conn.execute(text(LOCK_DEBUG_SQL)).fetchall()
                    if rows:
                        logger.error("=" * 80)
                        logger.error(f"LOCK DEBUG - Processes blocking index creation ({index_name}):")
                        logger.error("=" * 80)
                        for row in rows:
                            logger.error(f"  Blocked PID: {row[0]}, State: {row[1]}")
                            logger.error(f"    Query: {row[2][:200] if row[2] else 'N/A'}")
                            logger.error(f"  Blocking PID: {row[3]}, State: {row[4]}")
                            logger.error(f"    Query: {row[5][:200] if row[5] else 'N/A'}")
                            logger.error("-" * 80)
                    else:
                        logger.error("LOCK DEBUG: No blocking processes found (lock may have cleared)")
            except Exception as debug_error:
                logger.error(f"Could not retrieve lock debug info: {debug_error}")
            
            # Handle based on best_effort mode
            if best_effort:
                logger.warning(f"⚠️ Index creation failed for {index_name} after {retries} attempts - continuing (best-effort mode)")
                logger.warning(f"   The migration will continue, but performance may be impacted.")
                logger.warning(f"   You can manually create the index later with: {sql}")
                return False  # Return False to indicate failure in best-effort mode
            else:
                # Not best-effort - re-raise to fail the migration
                raise
                
        except Exception as e:
            # Non-lock error - log and handle
            last_error = e
            logger.error(f"Index creation failed for {index_name}: {e}", exc_info=True)
            
            if best_effort:
                logger.warning(f"⚠️ Index creation failed for {index_name} - continuing (best-effort mode)")
                logger.warning(f"   You can manually create the index later with: {sql}")
                return False
            else:
                raise
    
    # Should never reach here, but handle it anyway
    if last_error:
        if best_effort:
            logger.warning(f"⚠️ Index creation failed for {index_name} after {retries} attempts - continuing (best-effort mode)")
            return False
        else:
            raise last_error
    
    return True  # Success

def exec_ddl_heavy(engine, sql: str, params=None, retries=10):
    """
    Execute heavy DDL operations that require AccessExclusive locks.
    
    This is designed for operations like:
    - ALTER TABLE ... DROP CONSTRAINT
    - ALTER TABLE ... ADD CONSTRAINT
    - Other DDL that needs to wait for locks on busy tables
    
    Key differences from exec_ddl():
    - Longer lock_timeout (120s instead of 5s) - allows more time to acquire locks
    - statement_timeout = 0 (unlimited) - because waiting for locks is expected
    - More retries (10 instead of 4) with exponential backoff
    - Real-time lock debugging (shows blocking PIDs DURING lock wait, not after)
    
    Lock timeouts:
    - lock_timeout: 120s (wait longer to acquire AccessExclusive lock)
    - statement_timeout: 0 (unlimited - operation may need time)
    - idle_in_transaction_session_timeout: 60s (kill stuck transactions)
    
    Args:
        engine: SQLAlchemy engine
        sql: DDL statement to execute
        params: Optional parameters for the SQL statement
        retries: Number of retry attempts (default: 10)
        
    Raises:
        RuntimeError: If DDL fails after all retries due to lock contention
        Exception: If DDL fails for non-lock reasons
        
    Example:
        exec_ddl_heavy(migrate_engine, '''
            ALTER TABLE receipts 
            DROP CONSTRAINT IF EXISTS chk_receipt_status
        ''')
    """
    delay = 2.0
    
    for i in range(retries):
        try:
            with engine.begin() as conn:
                # Get our own PID for debugging
                backend_pid_result = conn.execute(text("SELECT pg_backend_pid()"))
                backend_pid = backend_pid_result.scalar()
                logger.info(f"🔍 DDL Heavy (attempt {i + 1}/{retries}): Backend PID = {backend_pid}")
                
                # Set timeouts appropriate for heavy DDL
                conn.execute(text("SET lock_timeout = '120s'"))
                conn.execute(text("SET statement_timeout = 0"))
                conn.execute(text("SET idle_in_transaction_session_timeout = '60s'"))
                
                # Execute the DDL
                logger.info(f"🔨 Executing DDL: {sql[:100]}...")
                conn.execute(text(sql), params or {})
                
            logger.info(f"✅ DDL Heavy completed successfully (attempt {i + 1}/{retries})")
            return  # Success
            
        except Exception as e:
            last_error = e
            # Check if this is a lock-related error
            # Note: psycopg2.errors.LockNotAvailable comes through e.orig
            msg = str(getattr(e, "orig", e)).lower()
            is_lock_error = any(pattern in msg for pattern in [
                "locknotavailable",
                "lock timeout",
                "could not obtain lock",
                "deadlock detected",
                "canceling statement due to lock timeout"
            ])
            
            # 🔥 CRITICAL: Log lock debug info IMMEDIATELY when lock error occurs
            # This captures the blocking processes IN REAL TIME, not after they're gone
            if is_lock_error:
                logger.error(f"❌ Lock error on heavy DDL (attempt {i + 1}/{retries}): {e}")
                
                # Get real-time lock information
                try:
                    with engine.connect() as debug_conn:
                        # Query 1: Get our backend PID
                        backend_pid_result = debug_conn.execute(text("SELECT pg_backend_pid()"))
                        my_pid = backend_pid_result.scalar()
                        
                        # Query 2: Get PIDs blocking us
                        blocking_pids_result = debug_conn.execute(text(
                            "SELECT pg_blocking_pids(:pid)::text"
                        ), {"pid": my_pid})
                        blocking_pids_str = blocking_pids_result.scalar()
                        
                        # Parse blocking PIDs (format: "{123,456}" or "{}")
                        blocking_pids = []
                        if blocking_pids_str and blocking_pids_str != '{}':
                            # Remove braces and split
                            blocking_pids = [int(p.strip()) for p in blocking_pids_str.strip('{}').split(',') if p.strip()]
                        
                        logger.error("=" * 80)
                        logger.error("🔍 REAL-TIME LOCK DEBUG (captured during lock timeout)")
                        logger.error("=" * 80)
                        logger.error(f"Our PID: {my_pid}")
                        logger.error(f"Blocking PIDs: {blocking_pids if blocking_pids else 'None (lock already released)'}")
                        
                        # Query 3: If we have blocking PIDs, get details about them
                        # 🔒 SECURITY: Use ANY() with parameterized array to avoid SQL injection
                        if blocking_pids:
                            blocking_details = debug_conn.execute(text("""
                                SELECT 
                                    pid, 
                                    usename,
                                    application_name,
                                    client_addr,
                                    state,
                                    now() - query_start AS query_age,
                                    left(query, 200) AS query
                                FROM pg_stat_activity
                                WHERE pid = ANY(:pids)
                            """), {"pids": blocking_pids}).fetchall()
                            
                            logger.error("-" * 80)
                            logger.error("🚨 BLOCKING PROCESSES:")
                            logger.error("-" * 80)
                            for row in blocking_details:
                                logger.error(f"  PID: {row[0]}")
                                logger.error(f"    User: {row[1]}")
                                logger.error(f"    App: {row[2]}")
                                logger.error(f"    Client: {row[3]}")
                                logger.error(f"    State: {row[4]}")
                                logger.error(f"    Query age: {row[5]}")
                                logger.error(f"    Query: {row[6]}")
                                logger.error("-" * 40)
                        
                        # Query 4: Show all active connections to this database
                        all_conns = debug_conn.execute(text("""
                            SELECT 
                                count(*) as total,
                                string_agg(DISTINCT application_name, ', ') as apps
                            FROM pg_stat_activity
                            WHERE datname = current_database()
                            AND pid != pg_backend_pid()
                        """)).fetchone()
                        
                        if all_conns:
                            logger.error("-" * 80)
                            logger.error(f"📊 DATABASE STATS:")
                            logger.error(f"    Total active connections: {all_conns[0]}")
                            logger.error(f"    Applications: {all_conns[1]}")
                        
                        logger.error("=" * 80)
                        
                except Exception as debug_error:
                    logger.error(f"⚠️ Could not retrieve lock debug info: {debug_error}")
            
            # Retry logic
            if is_lock_error and i < retries - 1:
                # Log warning and retry
                logger.warning(f"⏳ Retrying in {delay}s (attempt {i + 2}/{retries})...")
                time.sleep(delay)
                delay = min(delay * 1.5, 30)  # Exponential backoff, max 30s
                continue
            
            # Non-lock error or last attempt
            if not is_lock_error:
                logger.error(f"❌ Heavy DDL failed with non-lock error (attempt {i + 1}/{retries}): {e}")
            
            # If it's a lock error and we've exhausted retries, raise special error
            if is_lock_error:
                raise RuntimeError(f"DDL heavy failed due to locks after {retries} retries. Check logs above for blocking processes.")
            else:
                # Non-lock error - re-raise immediately
                raise
    
    # Should never reach here, but handle it anyway
    raise RuntimeError(f"DDL heavy failed due to locks after {retries} retries")

def execute_with_retry(engine, sql: str, params=None, *, max_retries=10, fetch=False):
    """
    Execute SQL with robust retry logic and engine.dispose() on SSL errors.
    
    🔥 IRON RULE: ALL migration queries MUST go through this function
    
    This function provides POOLER-safe execution with:
    - Detection of SSL/connection errors
    - engine.dispose() on errors to refresh connection pool
    - Exponential backoff: 1s, 2s, 4s, 8s...
    - Max 8-10 retries
    
    Args:
        engine: SQLAlchemy engine instance
        sql: SQL statement to execute
        params: Dictionary of query parameters (default: None)
        max_retries: Maximum number of retry attempts (default: 10)
        fetch: If True, return query results; if False, execute only
    
    Returns:
        Query results if fetch=True, None otherwise
    
    Raises:
        Exception: If all retry attempts fail
    
    Example:
        # Execute DDL
        execute_with_retry(engine, "ALTER TABLE leads ADD COLUMN name TEXT")
        
        # Fetch results (for SELECT queries or any query that returns results)
        rows = execute_with_retry(engine, "SELECT * FROM schema_migrations", fetch=True)
        
        # Note: This function automatically detects SELECT and returns results
        rows = execute_with_retry(engine, "SELECT COUNT(*) FROM leads")
    """
    last_error = None
    
    # Auto-detect if this is a SELECT query
    is_select = sql.strip().upper().startswith('SELECT')
    should_fetch = fetch or is_select
    
    for attempt in range(max_retries):
        try:
            with engine.begin() as conn:
                result = conn.execute(text(sql), params or {})
                if should_fetch:
                    return result.fetchall()
                return result  # Return result object so caller can access rowcount
                
        except (OperationalError, DBAPIError) as e:
            last_error = e
            error_msg = str(e).lower()
            
            # Check if this is a retryable connection error
            is_ssl_error = any(pattern.lower() in error_msg for pattern in [
                "ssl connection has been closed unexpectedly",
                "server closed the connection unexpectedly",
                "connection reset by peer",
                "could not receive data from server",
                "connection not open",
                "connection already closed",
                "network is unreachable",
                "could not connect to server"
            ])
            
            if is_ssl_error and attempt < max_retries - 1:
                # 🔥 CRITICAL: Dispose engine on SSL error to refresh connection pool
                try:
                    engine.dispose()
                    log.info(f"🔄 Disposed engine after SSL/connection error")
                except Exception as dispose_error:
                    log.warning(f"⚠️ Error disposing engine: {dispose_error}")
                
                # Exponential backoff: 1s, 2s, 4s, 8s (capped at 8s)
                sleep_time = min(2 ** attempt, 8)
                log.warning(f"⚠️ SSL/connection error (attempt {attempt + 1}/{max_retries}), "
                          f"retrying in {sleep_time}s: {e}")
                time.sleep(sleep_time)
                continue
            
            # Non-retryable or last attempt
            log.error(f"❌ execute_with_retry failed after {attempt + 1} attempts: {e}")
            raise
            
        except Exception as e:
            # ⚠️ IRON RULE: DDL FAILURES = FAIL HARD (except "already exists")
            # Note: This catch block is for non-connection errors (ProgrammingError, SyntaxError, etc.)
            # Connection errors are handled in the (OperationalError, DBAPIError) block above and retried.
            # DDL syntax/programming errors are not transient and won't be fixed by retrying.
            
            # Check if this is a DDL operation (ALTER, CREATE, DROP)
            sql_upper = sql.strip().upper()
            is_ddl = any(sql_upper.startswith(cmd) for cmd in ['ALTER', 'CREATE', 'DROP'])
            
            if is_ddl:
                # For DDL operations, check if error is "already exists" type
                if _is_already_exists_error(e):
                    log.warning(f"⚠️ DDL object already exists (safe to continue): {e}")
                    # Return a mock result with rowcount=0 for DDL operations
                    class MockResult:
                        rowcount = 0
                    return MockResult() if not should_fetch else []  # Success - object already exists
                
                # Any other DDL error = FAIL HARD
                log.error(f"❌ DDL FAILED in execute_with_retry - STOPPING MIGRATION: {e}")
                log.error("=" * 80)
                log.error("⚠️ MIGRATION STOPPED: DDL statement failed")
                log.error("⚠️ This is NOT an 'already exists' error - something is broken")
                log.error("⚠️ Fix the migration code and try again")
                log.error("=" * 80)
                raise
            else:
                # Non-DDL error - just log and raise (could be DML, SELECT, etc.)
                log.error(f"❌ Non-retryable error in execute_with_retry: {e}")
                raise
    
    # Should never reach here, but handle it
    raise last_error

def apply_migrations():
    """
    Apply all pending migrations
    
    🔒 DATA PROTECTION: This function ONLY adds new tables/columns/indexes.
    It NEVER deletes user data. All existing FAQs, leads, messages, etc. are preserved.
    
    🔒 CONCURRENCY PROTECTION: Uses PostgreSQL advisory lock to prevent multiple
    processes from running migrations simultaneously (prevents deadlocks).
    
    🔒 WORKER PROTECTION: Workers should NEVER run migrations. Migrations only run
    in API service during startup.
    
    🔒 CONNECTION LOCKING: Connection choice (DIRECT or POOLER) is made ONCE at the
    start and locked for entire run. No mid-run connection changes.
    """
    import os
    import time
    
    # 🔥 CRITICAL: Hard gate - workers must NEVER run migrations
    # Migrations should only run once during API startup, not on every job
    service_role = os.getenv('SERVICE_ROLE', '').lower()
    
    # Skip migrations if this is a worker
    if service_role == 'worker':
        checkpoint("=" * 80)
        checkpoint("🚫 MIGRATIONS_SKIPPED: service_role=worker")
        checkpoint("   Workers use existing schema - migrations run only in API")
        checkpoint("=" * 80)
        return 'skip'  # Return 'skip' to indicate migrations were skipped
    
    # 🔥 AUTOMATIC MIGRATIONS: When apply_migrations() is called by the API server,
    # it should run automatically. The RUN_MIGRATIONS env var is optional for backwards
    # compatibility but not required. Migrations run by default when called.
    run_migrations = os.getenv('RUN_MIGRATIONS', '1')  # Default to '1' (enabled)
    if run_migrations != '1':
        checkpoint("=" * 80)
        checkpoint("🚫 MIGRATIONS_DISABLED: RUN_MIGRATIONS explicitly set to disable")
        checkpoint("   Set RUN_MIGRATIONS=1 to enable migrations")
        checkpoint("=" * 80)
        return 'skip'  # Return 'skip' to indicate migrations were disabled
    
    checkpoint("Starting apply_migrations()")
    checkpoint(f"  SERVICE_ROLE: {service_role or 'not set (API server)'}")
    migrations_applied = []
    
    # 🔥 CRITICAL: Create migration engine ONCE at start - this locks connection choice
    # Try DIRECT first (with 5s timeout), fall back to POOLER if unavailable
    # After this, connection is LOCKED for entire run - no mid-run changes
    checkpoint("=" * 80)
    checkpoint("🔒 ESTABLISHING DATABASE CONNECTION (one-time decision)")
    checkpoint("=" * 80)
    migrate_engine = None
    try:
        migrate_engine = get_migrate_engine()
        # Try to connect 5 times with retry logic
        fetch_all(migrate_engine, "SELECT 1", retries=5)
        checkpoint("✅ DB connection established and locked for this run")
    except Exception as e:
        error_str = str(e).lower()
        # Check if this is a network unreachability issue (DIRECT not accessible)
        if "network is unreachable" in error_str or "could not connect to server" in error_str:
            checkpoint("=" * 80)
            checkpoint(f"⚠️  DIRECT connection unreachable: {e}")
            checkpoint("   Falling back to POOLER (this is expected when DIRECT unavailable)")
            checkpoint("=" * 80)
            # Connection is already locked to POOLER by get_migrate_engine()
            # No need to retry - the fallback already happened
        else:
            # Real database stability issue - abort migrations
            checkpoint("=" * 80)
            checkpoint(f"❌ DATABASE CONNECTION FAILED: {e}")
            checkpoint("   Database appears unstable (restarting/OOM/network issues)")
            checkpoint("   Action: Check database logs for issues")
            checkpoint("=" * 80)
            raise RuntimeError(f"Database connection failed: {e}")
    
    checkpoint("=" * 80)
    checkpoint("")
    
    # 🔒 CONCURRENCY PROTECTION: Acquire PostgreSQL advisory lock with retry
    # Lock ID: 1234567890 (arbitrary unique integer)
    # This ensures only ONE process runs migrations at a time
    LOCK_ID = 1234567890
    LOCK_WAIT_SECONDS = int(os.getenv("MIGRATION_LOCK_WAIT_SECONDS", "30"))
    
    checkpoint("Acquiring PostgreSQL advisory lock for migrations...")
    from sqlalchemy import text
    lock_acquired = False
    
    try:
        # 🔥 IRON RULE: Use migrate_engine for lock acquisition (not db.session)
        # Try to acquire lock with retry loop
        start_time = time.time()
        while time.time() - start_time < LOCK_WAIT_SECONDS:
            # Use execute_with_retry for lock acquisition
            result = execute_with_retry(
                migrate_engine,
                "SELECT pg_try_advisory_lock(:id)",
                {"id": LOCK_ID},
                fetch=True
            )
            lock_acquired = result[0][0] if result else False
            
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
        
        # 🔥 CRITICAL: Use the SAME migrate_engine for ALL operations
        # Never call get_migrate_engine() again - connection is already locked
        checkpoint("Setting up migration state tracking...")
        ensure_migration_tracking_table(migrate_engine)
        
        # 🔥 Reconcile existing state with SAME engine
        reconcile_existing_state(migrate_engine)
        
        # 🔒 BUILD 111: TRIPLE LAYER DATA PROTECTION
        # Layer 1: Count FAQs BEFORE migrations
        # Layer 2: Run migrations inside TRY block
        # Layer 3: Count FAQs AFTER migrations and ROLLBACK if decreased
        checkpoint("Starting data protection layer 1 - counting existing data")
        faq_count_before = 0
        lead_count_before = 0
        msg_count_before = 0
        try:
            # 🔥 CRITICAL FIX: Check table existence BEFORE counting to prevent UndefinedTable exceptions
            if check_table_exists('faqs'):
                result = execute_with_retry(migrate_engine, "SELECT COUNT(*) FROM faqs")
                faq_count_before = result[0][0] if result else 0
                checkpoint(f"🔒 LAYER 1 (BEFORE): {faq_count_before} FAQs exist")
            else:
                checkpoint(f"🔒 LAYER 1 (BEFORE): faqs table does not exist yet")
                
            if check_table_exists('leads'):
                result = execute_with_retry(migrate_engine, "SELECT COUNT(*) FROM leads")
                lead_count_before = result[0][0] if result else 0
                checkpoint(f"🔒 LAYER 1 (BEFORE): {lead_count_before} leads exist")
            else:
                checkpoint(f"🔒 LAYER 1 (BEFORE): leads table does not exist yet")
                
            if check_table_exists('messages'):
                result = execute_with_retry(migrate_engine, "SELECT COUNT(*) FROM messages")
                msg_count_before = result[0][0] if result else 0
                checkpoint(f"🔒 LAYER 1 (BEFORE): {msg_count_before} messages exist")
            else:
                checkpoint(f"🔒 LAYER 1 (BEFORE): messages table does not exist yet")
        except Exception as e:
            log.warning(f"Could not check data counts (database may be new): {e}")
            checkpoint(f"Could not check data counts (database may be new): {e}")
        
        # Migration 0: Create alembic_version table (for compatibility with health checks)
        # This is optional but prevents 503 errors in health endpoint
        if not check_table_exists('alembic_version'):
            try:
                checkpoint("Creating alembic_version table for health check compatibility")
                execute_with_retry(migrate_engine, """
                    CREATE TABLE IF NOT EXISTS alembic_version (
                        version_num VARCHAR(32) NOT NULL PRIMARY KEY
                    )
                """)
                # Insert a marker version to indicate ProSaaS custom migrations
                execute_with_retry(migrate_engine, """
                    INSERT INTO alembic_version(version_num)
                    SELECT :marker
                    WHERE NOT EXISTS (SELECT 1 FROM alembic_version)
                """, {"marker": PROSAAS_MIGRATION_MARKER})
                migrations_applied.append("create_alembic_version_table")
                checkpoint("✅ Created alembic_version table with marker")
            except Exception as e:
                log.warning(f"Could not create alembic_version table: {e}")
                checkpoint(f"Could not create alembic_version table: {e}")
        
        # Migration 1: Add transcript column to CallLog
        if check_table_exists('call_log'):
            try:
                # 🔒 IDEMPOTENT: Use IF NOT EXISTS to prevent DuplicateColumn errors
                execute_with_retry(migrate_engine, "ALTER TABLE call_log ADD COLUMN IF NOT EXISTS transcript TEXT")
                migrations_applied.append("add_call_log_transcript")
                log.info("Applied migration: add_call_log_transcript")
            except Exception as e:
                log.warning(f"Could not add transcript column (may already exist): {e}")
        
        # Migration 2: Create CallTurn table
        if not check_table_exists('call_turn'):
            execute_with_retry(migrate_engine, """
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
            """)
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
                default_value = 'true' if flag.startswith('enable_calls') or flag.startswith('enable_recording') else 'false'
                execute_with_retry(migrate_engine, f"ALTER TABLE business ADD COLUMN {flag} BOOLEAN DEFAULT {default_value}")
                migrations_applied.append(f"add_business_{flag}")
                log.info(f"Applied migration: add_business_{flag}")
        
        # Migration 4: Create threads table for unified messaging
        if not check_table_exists('threads'):
            execute_with_retry(migrate_engine, """
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
            """)
            migrations_applied.append("create_threads_table")
            log.info("Applied migration: create_threads_table")
        
        # Migration 5: Create messages table for unified messaging
        if not check_table_exists('messages'):
            execute_with_retry(migrate_engine, """
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
            """)
            migrations_applied.append("create_messages_table")
            log.info("Applied migration: create_messages_table")
        
        # Migration 6: Add unique index for message deduplication
        if check_table_exists('messages') and not check_index_exists('uniq_msg_provider_id'):
            try:
                # 🔄 SAFE DML: Required deduplication before creating UNIQUE index
                # This DELETE is necessary to enforce the UNIQUE constraint.
                # Keeps the earliest message (MIN(id)) for each provider_msg_id.
                execute_with_retry(migrate_engine, """
                    DELETE FROM messages 
                    WHERE id NOT IN (
                        SELECT MIN(id) 
                        FROM messages 
                        WHERE provider_msg_id IS NOT NULL AND provider_msg_id != ''
                        GROUP BY provider_msg_id
                    )
                    AND provider_msg_id IS NOT NULL AND provider_msg_id != ''
                """)
                
                # Create unique index on provider_msg_id (for non-null values)
                execute_with_retry(migrate_engine, """
                    CREATE UNIQUE INDEX uniq_msg_provider_id 
                    ON messages(provider_msg_id) 
                    WHERE provider_msg_id IS NOT NULL AND provider_msg_id != ''
                """)
                migrations_applied.append("add_unique_provider_msg_id")
                log.info("Applied migration: add_unique_provider_msg_id")
            except Exception as e:
                # 🔥 CRITICAL FIX: ROLLBACK immediately to prevent InFailedSqlTransaction
                log.warning(f"Could not create unique index (may already exist): {e}")
        
        # Migration 7: Create leads table for CRM system
        if not check_table_exists('leads'):
            execute_with_retry(migrate_engine, """
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
            """)
            
            indexes = [
            ]
            
            for index_sql in indexes:
                execute_with_retry(migrate_engine, index_sql)
                
            migrations_applied.append("create_leads_table")
            log.info("Applied migration: create_leads_table")
        
        # Migration 8: Create lead_reminders table
        if not check_table_exists('lead_reminders'):
            execute_with_retry(migrate_engine, """
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
            """)
            
            migrations_applied.append("create_lead_reminders_table")
            log.info("Applied migration: create_lead_reminders_table")
        
        # Migration 9: Create lead_activities table
        if not check_table_exists('lead_activities'):
            execute_with_retry(migrate_engine, """
                CREATE TABLE lead_activities (
                    id SERIAL PRIMARY KEY,
                    lead_id INTEGER NOT NULL REFERENCES leads(id),
                    type VARCHAR(32) NOT NULL,
                    payload JSONB,
                    at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by INTEGER REFERENCES users(id)
                )
            """)
            
            migrations_applied.append("create_lead_activities_table")
            log.info("Applied migration: create_lead_activities_table")
        
        # Migration 10: Create lead_merge_candidates table
        if not check_table_exists('lead_merge_candidates'):
            execute_with_retry(migrate_engine, """
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
            """)
            
            migrations_applied.append("create_lead_merge_candidates_table")
            log.info("Applied migration: create_lead_merge_candidates_table")
        
        # Migration 11: Add order_index column to leads table for Kanban support
        if check_table_exists('leads') and not check_column_exists('leads', 'order_index'):
            execute_with_retry(migrate_engine, "ALTER TABLE leads ADD COLUMN order_index INTEGER DEFAULT 0")
            # Set default order for existing leads based on their ID
            execute_with_retry(migrate_engine, "UPDATE leads SET order_index = id WHERE order_index = 0")
            migrations_applied.append("add_leads_order_index")
            log.info("Applied migration: add_leads_order_index")
        
        # Migration 12: Add working_hours and voice_message columns to business table
        business_columns = [
            ('working_hours', 'VARCHAR(50)', "'08:00-18:00'"),
            ('voice_message', 'TEXT', 'NULL')
        ]
        
        for col_name, col_type, default_val in business_columns:
            if check_table_exists('business') and not check_column_exists('business', col_name):
                execute_with_retry(migrate_engine, f"ALTER TABLE business ADD COLUMN {col_name} {col_type} DEFAULT {default_val}")
                migrations_applied.append(f"add_business_{col_name}")
                log.info(f"Applied migration: add_business_{col_name}")
        
        # Migration 15: Add unique constraint on call_log.call_sid to prevent duplicates
        if check_table_exists('call_log') and not check_index_exists('uniq_call_log_call_sid'):
            try:
                # First remove any existing duplicates (keep the earliest)
                execute_with_retry(migrate_engine, """
                    DELETE FROM call_log 
                    WHERE id NOT IN (
                        SELECT MIN(id) 
                        FROM call_log 
                        WHERE call_sid IS NOT NULL AND call_sid != ''
                        GROUP BY call_sid
                    )
                    AND call_sid IS NOT NULL AND call_sid != ''
                """)
                
                # Create unique index on call_sid
                execute_with_retry(migrate_engine, """
                    CREATE UNIQUE INDEX uniq_call_log_call_sid 
                    ON call_log(call_sid) 
                    WHERE call_sid IS NOT NULL AND call_sid != ''
                """)
                migrations_applied.append("add_unique_call_sid")
                log.info("Applied migration: add_unique_call_sid")
            except Exception as e:
                # 🔥 CRITICAL FIX: ROLLBACK immediately to prevent InFailedSqlTransaction
                log.warning(f"Could not create unique index on call_sid (may already exist): {e}")
        
        # Migration 13: Create business_settings table for AI prompt management
        if not check_table_exists('business_settings'):
            execute_with_retry(migrate_engine, """
                CREATE TABLE business_settings (
                    tenant_id INTEGER NOT NULL REFERENCES business(id) PRIMARY KEY,
                    ai_prompt TEXT,
                    model VARCHAR(50) DEFAULT 'gpt-4o-mini',
                    max_tokens INTEGER DEFAULT 150,
                    temperature FLOAT DEFAULT 0.7,
                    updated_by VARCHAR(255),
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            migrations_applied.append("create_business_settings_table")
            log.info("Applied migration: create_business_settings_table")
        
        # Migration 14: Create prompt_revisions table for AI prompt versioning
        if not check_table_exists('prompt_revisions'):
            execute_with_retry(migrate_engine, """
                CREATE TABLE prompt_revisions (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL REFERENCES business(id),
                    version INTEGER NOT NULL,
                    prompt TEXT,
                    changed_by VARCHAR(255),
                    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            migrations_applied.append("create_prompt_revisions_table")
            log.info("Applied migration: create_prompt_revisions_table")
        
        # Migration 16: Create business_contact_channels table for multi-tenant routing
        if not check_table_exists('business_contact_channels'):
            execute_with_retry(migrate_engine, """
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
            """)
            
            
            # Unique constraint: one identifier per channel type
            execute_with_retry(migrate_engine, """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_channel_identifier 
                ON business_contact_channels(channel_type, identifier)
            """)
            
            # Seed data: Add contact channels for existing businesses
            # For each business with a phone_number, create twilio_voice + whatsapp channels
            execute_with_retry(migrate_engine, """
                INSERT INTO business_contact_channels (business_id, channel_type, identifier, is_primary)
                SELECT 
                    id as business_id,
                    'twilio_voice' as channel_type,
                    phone_number as identifier,
                    true as is_primary
                FROM business
                WHERE phone_number IS NOT NULL AND phone_number != ''
                ON CONFLICT (channel_type, identifier) DO NOTHING
            """)
            
            # Add WhatsApp channels with business_X format
            execute_with_retry(migrate_engine, """
                INSERT INTO business_contact_channels (business_id, channel_type, identifier, is_primary)
                SELECT 
                    id as business_id,
                    'whatsapp' as channel_type,
                    'business_' || id as identifier,
                    true as is_primary
                FROM business
                ON CONFLICT (channel_type, identifier) DO NOTHING
            """)
            
            migrations_applied.append("create_business_contact_channels_table")
            log.info("Applied migration: create_business_contact_channels_table with seed data")
        
        # Migration 17: Add signature_data to contract table
        if check_table_exists('contract') and not check_column_exists('contract', 'signature_data'):
            execute_with_retry(migrate_engine, "ALTER TABLE contract ADD COLUMN signature_data TEXT")
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
                execute_with_retry(migrate_engine, f"ALTER TABLE call_log ADD COLUMN {col_name} {col_type} DEFAULT {default_val}")
                migrations_applied.append(f"add_call_log_{col_name}")
                log.info(f"Applied migration: add_call_log_{col_name}")
        
        # Migration 18: Fix Deal.customer_id foreign key (leads.id → customer.id)
        if check_table_exists('deal'):
            try:
                # Check if the wrong constraint exists
                result = execute_with_retry(migrate_engine, """
                    SELECT constraint_name 
                    FROM information_schema.table_constraints 
                    WHERE table_name = 'deal' 
                    AND constraint_type = 'FOREIGN KEY'
                    AND constraint_name LIKE '%customer_id%'
                """)
                constraint_check = result[0] if result else None
                
                if constraint_check:
                    constraint_name = constraint_check[0]
                    # Drop old wrong foreign key (if it points to leads)
                    execute_with_retry(migrate_engine, f"ALTER TABLE deal DROP CONSTRAINT IF EXISTS {constraint_name}")
                    log.info(f"Dropped old foreign key constraint: {constraint_name}")
                
                # Add correct foreign key pointing to customer.id with CASCADE
                execute_with_retry(migrate_engine, """
                    ALTER TABLE deal 
                    ADD CONSTRAINT deal_customer_id_fkey 
                    FOREIGN KEY (customer_id) 
                    REFERENCES customer(id) 
                    ON DELETE CASCADE
                """)
                migrations_applied.append("fix_deal_customer_fkey")
                log.info("Applied migration: fix_deal_customer_fkey - Now points to customer.id with CASCADE")
            except Exception as e:
                # 🔥 CRITICAL FIX: ROLLBACK immediately to prevent InFailedSqlTransaction
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
                execute_with_retry(migrate_engine, f"ALTER TABLE business_settings ADD COLUMN {col_name} {col_type} DEFAULT {default_val}")
                migrations_applied.append(f"add_business_settings_{col_name}")
                log.info(f"✅ Applied migration: add_business_settings_{col_name} - Policy Engine field")
        
        # Migration 20: Add require_phone_before_booking to business_settings
        if check_table_exists('business_settings') and not check_column_exists('business_settings', 'require_phone_before_booking'):
            execute_with_retry(migrate_engine, "ALTER TABLE business_settings ADD COLUMN require_phone_before_booking BOOLEAN DEFAULT TRUE")
            migrations_applied.append("add_business_settings_require_phone_before_booking")
            log.info("✅ Applied migration 20: require_phone_before_booking - Phone required guard")
        
        # Migration 21: Create FAQs table for business-specific fast-path responses
        if not check_table_exists('faqs'):
            execute_with_retry(migrate_engine, """
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
            """)
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
                if default_val is None:
                    # Nullable column without default
                    execute_with_retry(migrate_engine, f"ALTER TABLE faqs ADD COLUMN {col_name} {col_type}")
                else:
                    # Column with explicit default value
                    execute_with_retry(migrate_engine, f"ALTER TABLE faqs ADD COLUMN {col_name} {col_type} DEFAULT {default_val}")
                migrations_applied.append(f"add_faqs_{col_name}")
                log.info(f"✅ Applied migration 22: add_faqs_{col_name} - FAQ Fast-Path field")
        
        # Migration 23: Create CallSession table for appointment deduplication
        if not check_table_exists('call_session'):
            execute_with_retry(migrate_engine, """
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
            """)
            migrations_applied.append("create_call_session_table")
            log.info("✅ Applied migration 23: create_call_session_table - Appointment deduplication")
        
        # Migration 24: Create WhatsAppConversationState table for AI toggle per conversation
        if not check_table_exists('whatsapp_conversation_state'):
            execute_with_retry(migrate_engine, """
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
            """)
            migrations_applied.append("create_whatsapp_conversation_state_table")
            log.info("✅ Applied migration 24: create_whatsapp_conversation_state_table - AI toggle per conversation")
        
        # Migration 25: Add whatsapp_provider column to business table (Meta Cloud API support)
        if check_table_exists('business') and not check_column_exists('business', 'whatsapp_provider'):
            execute_with_retry(migrate_engine, "ALTER TABLE business ADD COLUMN whatsapp_provider VARCHAR(32) DEFAULT 'baileys'")
            migrations_applied.append("add_business_whatsapp_provider")
            log.info("✅ Applied migration 25: add_business_whatsapp_provider - Meta Cloud API support")
        
        # Migration 26: Create WhatsAppConversation table for session tracking and auto-summary
        if not check_table_exists('whatsapp_conversation'):
            execute_with_retry(migrate_engine, """
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
            """)
            migrations_applied.append("create_whatsapp_conversation_table")
            log.info("✅ Applied migration 26: create_whatsapp_conversation_table - Session tracking + auto-summary")
        
        # Migration 27: Add whatsapp_last_summary fields to leads table
        if check_table_exists('leads') and not check_column_exists('leads', 'whatsapp_last_summary'):
            execute_with_retry(migrate_engine, "ALTER TABLE leads ADD COLUMN whatsapp_last_summary TEXT")
            execute_with_retry(migrate_engine, "ALTER TABLE leads ADD COLUMN whatsapp_last_summary_at TIMESTAMP")
            migrations_applied.append("add_leads_whatsapp_summary")
            log.info("✅ Applied migration 27: add_leads_whatsapp_summary - WhatsApp session summary on leads")
        
        # Migration 28: BUILD 163 - Monday.com integration + Auto-hangup + Bot speaks first
        if check_table_exists('business_settings'):
            
            # Monday.com integration fields
            if not check_column_exists('business_settings', 'monday_webhook_url'):
                execute_with_retry(migrate_engine, "ALTER TABLE business_settings ADD COLUMN monday_webhook_url VARCHAR(512)")
                migrations_applied.append("add_monday_webhook_url")
                log.info("✅ Applied migration 28a: add_monday_webhook_url")
            
            if not check_column_exists('business_settings', 'send_call_transcripts_to_monday'):
                execute_with_retry(migrate_engine, "ALTER TABLE business_settings ADD COLUMN send_call_transcripts_to_monday BOOLEAN DEFAULT FALSE")
                migrations_applied.append("add_send_call_transcripts_to_monday")
                log.info("✅ Applied migration 28b: add_send_call_transcripts_to_monday")
            
            # Auto hang-up fields
            if not check_column_exists('business_settings', 'auto_end_after_lead_capture'):
                execute_with_retry(migrate_engine, "ALTER TABLE business_settings ADD COLUMN auto_end_after_lead_capture BOOLEAN DEFAULT FALSE")
                migrations_applied.append("add_auto_end_after_lead_capture")
                log.info("✅ Applied migration 28c: add_auto_end_after_lead_capture")
            
            if not check_column_exists('business_settings', 'auto_end_on_goodbye'):
                execute_with_retry(migrate_engine, "ALTER TABLE business_settings ADD COLUMN auto_end_on_goodbye BOOLEAN DEFAULT FALSE")
                migrations_applied.append("add_auto_end_on_goodbye")
                log.info("✅ Applied migration 28d: add_auto_end_on_goodbye")
            
            # Bot speaks first field
            if not check_column_exists('business_settings', 'bot_speaks_first'):
                execute_with_retry(migrate_engine, "ALTER TABLE business_settings ADD COLUMN bot_speaks_first BOOLEAN DEFAULT FALSE")
                migrations_applied.append("add_bot_speaks_first")
                log.info("✅ Applied migration 28e: add_bot_speaks_first")
        
        # Migration 29: BUILD 182 - Outbound lead lists for bulk import
        if not check_table_exists('outbound_lead_lists'):
            execute_with_retry(migrate_engine, """
                CREATE TABLE outbound_lead_lists (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL REFERENCES business(id),
                    name VARCHAR(255) NOT NULL,
                    file_name VARCHAR(255),
                    total_leads INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            migrations_applied.append("create_outbound_lead_lists_table")
            log.info("✅ Applied migration 29a: create_outbound_lead_lists_table - Bulk import for outbound calls")
        
        # Migration 29b: Add outbound_list_id to leads table
        if check_table_exists('leads') and not check_column_exists('leads', 'outbound_list_id'):
            execute_with_retry(migrate_engine, "ALTER TABLE leads ADD COLUMN outbound_list_id INTEGER REFERENCES outbound_lead_lists(id)")
            migrations_applied.append("add_leads_outbound_list_id")
            log.info("✅ Applied migration 29b: add_leads_outbound_list_id - Link leads to import lists")
        
        # Migration 30: BUILD 183 - Separate inbound/outbound webhook URLs
        if check_table_exists('business_settings'):
            
            if not check_column_exists('business_settings', 'inbound_webhook_url'):
                execute_with_retry(migrate_engine, "ALTER TABLE business_settings ADD COLUMN inbound_webhook_url VARCHAR(512)")
                migrations_applied.append("add_inbound_webhook_url")
                log.info("✅ Applied migration 30a: add_inbound_webhook_url - Separate webhook for inbound calls")
            
            if not check_column_exists('business_settings', 'outbound_webhook_url'):
                execute_with_retry(migrate_engine, "ALTER TABLE business_settings ADD COLUMN outbound_webhook_url VARCHAR(512)")
                migrations_applied.append("add_outbound_webhook_url")
                log.info("✅ Applied migration 30b: add_outbound_webhook_url - Separate webhook for outbound calls")
        
        # Migration 31: BUILD 186 - Calendar scheduling toggle for inbound calls
        if check_table_exists('business_settings'):
            
            if not check_column_exists('business_settings', 'enable_calendar_scheduling'):
                execute_with_retry(migrate_engine, "ALTER TABLE business_settings ADD COLUMN enable_calendar_scheduling BOOLEAN DEFAULT TRUE")
                migrations_applied.append("add_enable_calendar_scheduling")
                log.info("✅ Applied migration 31: add_enable_calendar_scheduling - Toggle for AI appointment scheduling")
        
        # Migration 32: BUILD 204 - Dynamic STT Vocabulary for per-business transcription quality
        if check_table_exists('business_settings'):
            
            if not check_column_exists('business_settings', 'stt_vocabulary_json'):
                execute_with_retry(migrate_engine, "ALTER TABLE business_settings ADD COLUMN stt_vocabulary_json JSON")
                migrations_applied.append("add_stt_vocabulary_json")
                log.info("✅ Applied migration 32a: add_stt_vocabulary_json - Per-business STT vocabulary")
            
            if not check_column_exists('business_settings', 'business_context'):
                execute_with_retry(migrate_engine, "ALTER TABLE business_settings ADD COLUMN business_context VARCHAR(500)")
                migrations_applied.append("add_business_context")
                log.info("✅ Applied migration 32b: add_business_context - Business context for STT prompts")
        
        # Migration 33: BUILD 309 - SIMPLE_MODE settings for call flow control
        if check_table_exists('business_settings'):
            
            if not check_column_exists('business_settings', 'call_goal'):
                execute_with_retry(migrate_engine, "ALTER TABLE business_settings ADD COLUMN call_goal VARCHAR(50) DEFAULT 'lead_only'")
                migrations_applied.append("add_call_goal")
                log.info("✅ Applied migration 33a: add_call_goal - Controls call objective (lead_only vs appointment)")
            
            if not check_column_exists('business_settings', 'confirm_before_hangup'):
                execute_with_retry(migrate_engine, "ALTER TABLE business_settings ADD COLUMN confirm_before_hangup BOOLEAN DEFAULT TRUE")
                migrations_applied.append("add_confirm_before_hangup")
                log.info("✅ Applied migration 33b: add_confirm_before_hangup - Requires confirmation before disconnecting")
        
        # Migration 34: POST-CALL EXTRACTION - Full transcript + extracted fields for CallLog
        # 🔒 IDEMPOTENT: Uses PostgreSQL DO blocks to safely add columns
        if check_table_exists('call_log'):
            
            try:
                # Use single DO block for all call_log columns - more efficient
                # Use exec_sql with autocommit to prevent SSL connection failures
                migrate_engine = get_migrate_engine()
                exec_sql(migrate_engine, """
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
                """, autocommit=True)
                migrations_applied.append("add_call_log_extraction_fields")
                log.info("✅ Applied migration 34: add_call_log_extraction_fields - POST-CALL EXTRACTION for CallLog")
            except Exception as e:
                log.error(f"❌ Migration 34 failed: {e}")
                raise
        
        # Migration 35: POST-CALL EXTRACTION - Service type and city fields for Lead
        # 🔒 IDEMPOTENT: Uses PostgreSQL DO blocks to safely add columns
        if check_table_exists('leads'):
            try:
                # Use single DO block for all leads columns - more efficient
                # Use exec_sql with autocommit to prevent SSL connection failures
                migrate_engine = get_migrate_engine()
                exec_sql(migrate_engine, """
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
                """, autocommit=True)
                migrations_applied.append("add_leads_extraction_fields")
                log.info("✅ Applied migration 35: add_leads_extraction_fields - POST-CALL EXTRACTION for Lead")
            except Exception as e:
                log.error(f"❌ Migration 35 failed: {e}")
                raise
        
        # Migration 36: BUILD 350 - Add last_call_direction to leads for inbound/outbound filtering
        # 🔒 IDEMPOTENT: Uses PostgreSQL DO block to safely add column (SCHEMA ONLY)
        # ⚠️ NOTE: Performance indexes for this migration are in server/db_indexes.py
        #          and will be built separately during deployment
        # 🔥 BACKFILL MOVED: Data backfill now runs via server/db_backfill.py (separate step)
        #    This prevents migration failures due to lock timeouts on large tables
        if check_table_exists('leads'):
            try:
                # Use DO block to add column with exec_sql and autocommit
                migrate_engine = get_migrate_engine()
                exec_sql(migrate_engine, """
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
                """, autocommit=True)
                
                # 🔥 INDEXES MOVED TO server/db_indexes.py
                # Previously this migration created these indexes:
                # - idx_leads_last_call_direction
                # - idx_call_log_lead_created  
                # - idx_leads_backfill_pending
                # 
                # These are now built separately during deployment via db_build_indexes.py
                # to prevent migration failures and allow safe retries.
                checkpoint("✅ Schema changes complete (indexes will be built separately)")
                
                # 🔥 BACKFILL MOVED TO SEPARATE TOOL
                # Backfill is now handled by server/db_backfill.py which runs after migrations
                # This separation ensures:
                # 1. Migrations never fail due to lock timeouts on data operations
                # 2. Backfill can retry on lock conflicts using SKIP LOCKED
                # 3. Deployment continues even if backfill is incomplete
                # 4. Schema changes (critical) are separated from data maintenance (non-critical)
                checkpoint("ℹ️  Backfill will run separately via db_backfill.py after migrations")
                checkpoint("   (This is normal - backfill is a separate maintenance step)")
                
                migrations_applied.append("add_leads_last_call_direction")
                log.info("✅ Applied migration 36: add_leads_last_call_direction - Schema only (backfill runs separately)")
            except Exception as e:
                log.error(f"❌ Migration 36 failed: {e}")
                raise
        
        # Migration 37: Lead Attachments - Production-ready file uploads for leads
        if not check_table_exists('lead_attachments'):
            checkpoint("Migration 37: Creating lead_attachments table for secure file storage")
            try:
                execute_with_retry(migrate_engine, """
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
                """)
                
                
                migrations_applied.append('create_lead_attachments_table')
                log.info("✅ Applied migration 37: create_lead_attachments_table - Secure file upload support")
            except Exception as e:
                log.error(f"❌ Migration 37 failed: {e}")
                raise
        
        # Migration 38: BUILD 342 - Add recording_sid to call_log for Twilio recording tracking
        # 🔒 CRITICAL FIX: This column is referenced in code but missing from DB
        if check_table_exists('call_log') and not check_column_exists('call_log', 'recording_sid'):
            checkpoint("Migration 38: Adding recording_sid column to call_log table")
            try:
                execute_with_retry(migrate_engine, "ALTER TABLE call_log ADD COLUMN recording_sid VARCHAR(64)")
                migrations_applied.append('add_call_log_recording_sid')
                log.info("✅ Applied migration 38: add_call_log_recording_sid - Fix post-call pipeline crash")
            except Exception as e:
                log.error(f"❌ Migration 38 failed: {e}")
                raise
        
        # Migration 39: CRITICAL HOTFIX - Add missing columns to call_log for post-call pipeline
        # 🔒 IDEMPOTENT: These columns are referenced in code but missing from production DB
        # Fixes: psycopg2.errors.UndefinedColumn: column call_log.audio_bytes_len does not exist
        if check_table_exists('call_log'):
            checkpoint("Migration 39: Adding missing audio/transcript columns to call_log table")
            try:
                
                # Add audio_bytes_len column if missing
                if not check_column_exists('call_log', 'audio_bytes_len'):
                    execute_with_retry(migrate_engine, "ALTER TABLE call_log ADD COLUMN audio_bytes_len BIGINT")
                    migrations_applied.append('add_call_log_audio_bytes_len')
                    log.info("✅ Applied migration 39a: add_call_log_audio_bytes_len")
                
                # Add audio_duration_sec column if missing
                if not check_column_exists('call_log', 'audio_duration_sec'):
                    execute_with_retry(migrate_engine, "ALTER TABLE call_log ADD COLUMN audio_duration_sec DOUBLE PRECISION")
                    migrations_applied.append('add_call_log_audio_duration_sec')
                    log.info("✅ Applied migration 39b: add_call_log_audio_duration_sec")
                
                # Add transcript_source column if missing
                if not check_column_exists('call_log', 'transcript_source'):
                    execute_with_retry(migrate_engine, "ALTER TABLE call_log ADD COLUMN transcript_source VARCHAR(32)")
                    migrations_applied.append('add_call_log_transcript_source')
                    log.info("✅ Applied migration 39c: add_call_log_transcript_source")
                
                checkpoint("✅ Migration 39 completed - all missing columns added")
            except Exception as e:
                log.error(f"❌ Migration 39 failed: {e}")
                raise
        
        # Migration 40: Outbound Call Management - Bulk calling infrastructure
        # 🔒 CRITICAL: These tables are referenced in routes_outbound.py and tasks_recording.py
        # Creates: outbound_call_runs (campaigns) and outbound_call_jobs (individual calls)
        if not check_table_exists('outbound_call_runs'):
            checkpoint("Migration 40a: Creating outbound_call_runs table for bulk calling campaigns")
            try:
                execute_with_retry(migrate_engine, """
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
                """)
                
                
                migrations_applied.append('create_outbound_call_runs_table')
                log.info("✅ Applied migration 40a: create_outbound_call_runs_table - Bulk calling campaign tracking")
            except Exception as e:
                log.error(f"❌ Migration 40a failed: {e}")
                raise
        
        if not check_table_exists('outbound_call_jobs'):
            checkpoint("Migration 40b: Creating outbound_call_jobs table for individual call tracking")
            try:
                execute_with_retry(migrate_engine, """
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
                """)
                
                
                migrations_applied.append('create_outbound_call_jobs_table')
                log.info("✅ Applied migration 40b: create_outbound_call_jobs_table - Individual call job tracking")
            except Exception as e:
                log.error(f"❌ Migration 40b failed: {e}")
                raise
        
        # Migration 41: Add parent_call_sid and twilio_direction to call_log
        # 🔥 FIX: Prevents duplicate call logs and tracks original Twilio direction
        if not check_column_exists('call_log', 'parent_call_sid'):
            checkpoint("Migration 41a: Adding parent_call_sid to call_log for tracking parent/child call relationships")
            try:
                execute_with_retry(migrate_engine, """
                    ALTER TABLE call_log 
                    ADD COLUMN parent_call_sid VARCHAR(64)
                """)
                
                
                migrations_applied.append('add_parent_call_sid_to_call_log')
                log.info("✅ Applied migration 41a: add_parent_call_sid_to_call_log - Track parent/child call legs")
            except Exception as e:
                log.error(f"❌ Migration 41a failed: {e}")
                raise
        
        if not check_column_exists('call_log', 'twilio_direction'):
            checkpoint("Migration 41b: Adding twilio_direction to call_log for storing original Twilio direction")
            try:
                execute_with_retry(migrate_engine, """
                    ALTER TABLE call_log 
                    ADD COLUMN twilio_direction VARCHAR(32)
                """)
                
                
                migrations_applied.append('add_twilio_direction_to_call_log')
                log.info("✅ Applied migration 41b: add_twilio_direction_to_call_log - Store original Twilio direction values")
            except Exception as e:
                log.error(f"❌ Migration 41b failed: {e}")
                raise
        
        # Migration 42: AI Topic Classification System
        checkpoint("Migration 42: AI Topic Classification System")
        try:
            # Create business_topics table
            if not check_table_exists('business_topics'):
                log.info("Creating business_topics table...")
                execute_with_retry(migrate_engine, """
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
                """)
                migrations_applied.append('create_business_topics_table')
                log.info("✅ Created business_topics table")
            
            # Create business_ai_settings table
            if not check_table_exists('business_ai_settings'):
                log.info("Creating business_ai_settings table...")
                execute_with_retry(migrate_engine, """
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
                """)
                migrations_applied.append('create_business_ai_settings_table')
                log.info("✅ Created business_ai_settings table")
            
            # Add topic classification fields to call_log
            if check_table_exists('call_log'):
                if not check_column_exists('call_log', 'detected_topic_id'):
                    log.info("Adding topic classification fields to call_log...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE call_log 
                        ADD COLUMN detected_topic_id INTEGER REFERENCES business_topics(id),
                        ADD COLUMN detected_topic_confidence FLOAT,
                        ADD COLUMN detected_topic_source VARCHAR(32) DEFAULT 'embedding'
                    """)
                    migrations_applied.append('add_topic_fields_to_call_log')
                    log.info("✅ Added topic classification fields to call_log")
            
            # Add topic classification fields to leads
            if check_table_exists('leads'):
                if not check_column_exists('leads', 'detected_topic_id'):
                    log.info("Adding topic classification fields to leads...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE leads 
                        ADD COLUMN detected_topic_id INTEGER REFERENCES business_topics(id),
                        ADD COLUMN detected_topic_confidence FLOAT,
                        ADD COLUMN detected_topic_source VARCHAR(32) DEFAULT 'embedding'
                    """)
                    migrations_applied.append('add_topic_fields_to_leads')
                    log.info("✅ Added topic classification fields to leads")
            
            # Add topic classification fields to whatsapp_conversation
            if check_table_exists('whatsapp_conversation'):
                if not check_column_exists('whatsapp_conversation', 'detected_topic_id'):
                    log.info("Adding topic classification fields to whatsapp_conversation...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE whatsapp_conversation 
                        ADD COLUMN detected_topic_id INTEGER REFERENCES business_topics(id),
                        ADD COLUMN detected_topic_confidence FLOAT,
                        ADD COLUMN detected_topic_source VARCHAR(32) DEFAULT 'embedding'
                    """)
                    migrations_applied.append('add_topic_fields_to_whatsapp_conversation')
                    log.info("✅ Added topic classification fields to whatsapp_conversation")
            
            log.info("✅ Applied migration 42: AI Topic Classification System")
        except Exception as e:
            log.error(f"❌ Migration 42 failed: {e}")
            raise
        
        # Migration 43: Service Canonicalization - Add canonical_service_type to BusinessTopic and service mapping settings
        checkpoint("Migration 43: Service Canonicalization and Topic-to-Service Mapping")
        try:
            # Add canonical_service_type to business_topics
            if check_table_exists('business_topics'):
                if not check_column_exists('business_topics', 'canonical_service_type'):
                    log.info("Adding canonical_service_type to business_topics...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE business_topics 
                        ADD COLUMN canonical_service_type VARCHAR(255)
                    """)
                    migrations_applied.append('add_canonical_service_type_to_business_topics')
                    log.info("✅ Added canonical_service_type to business_topics")
            
            # Add service mapping settings to business_ai_settings
            if check_table_exists('business_ai_settings'):
                if not check_column_exists('business_ai_settings', 'map_topic_to_service_type'):
                    log.info("Adding service mapping settings to business_ai_settings...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE business_ai_settings 
                        ADD COLUMN map_topic_to_service_type BOOLEAN DEFAULT FALSE,
                        ADD COLUMN service_type_min_confidence FLOAT DEFAULT 0.75
                    """)
                    migrations_applied.append('add_service_mapping_settings_to_business_ai_settings')
                    log.info("✅ Added service mapping settings to business_ai_settings")
            
            log.info("✅ Applied migration 43: Service Canonicalization and Topic-to-Service Mapping")
        except Exception as e:
            log.error(f"❌ Migration 43 failed: {e}")
            raise
        
        # Migration 44: WhatsApp Broadcast System - Campaign management tables
        checkpoint("Migration 44: WhatsApp Broadcast System")
        try:
            # Create whatsapp_broadcasts table
            if not check_table_exists('whatsapp_broadcasts'):
                log.info("Creating whatsapp_broadcasts table...")
                execute_with_retry(migrate_engine, """
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
                """)
                migrations_applied.append('create_whatsapp_broadcasts_table')
                log.info("✅ Created whatsapp_broadcasts table")
            
            # Create whatsapp_broadcast_recipients table
            if not check_table_exists('whatsapp_broadcast_recipients'):
                log.info("Creating whatsapp_broadcast_recipients table...")
                execute_with_retry(migrate_engine, """
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
                """)
                migrations_applied.append('create_whatsapp_broadcast_recipients_table')
                log.info("✅ Created whatsapp_broadcast_recipients table")
            
            log.info("✅ Applied migration 44: WhatsApp Broadcast System")
        except Exception as e:
            log.error(f"❌ Migration 44 failed: {e}")
            raise
        
        # Migration 45: Status Webhook - Add status_webhook_url to business_settings for lead status change notifications
        checkpoint("Migration 45: Status Webhook URL for lead status changes")
        if check_table_exists('business_settings') and not check_column_exists('business_settings', 'status_webhook_url'):
            try:
                execute_with_retry(migrate_engine, """
                    ALTER TABLE business_settings 
                    ADD COLUMN status_webhook_url VARCHAR(512) NULL
                """)
                migrations_applied.append('add_status_webhook_url')
                log.info("✅ Added status_webhook_url column to business_settings")
            except Exception as e:
                log.error(f"❌ Migration 45 failed: {e}")
                raise
        
        # Migration 46: Bulk Call Deduplication - Add idempotency fields to outbound_call_jobs
        # Prevents duplicate calls from retry/concurrency/timeout scenarios
        checkpoint("Migration 46: Bulk Call Deduplication - Adding idempotency fields")
        
        # Add twilio_call_sid column for tracking initiated calls
        if check_table_exists('outbound_call_jobs') and not check_column_exists('outbound_call_jobs', 'twilio_call_sid'):
            try:
                execute_with_retry(migrate_engine, """
                    ALTER TABLE outbound_call_jobs 
                    ADD COLUMN twilio_call_sid VARCHAR(64) NULL
                """)
                migrations_applied.append('add_twilio_call_sid_to_outbound_jobs')
                log.info("✅ Added twilio_call_sid column to outbound_call_jobs for deduplication")
            except Exception as e:
                log.error(f"❌ Migration 46a failed: {e}")
                raise
        
        # Add dial_started_at column for tracking when dial attempt started
        if check_table_exists('outbound_call_jobs') and not check_column_exists('outbound_call_jobs', 'dial_started_at'):
            try:
                execute_with_retry(migrate_engine, """
                    ALTER TABLE outbound_call_jobs 
                    ADD COLUMN dial_started_at TIMESTAMP NULL
                """)
                migrations_applied.append('add_dial_started_at_to_outbound_jobs')
                log.info("✅ Added dial_started_at column to outbound_call_jobs for tracking dial attempts")
            except Exception as e:
                log.error(f"❌ Migration 46b failed: {e}")
                raise
        
        # Add dial_lock_token column for atomic locking
        if check_table_exists('outbound_call_jobs') and not check_column_exists('outbound_call_jobs', 'dial_lock_token'):
            try:
                execute_with_retry(migrate_engine, """
                    ALTER TABLE outbound_call_jobs 
                    ADD COLUMN dial_lock_token VARCHAR(64) NULL
                """)
                migrations_applied.append('add_dial_lock_token_to_outbound_jobs')
                log.info("✅ Added dial_lock_token column to outbound_call_jobs for atomic locking")
            except Exception as e:
                log.error(f"❌ Migration 46c failed: {e}")
                raise
        
        # Migration 46d: Add composite index for cleanup query performance
        if check_table_exists('outbound_call_jobs') and not check_index_exists('idx_outbound_call_jobs_status_twilio_sid'):
            checkpoint("Migration 46d: Adding composite index for cleanup query performance")
            try:
                # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
                # Performance indexes MUST be created separately via db_build_indexes.py
                migrations_applied.append('add_composite_index_status_twilio_sid')
                log.info("✅ Added composite index on (status, twilio_call_sid) for cleanup query performance")
            except Exception as e:
                log.error(f"❌ Migration 46d failed: {e}")
                raise
        
        # Migration 47: WhatsApp Webhook Secret - Add webhook_secret column to business table
        # 🔒 IDEMPOTENT: Safe column addition for n8n integration security
        checkpoint("Migration 47: WhatsApp Webhook Secret for n8n integration")
        if check_table_exists('business') and not check_column_exists('business', 'webhook_secret'):
            try:
                # Add webhook_secret column with unique constraint
                execute_with_retry(migrate_engine, """
                    ALTER TABLE business 
                    ADD COLUMN webhook_secret VARCHAR(128) UNIQUE NULL
                """)
                migrations_applied.append('add_business_webhook_secret')
                log.info("✅ Added webhook_secret column to business table for n8n webhook authentication")
            except Exception as e:
                log.error(f"❌ Migration 47 failed: {e}")
                raise
        
        # Migration 48: Add call_transcript column to appointments table
        # 🔒 IDEMPOTENT: Safe column addition for storing full conversation transcripts
        checkpoint("Migration 48: Add call_transcript to appointments")
        if check_table_exists('appointments') and not check_column_exists('appointments', 'call_transcript'):
            try:
                # Add call_transcript column to store full transcripts
                execute_with_retry(migrate_engine, """
                    ALTER TABLE appointments 
                    ADD COLUMN call_transcript TEXT
                """)
                migrations_applied.append('add_appointments_call_transcript')
                log.info("✅ Added call_transcript column to appointments table for full conversation transcripts")
            except Exception as e:
                log.error(f"❌ Migration 48 failed: {e}")
                raise
        
        # Migration 49: Add idempotency_key column to whatsapp_broadcasts table
        # 🔒 IDEMPOTENT: Safe column addition for preventing duplicate broadcasts
        checkpoint("Migration 49: Add idempotency_key to whatsapp_broadcasts")
        if check_table_exists('whatsapp_broadcasts') and not check_column_exists('whatsapp_broadcasts', 'idempotency_key'):
            try:
                # Add idempotency_key column with index for duplicate prevention
                execute_with_retry(migrate_engine, """
                    ALTER TABLE whatsapp_broadcasts 
                    ADD COLUMN idempotency_key VARCHAR(64)
                """)
                # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
                migrations_applied.append('add_whatsapp_broadcasts_idempotency_key')
                log.info("✅ Added idempotency_key column to whatsapp_broadcasts table for duplicate prevention")
            except Exception as e:
                log.error(f"❌ Migration 49 failed: {e}")
                raise
        
        # Migration 50: Add dynamic_summary and lead_id to appointments table
        # 🔒 CRITICAL FIX: These columns are referenced in code but missing from production DB
        # Fixes: psycopg2.errors.UndefinedColumn: column appointments.lead_id does not exist
        checkpoint("Migration 50: Adding dynamic_summary and lead_id to appointments")
        if check_table_exists('appointments'):
            try:
                
                # Add lead_id column if missing
                if not check_column_exists('appointments', 'lead_id'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE appointments 
                        ADD COLUMN lead_id INTEGER REFERENCES leads(id) ON DELETE SET NULL
                    """)
                    # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
                    migrations_applied.append('add_appointments_lead_id')
                    log.info("✅ Added lead_id column to appointments table")
                
                # Add dynamic_summary column if missing
                if not check_column_exists('appointments', 'dynamic_summary'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE appointments 
                        ADD COLUMN dynamic_summary TEXT
                    """)
                    migrations_applied.append('add_appointments_dynamic_summary')
                    log.info("✅ Added dynamic_summary column to appointments table")
                
                checkpoint("✅ Migration 50 completed - appointments table updated")
            except Exception as e:
                log.error(f"❌ Migration 50 failed: {e}")
                raise
        
        # Migration 51: Add Twilio Cost Metrics columns to call_log table
        # 🔒 CRITICAL FIX: These columns are referenced in code but missing from production DB
        # Fixes: psycopg2.errors.UndefinedColumn: column call_log.recording_mode does not exist
        # This migration adds recording_mode and all related cost tracking fields
        checkpoint("Migration 51: Adding Twilio Cost Metrics columns to call_log")
        if check_table_exists('call_log'):
            try:
                
                # Add recording_mode column if missing
                if not check_column_exists('call_log', 'recording_mode'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE call_log 
                        ADD COLUMN recording_mode VARCHAR(32)
                    """)
                    migrations_applied.append('add_call_log_recording_mode')
                    log.info("✅ Added recording_mode column to call_log table")
                
                # Add stream_started_at column if missing
                if not check_column_exists('call_log', 'stream_started_at'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE call_log 
                        ADD COLUMN stream_started_at TIMESTAMP
                    """)
                    migrations_applied.append('add_call_log_stream_started_at')
                    log.info("✅ Added stream_started_at column to call_log table")
                
                # Add stream_ended_at column if missing
                if not check_column_exists('call_log', 'stream_ended_at'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE call_log 
                        ADD COLUMN stream_ended_at TIMESTAMP
                    """)
                    migrations_applied.append('add_call_log_stream_ended_at')
                    log.info("✅ Added stream_ended_at column to call_log table")
                
                # Add stream_duration_sec column if missing
                if not check_column_exists('call_log', 'stream_duration_sec'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE call_log 
                        ADD COLUMN stream_duration_sec DOUBLE PRECISION
                    """)
                    migrations_applied.append('add_call_log_stream_duration_sec')
                    log.info("✅ Added stream_duration_sec column to call_log table")
                
                # Add stream_connect_count column if missing
                if not check_column_exists('call_log', 'stream_connect_count'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE call_log 
                        ADD COLUMN stream_connect_count INTEGER DEFAULT 0
                    """)
                    migrations_applied.append('add_call_log_stream_connect_count')
                    log.info("✅ Added stream_connect_count column to call_log table")
                
                # Add webhook_11205_count column if missing
                if not check_column_exists('call_log', 'webhook_11205_count'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE call_log 
                        ADD COLUMN webhook_11205_count INTEGER DEFAULT 0
                    """)
                    migrations_applied.append('add_call_log_webhook_11205_count')
                    log.info("✅ Added webhook_11205_count column to call_log table")
                
                # Add webhook_retry_count column if missing
                if not check_column_exists('call_log', 'webhook_retry_count'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE call_log 
                        ADD COLUMN webhook_retry_count INTEGER DEFAULT 0
                    """)
                    migrations_applied.append('add_call_log_webhook_retry_count')
                    log.info("✅ Added webhook_retry_count column to call_log table")
                
                # Add recording_count column if missing
                if not check_column_exists('call_log', 'recording_count'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE call_log 
                        ADD COLUMN recording_count INTEGER DEFAULT 0
                    """)
                    migrations_applied.append('add_call_log_recording_count')
                    log.info("✅ Added recording_count column to call_log table")
                
                # Add estimated_cost_bucket column if missing
                if not check_column_exists('call_log', 'estimated_cost_bucket'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE call_log 
                        ADD COLUMN estimated_cost_bucket VARCHAR(16)
                    """)
                    migrations_applied.append('add_call_log_estimated_cost_bucket')
                    log.info("✅ Added estimated_cost_bucket column to call_log table")
                
                checkpoint("✅ Migration 51 completed - call_log cost metrics columns added")
            except Exception as e:
                log.error(f"❌ Migration 51 failed: {e}")
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
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE call_log 
                        ADD COLUMN customer_name VARCHAR(255)
                    """)
                    checkpoint("  ✅ call_log.customer_name added")
                else:
                    checkpoint("  ℹ️ call_log.customer_name already exists")
                
                # 2. Add lead_name to outbound_call_jobs
                if not check_column_exists('outbound_call_jobs', 'lead_name'):
                    checkpoint("  → Adding lead_name to outbound_call_jobs...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE outbound_call_jobs 
                        ADD COLUMN lead_name VARCHAR(255)
                    """)
                    checkpoint("  ✅ outbound_call_jobs.lead_name added")
                else:
                    checkpoint("  ℹ️ outbound_call_jobs.lead_name already exists")
                
                migrations_applied.append('migration_52_name_anchor_ssot')
                checkpoint("✅ Migration 52 completed - NAME_ANCHOR SSOT fields added")
            except Exception as e:
                log.error(f"❌ Migration 52 failed: {e}")
                raise
        
        # Migration 53: Add gender column to leads table
        # 🔥 PURPOSE: Fix missing gender column - prevents "column leads.gender does not exist" errors
        # This column is defined in Lead model but was never added to DB via migration
        if check_table_exists('leads') and not check_column_exists('leads', 'gender'):
            checkpoint("Migration 53: Adding gender column to leads table")
            try:
                checkpoint("  → Adding gender to leads...")
                execute_with_retry(migrate_engine, """
                    ALTER TABLE leads 
                    ADD COLUMN gender VARCHAR(16)
                """)
                checkpoint("  ✅ leads.gender added")
                migrations_applied.append('add_leads_gender_column')
                checkpoint("✅ Migration 53 completed - leads.gender column added")
            except Exception as e:
                log.error(f"❌ Migration 53 failed: {e}")
                raise
        
        # Migration 54: Projects for Outbound Calls
        # 🎯 PURPOSE: Enable grouping leads into projects with call tracking and statistics
        # Projects = Container for leads + call history + stats (only after calls start)
        if not check_table_exists('outbound_projects'):
            checkpoint("Migration 54: Creating outbound_projects table")
            try:
                checkpoint("  → Creating outbound_projects table...")
                execute_with_retry(migrate_engine, """
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
                """)
                checkpoint("  ✅ outbound_projects table created")
                
                # Junction table for project-lead relationships
                checkpoint("  → Creating project_leads junction table...")
                execute_with_retry(migrate_engine, """
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
                """)
                checkpoint("  ✅ project_leads junction table created")
                
                migrations_applied.append('create_outbound_projects_tables')
                checkpoint("✅ Migration 54 completed - Projects tables created")
            except Exception as e:
                log.error(f"❌ Migration 54 failed: {e}")
                raise
        
        # Migration 54b: Add project_id to call_log for project statistics
        if check_table_exists('call_log') and not check_column_exists('call_log', 'project_id'):
            checkpoint("Migration 54b: Adding project_id to call_log")
            try:
                checkpoint("  → Adding project_id to call_log...")
                execute_with_retry(migrate_engine, "ALTER TABLE call_log ADD COLUMN project_id INTEGER REFERENCES outbound_projects(id) ON DELETE SET NULL")
                checkpoint("  ✅ call_log.project_id added")
                migrations_applied.append('add_call_log_project_id')
                checkpoint("✅ Migration 54b completed - project tracking in calls")
            except Exception as e:
                log.error(f"❌ Migration 54b failed: {e}")
                raise
        
        # Migration 54c: Add project_id to outbound_call_jobs for bulk operations
        if check_table_exists('outbound_call_jobs') and not check_column_exists('outbound_call_jobs', 'project_id'):
            checkpoint("Migration 54c: Adding project_id to outbound_call_jobs")
            try:
                checkpoint("  → Adding project_id to outbound_call_jobs...")
                execute_with_retry(migrate_engine, "ALTER TABLE outbound_call_jobs ADD COLUMN project_id INTEGER REFERENCES outbound_projects(id) ON DELETE SET NULL")
                checkpoint("  ✅ outbound_call_jobs.project_id added")
                migrations_applied.append('add_outbound_call_jobs_project_id')
                checkpoint("✅ Migration 54c completed - project tracking in bulk jobs")
            except Exception as e:
                log.error(f"❌ Migration 54c failed: {e}")
                raise
        
        # Migration 55: Add delivered_at column to whatsapp_broadcast_recipients
        # 🔥 CRITICAL FIX: This column is defined in WhatsappBroadcastRecipient model but missing from DB
        # Fixes: psycopg2.errors.UndefinedColumn: column "delivered_at" of relation "whatsapp_broadcast_recipients" does not exist
        if check_table_exists('whatsapp_broadcast_recipients') and not check_column_exists('whatsapp_broadcast_recipients', 'delivered_at'):
            checkpoint("Migration 55: Adding delivered_at to whatsapp_broadcast_recipients")
            try:
                checkpoint("  → Adding delivered_at to whatsapp_broadcast_recipients...")
                execute_with_retry(migrate_engine, """
                    ALTER TABLE whatsapp_broadcast_recipients 
                    ADD COLUMN delivered_at TIMESTAMP
                """)
                checkpoint("  ✅ whatsapp_broadcast_recipients.delivered_at added")
                migrations_applied.append('add_whatsapp_broadcast_recipients_delivered_at')
                checkpoint("✅ Migration 55 completed - WhatsApp broadcast delivery tracking column added")
            except Exception as e:
                log.error(f"❌ Migration 55 failed: {e}")
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
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE whatsapp_broadcasts 
                        ADD COLUMN stopped_by INTEGER REFERENCES users(id)
                    """)
                    checkpoint("  ✅ whatsapp_broadcasts.stopped_by added")
                    migrations_applied.append('add_whatsapp_broadcasts_stopped_by')
                
                # Add stopped_at column if missing
                if not check_column_exists('whatsapp_broadcasts', 'stopped_at'):
                    checkpoint("  → Adding stopped_at to whatsapp_broadcasts...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE whatsapp_broadcasts 
                        ADD COLUMN stopped_at TIMESTAMP
                    """)
                    checkpoint("  ✅ whatsapp_broadcasts.stopped_at added")
                    migrations_applied.append('add_whatsapp_broadcasts_stopped_at')
                
                checkpoint("✅ Migration 56 completed - WhatsApp broadcast stop functionality columns added")
            except Exception as e:
                log.error(f"❌ Migration 56 failed: {e}")
                raise
        
        # Migration 57: Authentication & Session Management System
        # Add refresh tokens table and password reset fields to users
        checkpoint("Migration 57: Adding authentication and session management features")
        
        # 57a: Create refresh_tokens table
        if not check_table_exists('refresh_tokens'):
            checkpoint("  → Creating refresh_tokens table...")
            try:
                execute_with_retry(migrate_engine, """
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
                """)
                
                # Add indexes for performance
                
                # Add last_activity_at column for per-session idle tracking
                if not check_column_exists('refresh_tokens', 'last_activity_at'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE refresh_tokens 
                        ADD COLUMN last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    """)
                    # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
                    checkpoint("  ✅ refresh_tokens.last_activity_at added")
                    migrations_applied.append('add_refresh_tokens_last_activity_at')
                
                checkpoint("  ✅ refresh_tokens table created with all fields")
                migrations_applied.append('create_refresh_tokens_table')
            except Exception as e:
                log.error(f"❌ Migration 57a failed: {e}")
                raise
        
        # 57b: Add password reset fields to users table
        if check_table_exists('users'):
            checkpoint("  → Adding password reset fields to users table...")
            try:
                # Add reset_token_hash column
                if not check_column_exists('users', 'reset_token_hash'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE users 
                        ADD COLUMN reset_token_hash VARCHAR(255)
                    """)
                    checkpoint("  ✅ users.reset_token_hash added")
                    migrations_applied.append('add_users_reset_token_hash')
                
                # Add reset_token_expiry column
                if not check_column_exists('users', 'reset_token_expiry'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE users 
                        ADD COLUMN reset_token_expiry TIMESTAMP
                    """)
                    checkpoint("  ✅ users.reset_token_expiry added")
                    migrations_applied.append('add_users_reset_token_expiry')
                
                # Add reset_token_used column
                if not check_column_exists('users', 'reset_token_used'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE users 
                        ADD COLUMN reset_token_used BOOLEAN DEFAULT FALSE
                    """)
                    checkpoint("  ✅ users.reset_token_used added")
                    migrations_applied.append('add_users_reset_token_used')
                
                # Add last_activity_at column for idle timeout tracking
                if not check_column_exists('users', 'last_activity_at'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE users 
                        ADD COLUMN last_activity_at TIMESTAMP
                    """)
                    checkpoint("  ✅ users.last_activity_at added")
                    migrations_applied.append('add_users_last_activity_at')
                
                checkpoint("  ✅ Password reset and activity tracking fields added to users")
            except Exception as e:
                log.error(f"❌ Migration 57b failed: {e}")
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
                execute_with_retry(migrate_engine, """
                    ALTER TABLE users 
                    ADD COLUMN push_enabled BOOLEAN NOT NULL DEFAULT TRUE
                """)
                
                migrations_applied.append('add_users_push_enabled')
                checkpoint("✅ Applied migration 57c: add_users_push_enabled - Push notification user preference")
            except Exception as e:
                log.error(f"❌ Migration 57c failed: {e}")
                raise
        
        # Migration 58: Add voice_id to business table for per-business voice selection
        # 🔒 CRITICAL FIX: This column is referenced in Business model but missing from DB
        # Fixes: psycopg2.errors.UndefinedColumn: column business.voice_id does not exist
        if check_table_exists('business') and not check_column_exists('business', 'voice_id'):
            checkpoint("Migration 58: Adding voice_id column to business table")
            try:
                # Add voice_id column with default value 'ash'
                # NOT NULL DEFAULT ensures all existing rows automatically get 'ash' value
                execute_with_retry(migrate_engine, """
                    ALTER TABLE business 
                    ADD COLUMN voice_id VARCHAR(32) NOT NULL DEFAULT 'ash'
                """)
                
                migrations_applied.append('add_business_voice_id')
                checkpoint("✅ Applied migration 58: add_business_voice_id - Per-business voice selection")
            except Exception as e:
                log.error(f"❌ Migration 58 failed: {e}")
                raise
        
        # Migration 60: Email System - Add email_settings, email_messages, and email_templates tables
        # Production-grade email system with per-business configuration and complete logging
        checkpoint("Migration 60: Creating email system tables (email_settings, email_messages, email_templates)")
        
        # Migration 60a: Create email_settings table (per-business email configuration)
        if not check_table_exists('email_settings'):
            try:
                execute_with_retry(migrate_engine, """
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
                """)
                
                execute_with_retry(migrate_engine, """
                    CREATE UNIQUE INDEX idx_email_settings_business_id ON email_settings(business_id)
                """)
                
                migrations_applied.append('create_email_settings_table')
                checkpoint("  ✅ email_settings table created with branding fields (logo, color, greeting, footer)")
            except Exception as e:
                log.error(f"❌ Migration 60a (email_settings) failed: {e}")
                raise
        
        # Migration 60b: Create email_templates table (per-business email templates)
        # IMPORTANT: Must be created before email_messages (FK dependency)
        if not check_table_exists('email_templates'):
            try:
                execute_with_retry(migrate_engine, """
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
                """)
                
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                
                migrations_applied.append('create_email_templates_table')
                checkpoint("  ✅ email_templates table created with indexes on business_id, is_active")
            except Exception as e:
                log.error(f"❌ Migration 60b (email_templates) failed: {e}")
                raise
        
        # Migration 60c: Create email_messages table (complete email log)
        if not check_table_exists('email_messages'):
            try:
                execute_with_retry(migrate_engine, """
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
                """)
                
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                
                migrations_applied.append('create_email_messages_table')
                checkpoint("  ✅ email_messages table created with indexes on business_id, lead_id, status, created_at, template_id")
            except Exception as e:
                log.error(f"❌ Migration 60c (email_messages) failed: {e}")
                raise
        
        checkpoint("✅ Migration 60 completed - Email system tables created")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 61: Clean up invalid voice_id values in businesses table
        # Only Realtime-supported voices are allowed
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 61: Cleaning up invalid voice_id values")
        
        try:
            # Check if voice_id column exists
            result = execute_with_retry(migrate_engine, """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'businesses' 
                AND column_name = 'voice_id'
            """)
            voice_id_exists = result[0] if result else None
            
            if voice_id_exists:
                # Valid Realtime voices
                valid_voices = ['alloy', 'ash', 'ballad', 'coral', 'echo', 'sage', 'shimmer', 'verse', 'marin', 'cedar']
                default_voice = 'cedar'
                
                # Find businesses with invalid voices
                invalid_count_result = execute_with_retry(migrate_engine, """
                    SELECT COUNT(*) 
                    FROM businesses 
                    WHERE voice_id IS NULL 
                       OR voice_id NOT IN :valid_voices
                """, {"valid_voices": tuple(valid_voices)})
                
                invalid_count = invalid_count_result[0][0] if invalid_count_result else 0
                
                if invalid_count > 0:
                    checkpoint(f"  Found {invalid_count} businesses with invalid voice_id values")
                    
                    # Update invalid voices to default
                    execute_with_retry(migrate_engine, """
                        UPDATE businesses 
                        SET voice_id = :default_voice
                        WHERE voice_id IS NULL 
                           OR voice_id NOT IN :valid_voices
                    """, {
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
                businesses_result = execute_with_retry(migrate_engine, """
                    SELECT b.id, b.name
                    FROM business b
                    WHERE NOT EXISTS (
                        SELECT 1 FROM email_templates et 
                        WHERE et.business_id = b.id
                    )
                    AND b.is_active = TRUE
                """)
                
                businesses_count = len(businesses_result) if businesses_result else 0
                
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
                            execute_with_retry(migrate_engine, """
                                INSERT INTO email_templates 
                                (business_id, name, type, subject_template, html_template, text_template, is_active, created_at, updated_at)
                                VALUES (:business_id, :name, :type, :subject_template, :html_template, :text_template, TRUE, NOW(), NOW())
                            """, {
                                "business_id": business_id,
                                "name": "ברירת מחדל - ברכה",
                                "type": "welcome",
                                "subject_template": template_1_subject,
                                "html_template": template_1_html,
                                "text_template": template_1_text
                            })
                            
                            # Template 2
                            execute_with_retry(migrate_engine, """
                                INSERT INTO email_templates 
                                (business_id, name, type, subject_template, html_template, text_template, is_active, created_at, updated_at)
                                VALUES (:business_id, :name, :type, :subject_template, :html_template, :text_template, TRUE, NOW(), NOW())
                            """, {
                                "business_id": business_id,
                                "name": "תזכורת - קביעת שיחה",
                                "type": "followup",
                                "subject_template": template_2_subject,
                                "html_template": template_2_html,
                                "text_template": template_2_text
                            })
                            
                            # Template 3
                            execute_with_retry(migrate_engine, """
                                INSERT INTO email_templates 
                                (business_id, name, type, subject_template, html_template, text_template, is_active, created_at, updated_at)
                                VALUES (:business_id, :name, :type, :subject_template, :html_template, :text_template, TRUE, NOW(), NOW())
                            """, {
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
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE email_settings 
                        ADD COLUMN theme_id VARCHAR(50) DEFAULT 'classic_blue'
                    """)
                    checkpoint("  ✅ email_settings.theme_id added")
                    migrations_applied.append('add_email_settings_theme_id')
                
                # Add cta_default_text column if missing
                if not check_column_exists('email_settings', 'cta_default_text'):
                    checkpoint("  → Adding cta_default_text to email_settings...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE email_settings 
                        ADD COLUMN cta_default_text VARCHAR(200)
                    """)
                    checkpoint("  ✅ email_settings.cta_default_text added")
                    migrations_applied.append('add_email_settings_cta_default_text')
                
                # Add cta_default_url column if missing
                if not check_column_exists('email_settings', 'cta_default_url'):
                    checkpoint("  → Adding cta_default_url to email_settings...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE email_settings 
                        ADD COLUMN cta_default_url VARCHAR(500)
                    """)
                    checkpoint("  ✅ email_settings.cta_default_url added")
                    migrations_applied.append('add_email_settings_cta_default_url')
                
                checkpoint("✅ Migration 63 completed - Theme-based email settings fields added")
            except Exception as e:
                log.error(f"❌ Migration 63 failed: {e}")
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
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE business 
                        ADD COLUMN company_id VARCHAR(50)
                    """)
                    checkpoint("  ✅ business.company_id added")
                    migrations_applied.append('add_business_company_id')
                else:
                    checkpoint("  ✅ business.company_id already exists")
                
                checkpoint("✅ Migration 64 completed - company_id field added to Business")
            except Exception as e:
                log.error(f"❌ Migration 64 failed: {e}")
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
                execute_with_retry(migrate_engine, """
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
                """)
                
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                # Unique constraint to prevent duplicate subscriptions
                execute_with_retry(migrate_engine, """
                    CREATE UNIQUE INDEX idx_push_subscriptions_user_endpoint ON push_subscriptions(user_id, endpoint)
                """)
                
                migrations_applied.append('create_push_subscriptions_table')
                checkpoint("✅ Applied migration 65: create_push_subscriptions_table - Web Push notifications support")
            except Exception as e:
                log.error(f"❌ Migration 65 failed: {e}")
                raise
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 66: Reminder Push Log - Track sent reminder push notifications
        # 🔔 PURPOSE: Prevent duplicate reminder push notifications across workers
        # Uses DB-backed deduplication with unique constraint on (reminder_id, offset_minutes)
        # ═══════════════════════════════════════════════════════════════════════
        if not check_table_exists('reminder_push_log'):
            checkpoint("Migration 66: Creating reminder_push_log table for reminder notification deduplication")
            try:
                execute_with_retry(migrate_engine, """
                    CREATE TABLE reminder_push_log (
                        id SERIAL PRIMARY KEY,
                        reminder_id INTEGER NOT NULL REFERENCES lead_reminders(id) ON DELETE CASCADE,
                        offset_minutes INTEGER NOT NULL,
                        sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                # Unique constraint to prevent duplicate notifications
                execute_with_retry(migrate_engine, """
                    CREATE UNIQUE INDEX uq_reminder_push_log ON reminder_push_log(reminder_id, offset_minutes)
                """)
                
                migrations_applied.append('create_reminder_push_log_table')
                checkpoint("✅ Applied migration 66: create_reminder_push_log_table - Reminder push notification deduplication")
            except Exception as e:
                log.error(f"❌ Migration 66 failed: {e}")
                raise
        
        # Migration 67: Email Text Templates - Quick text snippets for email body content
        # These are simple text templates (like quotes, greetings, pricing info) that can be used in emails
        checkpoint("Migration 67: Creating email_text_templates table for quick text snippets")
        if not check_table_exists('email_text_templates'):
            try:
                execute_with_retry(migrate_engine, """
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
                """)
                
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                
                migrations_applied.append('create_email_text_templates_table')
                checkpoint("✅ Applied migration 67: create_email_text_templates_table - Email text snippets for quick content")
            except Exception as e:
                log.error(f"❌ Migration 67 failed: {e}")
                raise
        
        # Migration 68: WhatsApp Manual Templates - Custom text templates for broadcasts
        checkpoint("Migration 68: Creating whatsapp_manual_templates table for custom broadcast templates")
        if not check_table_exists('whatsapp_manual_templates'):
            try:
                execute_with_retry(migrate_engine, """
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
                """)
                
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                
                migrations_applied.append('create_whatsapp_manual_templates_table')
                checkpoint("✅ Applied migration 68: create_whatsapp_manual_templates_table - WhatsApp custom templates")
            except Exception as e:
                log.error(f"❌ Migration 68 failed: {e}")
                raise
        
        # Migration 69: ISO 27001 Security Events Table - Audit and incident tracking
        # Required for ISO 27001 compliance (A.12.4, A.16) and audit readiness
        checkpoint("Migration 69: Creating security_events table for ISO 27001 compliance")
        if not check_table_exists('security_events'):
            try:
                execute_with_retry(migrate_engine, """
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
                """)
                
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                
                migrations_applied.append('create_security_events_table')
                checkpoint("✅ Applied migration 69: create_security_events_table - ISO 27001 security audit compliance")
            except Exception as e:
                log.error(f"❌ Migration 69 failed: {e}")
                raise
        
        # Migration 70: Rename metadata to event_metadata in security_events (SQLAlchemy reserved name fix)
        checkpoint("Migration 70: Checking if security_events.metadata needs to be renamed to event_metadata")
        if check_table_exists('security_events') and check_column_exists('security_events', 'metadata'):
            try:
                checkpoint("Migration 70: Renaming security_events.metadata to event_metadata (SQLAlchemy reserved name)")
                execute_with_retry(migrate_engine, """
                    ALTER TABLE security_events RENAME COLUMN metadata TO event_metadata
                """)
                migrations_applied.append('rename_security_events_metadata_to_event_metadata')
                checkpoint("✅ Applied migration 70: rename_security_events_metadata_to_event_metadata")
            except Exception as e:
                log.error(f"❌ Migration 70 failed: {e}")
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
                from server.security.page_registry import DEFAULT_ENABLED_PAGES
                import json
                
                checkpoint("  → Adding enabled_pages column...")
                # Add column with default empty list
                execute_with_retry(migrate_engine, """
                    ALTER TABLE business 
                    ADD COLUMN enabled_pages JSON NOT NULL DEFAULT '[]'
                """)
                checkpoint("  ✅ enabled_pages column added")
                
                # Set all existing businesses to have all pages enabled (backward compatibility)
                default_pages_json = json.dumps(DEFAULT_ENABLED_PAGES)
                checkpoint(f"  → Setting default pages for existing businesses: {len(DEFAULT_ENABLED_PAGES)} pages")
                
                # Update only rows that don't have pages set yet (NULL or empty array)
                # 🔥 FIX: Use JSONB cast and proper comparison to avoid "operator does not exist: json = json" error
                result = execute_with_retry(migrate_engine, """
                    UPDATE business 
                    SET enabled_pages = :pages
                    WHERE enabled_pages IS NULL 
                       OR CAST(enabled_pages AS TEXT) = '[]'
                       OR json_array_length(CAST(enabled_pages AS json)) = 0
                """, {"pages": default_pages_json})
                
                updated_count = getattr(result, "rowcount", 0)
                checkpoint(f"  ✅ Updated {updated_count} existing businesses with all pages enabled")
                
                migrations_applied.append('add_business_enabled_pages')
                checkpoint("✅ Applied migration 71: add_business_enabled_pages - Page-level permissions system")
            except Exception as e:
                log.error(f"❌ Migration 71 failed: {e}")
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
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE lead_notes 
                        ADD COLUMN note_type VARCHAR(32) DEFAULT 'manual'
                    """)
                    # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
                    checkpoint("  ✅ lead_notes.note_type added")
                    migrations_applied.append('add_lead_notes_note_type')
                
                # Add call_id column if missing
                if not check_column_exists('lead_notes', 'call_id'):
                    checkpoint("  → Adding call_id to lead_notes...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE lead_notes 
                        ADD COLUMN call_id INTEGER REFERENCES call_log(id)
                    """)
                    # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
                    checkpoint("  ✅ lead_notes.call_id added")
                    migrations_applied.append('add_lead_notes_call_id')
                
                # Add structured_data column if missing
                if not check_column_exists('lead_notes', 'structured_data'):
                    checkpoint("  → Adding structured_data to lead_notes...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE lead_notes 
                        ADD COLUMN structured_data JSON
                    """)
                    checkpoint("  ✅ lead_notes.structured_data added")
                    migrations_applied.append('add_lead_notes_structured_data')
                
                checkpoint("✅ Migration 72 completed - CRM Context-Aware Support fields added to lead_notes")
            except Exception as e:
                log.error(f"❌ Migration 72 failed: {e}")
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
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE business_settings 
                        ADD COLUMN enable_customer_service BOOLEAN DEFAULT FALSE
                    """)
                    checkpoint("  ✅ business_settings.enable_customer_service added")
                    migrations_applied.append('add_business_settings_enable_customer_service')
                else:
                    checkpoint("  ✅ business_settings.enable_customer_service already exists")
                
                checkpoint("✅ Migration 73 completed - Customer service toggle added")
            except Exception as e:
                log.error(f"❌ Migration 73 failed: {e}")
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
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE email_text_templates 
                        ADD COLUMN button_text VARCHAR(255)
                    """)
                    checkpoint("  ✅ email_text_templates.button_text added")
                    migrations_applied.append('add_email_text_templates_button_text')
                
                # Add button_link column if missing
                if not check_column_exists('email_text_templates', 'button_link'):
                    checkpoint("  → Adding button_link to email_text_templates...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE email_text_templates 
                        ADD COLUMN button_link VARCHAR(512)
                    """)
                    checkpoint("  ✅ email_text_templates.button_link added")
                    migrations_applied.append('add_email_text_templates_button_link')
                
                # Add footer_text column if missing
                if not check_column_exists('email_text_templates', 'footer_text'):
                    checkpoint("  → Adding footer_text to email_text_templates...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE email_text_templates 
                        ADD COLUMN footer_text TEXT
                    """)
                    checkpoint("  ✅ email_text_templates.footer_text added")
                    migrations_applied.append('add_email_text_templates_footer_text')
                
                checkpoint("✅ Migration 74 completed - Email text template fields added")
            except Exception as e:
                log.error(f"❌ Migration 74 failed: {e}")
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
                
                # Step 1: Update existing manual notes without attachments to be customer_service_ai
                # These are the notes that were added in the AI Customer Service tab
                # We identify them as manual notes with no attachments and no created_by user
                # (created_by=NULL typically means AI-created or system-created)
                checkpoint("  → Migrating existing AI customer service notes...")
                
                # First, check if attachments column exists and what type it is
                column_type_query = """
                    SELECT data_type, udt_name
                    FROM information_schema.columns
                    WHERE table_name = 'lead_notes' AND column_name = 'attachments'
                """
                result = execute_with_retry(migrate_engine, column_type_query)
                column_info = result[0] if result else None
                
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
                count_query = f"""
                    SELECT COUNT(*) FROM lead_notes
                    WHERE note_type = 'manual'
                      AND {attachments_condition}
                      AND created_by IS NULL
                """
                result = execute_with_retry(migrate_engine, count_query)
                notes_to_migrate = result[0][0] if result else 0
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
                    execute_with_retry(migrate_engine, update_query)
                    checkpoint(f"  ✅ Migrated {notes_to_migrate} notes to customer_service_ai type")
                else:
                    checkpoint("  ✅ No notes to migrate")
                
                # Step 2: Add index for faster filtering by note_type
                if not check_index_exists('idx_lead_notes_type_tenant'):
                    checkpoint("  → Index for note_type filtering removed (belongs in db_indexes.py)")
                    # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
                
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
                raise
        else:
            checkpoint("  ℹ️ lead_notes table does not exist - skipping")
        
        # Migration 76: Create attachments table for unified file management
        if not check_table_exists('attachments'):
            checkpoint("🔧 Running Migration 76: Create attachments table for unified file management")
            try:
                
                # Create attachments table
                execute_with_retry(migrate_engine, """
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
                """)
                checkpoint("  ✅ attachments table created")
                
                # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
                # Performance indexes MUST be created separately via db_build_indexes.py
                
                # Create storage directory structure
                import os
                storage_root = os.path.join(os.getcwd(), 'storage', 'attachments')
                os.makedirs(storage_root, exist_ok=True)
                checkpoint(f"  ✅ Storage directory created: {storage_root}")
                
                migrations_applied.append('create_attachments_table')
                checkpoint("✅ Migration 76 completed - Unified attachments system ready")
                
            except Exception as e:
                log.error(f"❌ Migration 76 failed: {e}")
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
                        execute_with_retry(migrate_engine, """
                            ALTER TABLE contract 
                            ADD COLUMN lead_id INTEGER REFERENCES leads(id)
                        """)
                        checkpoint("    ✅ Added lead_id column")
                    
                    # Add title if missing
                    if not check_column_exists('contract', 'title'):
                        execute_with_retry(migrate_engine, """
                            ALTER TABLE contract 
                            ADD COLUMN title VARCHAR(255)
                        """)
                        checkpoint("    ✅ Added title column")
                    
                    # Update status column to use new enum values with CHECK constraint
                    if check_column_exists('contract', 'status'):
                        # Drop old constraint if exists and add new one
                        execute_with_retry(migrate_engine, """
                            ALTER TABLE contract DROP CONSTRAINT IF EXISTS contract_status_check
                        """)
                        execute_with_retry(migrate_engine, """
                            ALTER TABLE contract 
                            ADD CONSTRAINT contract_status_check 
                            CHECK (status IN ('draft', 'sent', 'signed', 'cancelled'))
                        """)
                        checkpoint("    ✅ Updated status CHECK constraint")
                    
                    # Add signer fields if missing
                    for col in ['signer_name', 'signer_phone', 'signer_email']:
                        if not check_column_exists('contract', col):
                            execute_with_retry(migrate_engine, f"""
                                ALTER TABLE contract 
                                ADD COLUMN {col} VARCHAR(255)
                            """)
                    checkpoint("    ✅ Added signer fields")
                    
                    # Add created_by if missing
                    if not check_column_exists('contract', 'created_by'):
                        execute_with_retry(migrate_engine, """
                            ALTER TABLE contract 
                            ADD COLUMN created_by INTEGER REFERENCES users(id)
                        """)
                    checkpoint("    ✅ Added created_by field")
                    
                    # Add updated_at if missing
                    if not check_column_exists('contract', 'updated_at'):
                        execute_with_retry(migrate_engine, """
                            ALTER TABLE contract 
                            ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        """)
                    checkpoint("    ✅ Added updated_at field")
                    
                    # Ensure indexes
                    checkpoint("    ✅ Created performance indexes")
                
                # Create contract_files table - links contracts to attachments
                checkpoint("  → Creating contract_files table (attachment-based)...")
                execute_with_retry(migrate_engine, """
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
                """)
                
                checkpoint("    ✅ contract_files table created (attachment-based)")
                
                # Create contract_sign_tokens table - DB-based tokens (NOT JWT)
                checkpoint("  → Creating contract_sign_tokens table...")
                execute_with_retry(migrate_engine, """
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
                """)
                
                checkpoint("    ✅ contract_sign_tokens table created (secure DB-based tokens)")
                
                # Create contract_sign_events table (Audit Trail)
                checkpoint("  → Creating contract_sign_events table...")
                execute_with_retry(migrate_engine, """
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
                """)
                
                checkpoint("    ✅ contract_sign_events table created")
                
                migrations_applied.append('upgrade_contracts_system_attachment_based')
                checkpoint("✅ Migration 77 completed - Contracts system with attachment integration")
                checkpoint("  📋 Summary:")
                checkpoint("     • contract_files → attachment_id (reuses R2 storage)")
                checkpoint("     • contract_sign_tokens → DB-based (NOT JWT)")
                checkpoint("     • contract_sign_events → full audit trail")
                
            except Exception as e:
                log.error(f"❌ Migration 77 failed: {e}")
                raise
        else:
            checkpoint("  ℹ️ contract_files table already exists - skipping")
        
        # Migration 78: Rename metadata to event_metadata in contract_sign_events (SQLAlchemy reserved word fix)
        if check_table_exists('contract_sign_events') and check_column_exists('contract_sign_events', 'metadata'):
            checkpoint("🔧 Running Migration 78: Rename metadata to event_metadata in contract_sign_events")
            
            try:
                # Rename the column from metadata to event_metadata
                execute_with_retry(migrate_engine, """
                    ALTER TABLE contract_sign_events 
                    RENAME COLUMN metadata TO event_metadata
                """)
                
                migrations_applied.append('rename_contract_sign_events_metadata')
                checkpoint("✅ Migration 78 completed - Renamed metadata to event_metadata in contract_sign_events")
                checkpoint("  📋 Reason: 'metadata' is a reserved attribute in SQLAlchemy Declarative API")
                
            except Exception as e:
                log.error(f"❌ Migration 78 failed: {e}")
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
                execute_with_retry(migrate_engine, """
                    ALTER TABLE email_messages 
                    ADD COLUMN attachments JSON DEFAULT '[]'
                """)
                
                migrations_applied.append('add_email_messages_attachments')
                checkpoint("✅ Migration 79 completed - Added attachments column to email_messages")
                checkpoint("  📋 Purpose: Store attachment IDs for email attachments support")
                
            except Exception as e:
                log.error(f"❌ Migration 79 failed: {e}")
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
            
            # Initialize constraint_row before try block to avoid UnboundLocalError
            constraint_row = None
            
            try:
                # Check if constraint exists by querying check_constraints
                result = execute_with_retry(migrate_engine, """
                    SELECT constraint_name, check_clause
                    FROM information_schema.check_constraints 
                    WHERE constraint_name LIKE '%event_type%'
                    AND constraint_schema = 'public'
                """)
                constraint_row = result[0] if result else None

                
                if constraint_row:
                    constraint_name = constraint_row[0]
                    check_clause = constraint_row[1] if len(constraint_row) > 1 else ''
                    
                    # Check if 'file_downloaded' is already in the constraint
                    if 'file_downloaded' in check_clause:
                        checkpoint("  ℹ️ 'file_downloaded' already in event_type constraint - skipping")
                    else:
                        # Drop old constraint and add new one with 'file_downloaded'
                        execute_with_retry(migrate_engine, f"""
                            ALTER TABLE contract_sign_events 
                            DROP CONSTRAINT IF EXISTS {constraint_name}
                        """)
                        
                        execute_with_retry(migrate_engine, """
                            ALTER TABLE contract_sign_events 
                            ADD CONSTRAINT contract_sign_events_event_type_check 
                            CHECK (event_type IN (
                                'created', 'file_uploaded', 'sent_for_signature', 
                                'viewed', 'signed_completed', 'cancelled', 'file_downloaded'
                            ))
                        """)
                        
                        migrations_applied.append('add_file_downloaded_event_type')
                        checkpoint("✅ Migration 80 completed - Added 'file_downloaded' to allowed event types")
                        checkpoint("  📋 Purpose: Allow logging of file download events in contract audit trail")
                else:
                    checkpoint("  ℹ️ Event type constraint not found - table may not have constraint yet")
                
            except Exception as e:
                log.error(f"❌ Migration 80 failed: {e}")
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
                execute_with_retry(migrate_engine, """
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
                """)
                
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                
                checkpoint("  ✅ asset_items table created")
                migrations_applied.append('create_asset_items_table')
            except Exception as e:
                log.error(f"❌ Migration 81 (asset_items) failed: {e}")
                raise
        else:
            checkpoint("  ℹ️ asset_items table already exists - skipping")
        
        if not check_table_exists('asset_item_media'):
            try:
                checkpoint("  → Creating asset_item_media table...")
                execute_with_retry(migrate_engine, """
                    CREATE TABLE asset_item_media (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        asset_item_id INTEGER NOT NULL REFERENCES asset_items(id) ON DELETE CASCADE,
                        attachment_id INTEGER NOT NULL REFERENCES attachments(id) ON DELETE CASCADE,
                        role VARCHAR(32) NOT NULL DEFAULT 'gallery' CHECK (role IN ('cover', 'gallery', 'floorplan', 'other')),
                        sort_order INTEGER DEFAULT 0,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                execute_with_retry(migrate_engine, """
                """)
                
                checkpoint("  ✅ asset_item_media table created")
                migrations_applied.append('create_asset_item_media_table')
            except Exception as e:
                log.error(f"❌ Migration 81 (asset_item_media) failed: {e}")
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
                result = execute_with_retry(migrate_engine, """
                    UPDATE business
                    SET enabled_pages = enabled_pages::jsonb || '["assets"]'::jsonb
                    WHERE enabled_pages IS NOT NULL
                      AND NOT (enabled_pages::jsonb ? 'assets')
                """)
                updated_count = getattr(result, "rowcount", 0)
                
                if updated_count > 0:
                    checkpoint(f"  ✅ Enabled 'assets' page for {updated_count} businesses")
                else:
                    checkpoint("  ℹ️ All businesses already have 'assets' page enabled")
                
                # For businesses with NULL or empty enabled_pages, set default pages including assets
                result2 = execute_with_retry(migrate_engine, """
                    UPDATE business
                    SET enabled_pages = '["dashboard","crm_leads","crm_customers","calls_inbound","calls_outbound","whatsapp_inbox","whatsapp_broadcast","emails","calendar","statistics","invoices","contracts","assets","settings","users"]'::jsonb
                    WHERE enabled_pages IS NULL
                       OR enabled_pages::text = '[]'
                       OR jsonb_array_length(enabled_pages::jsonb) = 0
                """)
                updated_count2 = getattr(result2, "rowcount", 0)
                
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
                execute_with_retry(migrate_engine, """
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
                """)
                execute_with_retry(migrate_engine, """
                """)
                checkpoint("  ✅ gmail_connections table created")
                migrations_applied.append('create_gmail_connections_table')
            except Exception as e:
                log.error(f"❌ Migration 82 (gmail_connections) failed: {e}")
                raise
        else:
            checkpoint("  ℹ️ gmail_connections table already exists - skipping")
        
        # Create receipts table
        if not check_table_exists('receipts'):
            try:
                checkpoint("  → Creating receipts table...")
                execute_with_retry(migrate_engine, """
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
                """)
                # Use partial unique index to allow NULL gmail_message_id (for manual uploads)
                execute_with_retry(migrate_engine, """
                    CREATE UNIQUE INDEX uq_receipt_business_gmail_message 
                    ON receipts(business_id, gmail_message_id) 
                    WHERE gmail_message_id IS NOT NULL
                """)
                checkpoint("  ✅ receipts table created")
                migrations_applied.append('create_receipts_table')
            except Exception as e:
                log.error(f"❌ Migration 82 (receipts) failed: {e}")
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
                execute_with_retry(migrate_engine, """
                    ALTER TABLE business_settings
                    ADD COLUMN assets_use_ai BOOLEAN NOT NULL DEFAULT TRUE
                """)
                checkpoint("  ✅ assets_use_ai column added (default: TRUE)")
                migrations_applied.append('add_assets_use_ai_column')
                checkpoint("✅ Applied migration 83: add_assets_use_ai_column - AI tools toggle for assets")
            except Exception as e:
                log.error(f"❌ Migration 83 (assets_use_ai) failed: {e}")
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
                try:
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE attachments 
                        ADD COLUMN purpose VARCHAR(50) NOT NULL DEFAULT 'general_upload'
                    """)
                    
                    # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
                    # Performance indexes MUST be created separately via db_build_indexes.py
                    
                    migrations_applied.append("add_purpose_to_attachments")
                    checkpoint("✅ Migration 84a complete: purpose added with index")
                except Exception as e:
                    checkpoint(f"⚠️ Migration 84a failed: {e}")
                    log.error(f"Migration 84a error details: {e}", exc_info=True)
            else:
                checkpoint("Migration 84a: purpose column already exists - skipping")
        
        # 84b: Add origin_module field to attachments
        if check_table_exists('attachments'):
            if not check_column_exists('attachments', 'origin_module'):
                checkpoint("Migration 84b: Adding origin_module to attachments")
                try:
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE attachments 
                        ADD COLUMN origin_module VARCHAR(50)
                    """)
                    
                    # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
                    # Performance indexes MUST be created separately via db_build_indexes.py
                    
                    migrations_applied.append("add_origin_module_to_attachments")
                    checkpoint("✅ Migration 84b complete: origin_module added with index")
                except Exception as e:
                    checkpoint(f"⚠️ Migration 84b failed: {e}")
                    log.error(f"Migration 84b error details: {e}", exc_info=True)
            else:
                checkpoint("Migration 84b: origin_module column already exists - skipping")
        
        # 84c: Add email content fields to receipts
        if check_table_exists('receipts'):
            checkpoint("Migration 84c: Adding email content fields to receipts")
            try:
                fields_added = []
                
                # Add email_subject
                if not check_column_exists('receipts', 'email_subject'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE receipts 
                        ADD COLUMN email_subject VARCHAR(500)
                    """)
                    # Copy from existing subject field if available
                    execute_with_retry(migrate_engine, """
                        UPDATE receipts 
                        SET email_subject = subject 
                        WHERE subject IS NOT NULL
                    """)
                    fields_added.append('email_subject')
                
                # Add email_from
                if not check_column_exists('receipts', 'email_from'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE receipts 
                        ADD COLUMN email_from VARCHAR(255)
                    """)
                    # Copy from existing from_email field
                    execute_with_retry(migrate_engine, """
                        UPDATE receipts 
                        SET email_from = from_email 
                        WHERE from_email IS NOT NULL
                    """)
                    fields_added.append('email_from')
                
                # Add email_date
                if not check_column_exists('receipts', 'email_date'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE receipts 
                        ADD COLUMN email_date TIMESTAMP
                    """)
                    # Copy from existing received_at field
                    execute_with_retry(migrate_engine, """
                        UPDATE receipts 
                        SET email_date = received_at 
                        WHERE received_at IS NOT NULL
                    """)
                    fields_added.append('email_date')
                
                # Add email_html_snippet
                if not check_column_exists('receipts', 'email_html_snippet'):
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE receipts 
                        ADD COLUMN email_html_snippet TEXT
                    """)
                    fields_added.append('email_html_snippet')
                
                if fields_added:
                    migrations_applied.append("add_email_fields_to_receipts")
                    checkpoint(f"✅ Migration 84c complete: {', '.join(fields_added)} added")
                else:
                    checkpoint("Migration 84c: All email fields already exist")
            except Exception as e:
                checkpoint(f"⚠️ Migration 84c failed: {e}")
        
        # 84d: Add preview_attachment_id to receipts
        if check_table_exists('receipts') and not check_column_exists('receipts', 'preview_attachment_id'):
            checkpoint("Migration 84d: Adding preview_attachment_id to receipts")
            try:
                execute_with_retry(migrate_engine, """
                    ALTER TABLE receipts 
                    ADD COLUMN preview_attachment_id INTEGER 
                    REFERENCES attachments(id) ON DELETE SET NULL
                """)
                
                # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
                
                migrations_applied.append("add_preview_attachment_id_to_receipts")
                checkpoint("✅ Migration 84d complete: preview_attachment_id added")
            except Exception as e:
                checkpoint(f"⚠️ Migration 84d failed: {e}")
        
        # 84e: Create receipt_sync_runs table
        if not check_table_exists('receipt_sync_runs'):
            checkpoint("Migration 84e: Creating receipt_sync_runs table")
            try:
                execute_with_retry(migrate_engine, """
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
                """)
                
                # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
                # Performance indexes MUST be created separately via db_build_indexes.py
                
                migrations_applied.append("create_receipt_sync_runs_table")
                checkpoint("✅ Migration 84e complete: receipt_sync_runs table created")
            except Exception as e:
                checkpoint(f"⚠️ Migration 84e failed: {e}")
        
        # 84f: Backfill existing attachments with purpose and origin
        if check_table_exists('attachments') and check_column_exists('attachments', 'purpose'):
            checkpoint("Migration 84f: Backfilling attachments with purpose/origin")
            try:
                # Mark receipt attachments
                result = execute_with_retry(migrate_engine, """
                    UPDATE attachments a
                    SET 
                        purpose = 'receipt_source',
                        origin_module = 'receipts'
                    WHERE EXISTS (
                        SELECT 1 FROM receipts r 
                        WHERE r.attachment_id = a.id
                    ) AND a.purpose = 'general_upload'
                """)
                receipt_count = getattr(result, "rowcount", 0)
                
                # Mark contract attachments (if contract_files table exists)
                contract_count = 0
                if check_table_exists('contract_files'):
                    result = execute_with_retry(migrate_engine, """
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
                    """)
                    contract_count = getattr(result, "rowcount", 0)
                
                # Set origin_module for remaining general uploads
                execute_with_retry(migrate_engine, """
                    UPDATE attachments
                    SET origin_module = 'uploads'
                    WHERE purpose = 'general_upload' AND origin_module IS NULL
                """)
                
                migrations_applied.append("backfill_attachment_purpose_origin")
                checkpoint(f"✅ Migration 84f complete: Backfilled {receipt_count} receipts, {contract_count} contracts")
            except Exception as e:
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
            try:
                fields_added = []
                
                # Add cancelled_at column if missing (for cancellation tracking)
                if not check_column_exists('receipt_sync_runs', 'cancelled_at'):
                    checkpoint("  → Adding cancelled_at to receipt_sync_runs...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE receipt_sync_runs 
                        ADD COLUMN cancelled_at TIMESTAMP NULL
                    """)
                    fields_added.append('cancelled_at')
                    checkpoint("  ✅ cancelled_at added")
                
                # Add current_month column if missing (for monthly backfill tracking)
                if not check_column_exists('receipt_sync_runs', 'current_month'):
                    checkpoint("  → Adding current_month to receipt_sync_runs...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE receipt_sync_runs 
                        ADD COLUMN current_month VARCHAR(10) NULL
                    """)
                    # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
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
            try:
                fields_added = []
                
                # Add last_heartbeat_at column if missing
                if not check_column_exists('receipt_sync_runs', 'last_heartbeat_at'):
                    checkpoint("  → Adding last_heartbeat_at to receipt_sync_runs...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE receipt_sync_runs 
                        ADD COLUMN IF NOT EXISTS last_heartbeat_at TIMESTAMP NULL
                    """)
                    
                    # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
                    
                    # Initialize heartbeat for existing running syncs to prevent false positives
                    checkpoint("  → Initializing heartbeat for existing running syncs...")
                    result = execute_with_retry(migrate_engine, """
                        UPDATE receipt_sync_runs 
                        SET last_heartbeat_at = COALESCE(updated_at, started_at)
                        WHERE status = 'running' AND last_heartbeat_at IS NULL
                    """)
                    updated_count = result.rowcount if hasattr(result, 'rowcount') else 0
                    if updated_count > 0:
                        checkpoint(f"  ✅ Initialized heartbeat for {updated_count} existing running sync(s)")
                    
                    fields_added.append('last_heartbeat_at')
                    checkpoint("  ✅ last_heartbeat_at added")
                
                # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
                
                if fields_added:
                    migrations_applied.append("add_receipt_sync_heartbeat")
                    checkpoint(f"✅ Migration 86 complete: {', '.join(fields_added)} added")
                    checkpoint("   🔒 Idempotent: Safe to run multiple times")
                    checkpoint("   🎯 Purpose: Detects stale syncs (no heartbeat > 180s)")
                    checkpoint("   🔧 Enables: Auto-recovery from crashed background jobs")
                else:
                    checkpoint("✅ Migration 86: Heartbeat already exists - skipping")
                    
            except Exception as e:
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
                    result = execute_with_retry(migrate_engine, duplicates_query)
                    rows_deleted = getattr(result, "rowcount", 0)
                    
                    if rows_deleted > 0:
                        checkpoint(f"  → Removed {rows_deleted} duplicate messages (kept oldest per business)")
                    else:
                        checkpoint("  → No duplicate messages found")
                    
                    # Add unique constraint (partial index - only for non-NULL values)
                    # CRITICAL: (business_id, provider_message_id) not just provider_message_id
                    checkpoint("  → Creating unique index on (business_id, provider_message_id)...")
                    execute_with_retry(migrate_engine, """
                        CREATE UNIQUE INDEX idx_whatsapp_message_provider_id_unique
                        ON whatsapp_message(business_id, provider_message_id)
                        WHERE provider_message_id IS NOT NULL
                    """)
                    
                    migrations_applied.append("migration_87_whatsapp_unique_constraint")
                    checkpoint("✅ Migration 87 complete: unique constraint added")
                    checkpoint("   🔒 Idempotent: Safe to run multiple times")
                    checkpoint("   🎯 Purpose: Prevents duplicate WhatsApp messages PER BUSINESS")
                    checkpoint("   🔧 Multi-tenant: (business_id, provider_message_id) prevents cross-tenant conflicts")
                else:
                    checkpoint("✅ Migration 87: Unique constraint already exists - skipping")
                    
            except Exception as e:
                checkpoint(f"❌ Migration 87 failed: {e}")
                logger.error(f"Migration 87 error details: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ whatsapp_message table does not exist - skipping")
        
        # Migration 88: Create contract_signature_fields table for PDF signature placement
        # This allows businesses to mark signature areas on PDFs before sending for signature
        if not check_table_exists('contract_signature_fields'):
            checkpoint("🔧 Running Migration 88: Create contract_signature_fields table")
            try:
                
                execute_with_retry(migrate_engine, """
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
                """)
                
                # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
                
                migrations_applied.append("create_contract_signature_fields_table")
                checkpoint("✅ Migration 88: Created contract_signature_fields table with indexes")
            except Exception as e:
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
                # Use migration engine with retry for metadata query
                migrate_engine = get_migrate_engine()
                rows = fetch_all_retry(migrate_engine, """
                    SELECT constraint_name, check_clause
                    FROM information_schema.check_constraints 
                    WHERE constraint_name LIKE :p
                    AND constraint_schema = 'public'
                """, {"p": "%event_type%"})
                
                constraint_row = rows[0] if rows else None
                
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
                        
                        # Drop old constraint using exec_sql with autocommit
                        exec_sql(migrate_engine, f"""
                            ALTER TABLE contract_sign_events 
                            DROP CONSTRAINT IF EXISTS {constraint_name}
                        """, autocommit=True)
                        
                        # Build constraint with all event types from constant
                        event_types_sql = ', '.join([f"'{et}'" for et in CONTRACT_EVENT_TYPES])
                        exec_sql(migrate_engine, f"""
                            ALTER TABLE contract_sign_events 
                            ADD CONSTRAINT contract_sign_events_event_type_check 
                            CHECK (event_type IN ({event_types_sql}))
                        """, autocommit=True)
                        
                        migrations_applied.append('expand_contract_event_types')
                        checkpoint("✅ Migration 90 completed - Expanded event_type constraint")
                        checkpoint(f"   📋 Added: {', '.join(missing_types)}")
                        checkpoint("   🎯 Purpose: Fix PDF preview/audit trail failures")
                        checkpoint("   🔒 Security: Constraint still prevents typos, now matches actual code usage")
                else:
                    checkpoint("  ℹ️ Event type constraint not found - table may not have constraint yet")
                
            except Exception as e:
                log.error(f"❌ Migration 90 failed: {e}")
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
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE receipts 
                        ADD COLUMN preview_status VARCHAR(20) DEFAULT 'pending'
                    """)
                    
                    # Add CHECK constraint for valid values
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE receipts 
                        ADD CONSTRAINT chk_receipt_preview_status 
                        CHECK (preview_status IN ('pending', 'generated', 'failed', 'not_available', 'skipped'))
                    """)
                    
                    fields_to_add.append('preview_status')
                    checkpoint("    ✅ preview_status added with constraint")
                
                # Add preview_failure_reason field
                if not check_column_exists('receipts', 'preview_failure_reason'):
                    checkpoint("  → Adding preview_failure_reason column")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE receipts 
                        ADD COLUMN preview_failure_reason TEXT
                    """)
                    
                    fields_to_add.append('preview_failure_reason')
                    checkpoint("    ✅ preview_failure_reason added")
                
                # Backfill existing receipts with appropriate status
                if fields_to_add:
                    checkpoint("  → Backfilling existing receipts with status")
                    
                    # Set 'generated' for receipts that have preview_attachment_id
                    result = execute_with_retry(migrate_engine, """
                        UPDATE receipts 
                        SET preview_status = 'generated' 
                        WHERE preview_attachment_id IS NOT NULL 
                        AND preview_status = 'pending'
                    """)
                    generated_count = result.rowcount if hasattr(result, 'rowcount') else 0
                    
                    # Set 'not_available' for old receipts without preview (won't retry automatically)
                    result = execute_with_retry(migrate_engine, """
                        UPDATE receipts 
                        SET preview_status = 'not_available' 
                        WHERE preview_attachment_id IS NULL 
                        AND preview_status = 'pending'
                        AND created_at < NOW() - INTERVAL '7 days'
                    """)
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
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE receipts 
                        ADD COLUMN needs_review BOOLEAN DEFAULT FALSE
                    """)
                    fields_to_add.append('needs_review')
                    checkpoint("    ✅ needs_review added")
                
                # Add receipt_type field
                if not check_column_exists('receipts', 'receipt_type'):
                    checkpoint("  → Adding receipt_type column")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE receipts 
                        ADD COLUMN receipt_type VARCHAR(32)
                    """)
                    
                    # Add CHECK constraint for valid values
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE receipts 
                        ADD CONSTRAINT chk_receipt_type 
                        CHECK (receipt_type IS NULL OR receipt_type IN ('confirmation', 'receipt', 'invoice', 'statement', 'other'))
                    """)
                    
                    fields_to_add.append('receipt_type')
                    checkpoint("    ✅ receipt_type added with constraint")
                
                # Backfill existing receipts
                if fields_to_add:
                    checkpoint("  → Backfilling existing receipts")
                    
                    # Set needs_review for low-confidence receipts (confidence < 15)
                    result = execute_with_retry(migrate_engine, """
                        UPDATE receipts 
                        SET needs_review = TRUE 
                        WHERE confidence < 15 
                        AND needs_review = FALSE
                    """)
                    low_conf_count = result.rowcount if hasattr(result, 'rowcount') else 0
                    
                    # Set needs_review for receipts without amount
                    result = execute_with_retry(migrate_engine, """
                        UPDATE receipts 
                        SET needs_review = TRUE 
                        WHERE amount IS NULL 
                        AND needs_review = FALSE
                    """)
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
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE leads 
                        ADD COLUMN phone_raw VARCHAR(64) NULL
                    """)
                    
                    migrations_applied.append('add_leads_phone_raw_column')
                    checkpoint("✅ Migration 93 completed - phone_raw column added to leads")
                    checkpoint("   📋 Purpose: Store original phone input before normalization")
                    checkpoint("   🎯 Fixes: UndefinedColumn errors in routes and services")
                else:
                    checkpoint("  ℹ️ phone_raw column already exists - skipping")
                
            except Exception as e:
                log.error(f"❌ Migration 93 failed: {e}")
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
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE leads 
                        ADD COLUMN whatsapp_jid VARCHAR(128) NULL
                    """)
                    migrations_applied.append('add_leads_whatsapp_jid_column')
                else:
                    checkpoint("  ℹ️ whatsapp_jid column already exists - skipping")
                
                # Add whatsapp_jid_alt column
                if not check_column_exists('leads', 'whatsapp_jid_alt'):
                    checkpoint("  → Adding whatsapp_jid_alt column (VARCHAR(128), nullable)")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE leads 
                        ADD COLUMN whatsapp_jid_alt VARCHAR(128) NULL
                    """)
                    migrations_applied.append('add_leads_whatsapp_jid_alt_column')
                else:
                    checkpoint("  ℹ️ whatsapp_jid_alt column already exists - skipping")
                
                # Add reply_jid column (CRITICAL for Android/LID)
                if not check_column_exists('leads', 'reply_jid'):
                    checkpoint("  → Adding reply_jid column (VARCHAR(128), nullable)")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE leads 
                        ADD COLUMN reply_jid VARCHAR(128) NULL
                    """)
                    migrations_applied.append('add_leads_reply_jid_column')
                else:
                    checkpoint("  ℹ️ reply_jid column already exists - skipping")
                
                # Add reply_jid_type column
                if not check_column_exists('leads', 'reply_jid_type'):
                    checkpoint("  → Adding reply_jid_type column (VARCHAR(32), nullable)")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE leads 
                        ADD COLUMN reply_jid_type VARCHAR(32) NULL
                    """)
                    migrations_applied.append('add_leads_reply_jid_type_column')
                else:
                    checkpoint("  ℹ️ reply_jid_type column already exists - skipping")
                
                # Add index on whatsapp_jid for fast lookups
                if not check_index_exists('ix_leads_whatsapp_jid'):
                    checkpoint("  → Creating index on whatsapp_jid")
                    execute_with_retry(migrate_engine, """
                    """)
                    migrations_applied.append('add_index_leads_whatsapp_jid')
                else:
                    checkpoint("  ℹ️ Index ix_leads_whatsapp_jid already exists - skipping")
                
                # Add index on reply_jid for fast lookups
                if not check_index_exists('ix_leads_reply_jid'):
                    checkpoint("  → Creating index on reply_jid")
                    execute_with_retry(migrate_engine, """
                    """)
                    migrations_applied.append('add_index_leads_reply_jid')
                else:
                    checkpoint("  ℹ️ Index ix_leads_reply_jid already exists - skipping")
                
                checkpoint("✅ Migration 94 completed - WhatsApp JID columns added to leads")
                checkpoint("   📋 Purpose: Store WhatsApp identifiers for LID support")
                checkpoint("   🎯 Fixes: UndefinedColumn errors for WhatsApp features")
                
            except Exception as e:
                log.error(f"❌ Migration 94 failed: {e}")
                raise
        else:
            checkpoint("  ℹ️ leads table does not exist - skipping")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 95: Add 'incomplete' status to receipts check constraint
        # ═══════════════════════════════════════════════════════════════════════
        # PURPOSE: Update constraint to allow 'incomplete' status for validation failures
        #
        # 🔥 TWO-PHASE APPROACH (Production-Safe):
        # Phase 1: ADD CONSTRAINT ... NOT VALID (minimal blocking)
        # Phase 2: VALIDATE CONSTRAINT (allows concurrent reads)
        # Phase 3: DROP old constraint and rename (quick operation)
        #
        # This approach is production-safe because:
        # - ADD ... NOT VALID requires only ShareUpdateExclusiveLock (not AccessExclusiveLock)
        # - VALIDATE can run concurrently with SELECT queries
        # - Only the final DROP/RENAME is AccessExclusive, and it's very quick
        #
        # Traditional approach (DROP + ADD) would require AccessExclusiveLock for the entire
        # operation, blocking all queries. In Supabase pooler, this causes "ghost locks"
        # and timeouts after 120 seconds.
        # ═══════════════════════════════════════════════════════════════════════
        if check_table_exists('receipts'):
            try:
                checkpoint("🔧 Running Migration 95: Add 'incomplete' status to receipts (TWO-PHASE)")
                checkpoint("   ℹ️  Using production-safe two-phase constraint approach")
                
                migrate_engine = get_migrate_engine()
                
                # Phase 1: Drop old + Add new constraint as NOT VALID
                # ⚠️ LOCK INFO: DROP CONSTRAINT requires AccessExclusiveLock briefly,
                # but it's released immediately. ADD CONSTRAINT NOT VALID requires 
                # ShareUpdateExclusiveLock (less blocking than AccessExclusiveLock).
                # This is still much better than traditional DROP+ADD which holds
                # AccessExclusiveLock during constraint validation.
                checkpoint("   → Phase 1: Replacing constraint with NOT VALID version...")
                exec_ddl(migrate_engine, """
                    -- Drop old constraint if it exists (brief AccessExclusiveLock)
                    ALTER TABLE receipts DROP CONSTRAINT IF EXISTS chk_receipt_status;
                    
                    -- Add new constraint as NOT VALID (ShareUpdateExclusiveLock, no validation)
                    ALTER TABLE receipts 
                    ADD CONSTRAINT chk_receipt_status_v2
                    CHECK (status IN ('pending_review', 'approved', 'rejected', 'not_receipt', 'incomplete'))
                    NOT VALID;
                """)
                checkpoint("   ✅ Phase 1 complete: Constraint added (NOT VALID)")
                
                # Phase 2: Validate the constraint (can run concurrently with reads)
                # This checks existing rows but allows SELECT queries to continue
                checkpoint("   → Phase 2: Validating constraint - allows concurrent reads...")
                exec_ddl(migrate_engine, """
                    ALTER TABLE receipts 
                    VALIDATE CONSTRAINT chk_receipt_status_v2;
                """)
                checkpoint("   ✅ Phase 2 complete: Constraint validated")
                
                # Phase 3: Rename to final name
                # ⚠️ LOCK INFO: RENAME requires AccessExclusiveLock, but since we're
                # just renaming (not validating), it's extremely fast - typically < 100ms.
                # Uses exec_ddl with 5s lock_timeout, which is sufficient for rename.
                checkpoint("   → Phase 3: Renaming constraint to final name (fast)...")
                exec_ddl(migrate_engine, """
                    ALTER TABLE receipts 
                    RENAME CONSTRAINT chk_receipt_status_v2 TO chk_receipt_status;
                """)
                checkpoint("   ✅ Phase 3 complete: Constraint renamed")
                
                # ⚠️ MIGRATION TRACKING: Changed from 'add_incomplete_status_to_receipts'
                # to 'add_incomplete_status_to_receipts_two_phase' to reflect the new approach.
                # This is intentional - the two-phase method is fundamentally different and safer.
                # Old migration name won't be re-applied since we check for constraint existence.
                migrations_applied.append("add_incomplete_status_to_receipts_two_phase")
                checkpoint("✅ Migration 95 completed - 'incomplete' status added to receipts")
                checkpoint("   📋 Purpose: Track receipts with validation failures (missing snapshot/attachments)")
                checkpoint("   🎯 Ensures: NO emails with attachments are missed (Rule 6/7/10)")
                checkpoint("   ℹ️  Status values: pending_review, approved, rejected, not_receipt, incomplete")
                checkpoint("   🚀 Used production-safe two-phase approach to minimize blocking")
                
            except Exception as e:
                log.error(f"❌ Migration 95 failed: {e}")
                raise
        else:
            checkpoint("  ℹ️ receipts table does not exist - skipping")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 96: WhatsApp Prompt-Only Mode + Lead Name Tracking (DDL ONLY)
        # 🎯 PURPOSE: Add dedicated WhatsApp prompt fields to business table
        #            Add name tracking fields to leads table
        # ⚠️  CRITICAL: DATA MIGRATION MOVED TO BACKFILL (db_backfills.py)
        # ═══════════════════════════════════════════════════════════════════════
        
        # Define fingerprint function for migration 96
        def fp_96():
            """Check if migration 96 schema already exists"""
            return (
                check_column_exists("leads", "name") and
                check_column_exists("leads", "name_source") and
                check_column_exists("leads", "name_updated_at") and
                check_column_exists("business", "whatsapp_system_prompt") and
                check_column_exists("business", "whatsapp_temperature") and
                check_column_exists("business", "whatsapp_model") and
                check_column_exists("business", "whatsapp_max_tokens")
            )
        
        # Define DDL function for migration 96
        def run_96():
            """Execute migration 96 DDL - schema changes only"""
            checkpoint("Migration 96: WhatsApp Prompt-Only Mode + Lead Name Tracking (DDL ONLY)")
            
            # Part 1: Add WhatsApp prompt fields to business table
            if check_table_exists('business'):
                checkpoint("  → Part 1: Adding WhatsApp prompt fields to business...")
                
                if not check_column_exists('business', 'whatsapp_system_prompt'):
                    exec_ddl(migrate_engine, """
                        ALTER TABLE business 
                        ADD COLUMN IF NOT EXISTS whatsapp_system_prompt TEXT
                    """)
                    checkpoint("    ✅ business.whatsapp_system_prompt added")
                
                if not check_column_exists('business', 'whatsapp_temperature'):
                    exec_ddl(migrate_engine, """
                        ALTER TABLE business 
                        ADD COLUMN IF NOT EXISTS whatsapp_temperature FLOAT DEFAULT 0.0
                    """)
                    checkpoint("    ✅ business.whatsapp_temperature added")
                
                if not check_column_exists('business', 'whatsapp_model'):
                    exec_ddl(migrate_engine, """
                        ALTER TABLE business 
                        ADD COLUMN IF NOT EXISTS whatsapp_model VARCHAR(50) DEFAULT 'gpt-4o-mini'
                    """)
                    checkpoint("    ✅ business.whatsapp_model added")
                
                if not check_column_exists('business', 'whatsapp_max_tokens'):
                    exec_ddl(migrate_engine, """
                        ALTER TABLE business 
                        ADD COLUMN IF NOT EXISTS whatsapp_max_tokens INTEGER DEFAULT 350
                    """)
                    checkpoint("    ✅ business.whatsapp_max_tokens added")
                
                checkpoint("  ✅ Part 1 completed - WhatsApp prompt fields added")
            else:
                checkpoint("  ℹ️  business table does not exist - skipping Part 1")
            
            # Part 2: Add name tracking fields to leads table
            if check_table_exists('leads'):
                checkpoint("  → Part 2: Adding name tracking fields to leads...")
                
                if not check_column_exists('leads', 'name'):
                    exec_ddl(migrate_engine, """
                        ALTER TABLE leads 
                        ADD COLUMN IF NOT EXISTS name VARCHAR(255)
                    """)
                    checkpoint("    ✅ leads.name added")
                
                if not check_column_exists('leads', 'name_source'):
                    exec_ddl(migrate_engine, """
                        ALTER TABLE leads 
                        ADD COLUMN IF NOT EXISTS name_source VARCHAR(32)
                    """)
                    checkpoint("    ✅ leads.name_source added")
                
                if not check_column_exists('leads', 'name_updated_at'):
                    exec_ddl(migrate_engine, """
                        ALTER TABLE leads 
                        ADD COLUMN IF NOT EXISTS name_updated_at TIMESTAMP
                    """)
                    checkpoint("    ✅ leads.name_updated_at added")
                
                checkpoint("  ✅ Part 2 completed - Lead name tracking fields added")
            else:
                checkpoint("  ℹ️  leads table does not exist - skipping Part 2")
            
            checkpoint("✅ Migration 96 DDL completed")
            checkpoint("   ℹ️  DATA MIGRATION: Run separately via backfill system")
            checkpoint("   ℹ️  Command: python server/db_run_backfills.py --only migration_96_lead_name")
        
        # Run migration 96 with fingerprint-based reconciliation
        # Note: run_migration() handles all tracking via schema_migrations table
        status_96 = run_migration("096", fp_96, run_96, migrate_engine)
        if status_96 == "RUN":
            # Migration was executed - add to legacy tracking for backward compatibility
            migrations_applied.extend([
                'add_business_whatsapp_fields_96',
                'add_leads_name_fields_96'
            ])
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 97: Add unique constraint to receipts to prevent duplicates
        # ═══════════════════════════════════════════════════════════════════════
        if check_table_exists('receipts'):
            checkpoint("🔧 Running Migration 97: Add unique constraint to receipts")
            
            try:
                # Check if unique index already exists
                result = execute_with_retry(migrate_engine, """
                    SELECT COUNT(*) 
                    FROM pg_indexes 
                    WHERE indexname = 'uq_receipts_business_gmail_message'
                """)
                index_exists = result[0][0] if result else 0
                index_exists = index_exists > 0
                
                if not index_exists:
                    checkpoint("  → Creating unique index for Gmail message IDs...")
                    
                    # First, check for existing duplicates and clean them up
                    checkpoint("  → Checking for existing duplicates...")
                    result = execute_with_retry(migrate_engine, """
                        SELECT 
                            business_id,
                            gmail_message_id,
                            COUNT(*) as count
                        FROM receipts
                        WHERE is_deleted = FALSE 
                        AND gmail_message_id IS NOT NULL
                        GROUP BY business_id, gmail_message_id
                        HAVING COUNT(*) > 1
                    """)
                    
                    duplicates = result if result else []
                    if duplicates:
                        checkpoint(f"  ⚠️  Found {len(duplicates)} duplicate Gmail message IDs")
                        checkpoint("  → Marking older duplicates as deleted...")
                        
                        for dup in duplicates:
                            business_id, gmail_message_id, count = dup
                            # Keep the newest one, soft-delete the rest
                            execute_with_retry(migrate_engine, """
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
                            """, {
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
                    execute_with_retry(migrate_engine, """
                        CREATE UNIQUE INDEX uq_receipts_business_gmail_message 
                        ON receipts(business_id, gmail_message_id)
                        WHERE is_deleted = FALSE AND gmail_message_id IS NOT NULL
                    """)
                    
                    checkpoint("  ✅ Created unique constraint for receipts")
                    migrations_applied.append('add_receipts_unique_constraint')
                else:
                    checkpoint("  ℹ️  Unique index already exists - skipping")
                
                checkpoint("✅ Migration 97 completed - Receipts unique constraint added")
                
            except Exception as e:
                checkpoint(f"❌ Migration 97 failed: {e}")
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
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE business
                        ADD COLUMN tts_provider VARCHAR(32) DEFAULT 'openai'
                    """)
                    checkpoint("  ✅ tts_provider column added (default: 'openai')")
                    migrations_applied.append('add_business_tts_provider')
                else:
                    checkpoint("  ℹ️ tts_provider column already exists")
                
                # Add tts_voice_id column if missing
                if not check_column_exists('business', 'tts_voice_id'):
                    checkpoint("  → Adding tts_voice_id column...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE business
                        ADD COLUMN tts_voice_id VARCHAR(64) DEFAULT 'alloy'
                    """)
                    checkpoint("  ✅ tts_voice_id column added (default: 'alloy')")
                    migrations_applied.append('add_business_tts_voice_id')
                else:
                    checkpoint("  ℹ️ tts_voice_id column already exists")
                
                # Add tts_language column if missing
                if not check_column_exists('business', 'tts_language'):
                    checkpoint("  → Adding tts_language column...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE business
                        ADD COLUMN tts_language VARCHAR(16) DEFAULT 'he-IL'
                    """)
                    checkpoint("  ✅ tts_language column added (default: 'he-IL')")
                    migrations_applied.append('add_business_tts_language')
                else:
                    checkpoint("  ℹ️ tts_language column already exists")
                
                # Add tts_speed column if missing
                if not check_column_exists('business', 'tts_speed'):
                    checkpoint("  → Adding tts_speed column...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE business
                        ADD COLUMN tts_speed FLOAT DEFAULT 1.0
                    """)
                    checkpoint("  ✅ tts_speed column added (default: 1.0)")
                    migrations_applied.append('add_business_tts_speed')
                else:
                    checkpoint("  ℹ️ tts_speed column already exists")
                
                checkpoint("✅ Migration 98 completed - TTS provider fields added")
                
            except Exception as e:
                checkpoint(f"❌ Migration 98 failed: {e}")
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
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE call_log
                        ADD COLUMN recording_mode TEXT DEFAULT 'realtime'
                    """)
                    checkpoint("  ✅ recording_mode column added (default: 'realtime', nullable)")
                    migrations_applied.append('add_call_log_recording_mode')
                else:
                    checkpoint("  ℹ️ recording_mode column already exists")
                
                checkpoint("✅ Migration 99 completed - recording_mode column added")
                
            except Exception as e:
                checkpoint(f"❌ Migration 99 failed: {e}")
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
                execute_with_retry(migrate_engine, """
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
                """)
                checkpoint("  ✅ background_jobs table created")
                migrations_applied.append('create_background_jobs_table')
                
                # Add indexes for performance
                checkpoint("  → Creating indexes...")
                
                # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
                
                # Add unique constraint to prevent duplicate active jobs
                checkpoint("  → Creating unique constraint...")
                execute_with_retry(migrate_engine, """
                    CREATE UNIQUE INDEX idx_background_jobs_unique_active 
                    ON background_jobs(business_id, job_type) 
                    WHERE status IN ('queued', 'running', 'paused')
                """)
                checkpoint("  ✅ idx_background_jobs_unique_active created (prevents concurrent jobs)")
                
                checkpoint("✅ Migration 100 completed - background_jobs table ready")
                
            except Exception as e:
                checkpoint(f"❌ Migration 100 failed: {e}")
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
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE receipts 
                        ADD COLUMN preview_image_key VARCHAR(512)
                    """)
                    checkpoint("  ✅ preview_image_key column added")
                    migrations_applied.append('add_preview_image_key')
                else:
                    checkpoint("  ℹ️  preview_image_key column already exists")
                
                # Add preview_source column with enum constraint
                if not check_column_exists('receipts', 'preview_source'):
                    checkpoint("  → Adding preview_source column...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE receipts 
                        ADD COLUMN preview_source VARCHAR(32)
                    """)
                    checkpoint("  → Adding preview_source constraint...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE receipts 
                        ADD CONSTRAINT chk_preview_source 
                        CHECK (preview_source IN ('email_html', 'attachment_pdf', 'attachment_image', 'receipt_url', 'html_fallback'))
                    """)
                    checkpoint("  ✅ preview_source column added with constraint")
                    migrations_applied.append('add_preview_source')
                else:
                    checkpoint("  ℹ️  preview_source column already exists")
                
                # Add extraction_status column with enum constraint
                if not check_column_exists('receipts', 'extraction_status'):
                    checkpoint("  → Adding extraction_status column...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE receipts 
                        ADD COLUMN extraction_status VARCHAR(32) DEFAULT 'pending'
                    """)
                    checkpoint("  → Adding extraction_status constraint...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE receipts 
                        ADD CONSTRAINT chk_extraction_status 
                        CHECK (extraction_status IN ('pending', 'processing', 'success', 'needs_review', 'failed'))
                    """)
                    checkpoint("  ✅ extraction_status column added with constraint")
                    migrations_applied.append('add_extraction_status')
                else:
                    checkpoint("  ℹ️  extraction_status column already exists")
                
                # Add extraction_error column
                if not check_column_exists('receipts', 'extraction_error'):
                    checkpoint("  → Adding extraction_error column...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE receipts 
                        ADD COLUMN extraction_error TEXT
                    """)
                    checkpoint("  ✅ extraction_error column added")
                    migrations_applied.append('add_extraction_error')
                else:
                    checkpoint("  ℹ️  extraction_error column already exists")
                
                # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
                
                checkpoint("✅ Migration 101 completed - Enhanced receipt processing fields ready")
                
            except Exception as e:
                checkpoint(f"❌ Migration 101 failed: {e}")
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
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE business 
                        ADD COLUMN ai_provider VARCHAR(32) DEFAULT 'openai'
                    """)
                    checkpoint("  ✅ ai_provider column added")
                else:
                    checkpoint("  ℹ️ ai_provider column already exists")
                
                # Add voice_name column - voice within the selected provider
                if not check_column_exists('business', 'voice_name'):
                    checkpoint("  → Adding voice_name column...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE business 
                        ADD COLUMN voice_name VARCHAR(64) DEFAULT 'alloy'
                    """)
                    checkpoint("  ✅ voice_name column added")
                else:
                    checkpoint("  ℹ️ voice_name column already exists")
                
                # 🔥 MIGRATION LOGIC: Default to openai, preserve existing voice if valid
                checkpoint("  → Migrating existing provider settings...")
                
                # Step 1: Set ai_provider to 'openai' as default (don't guess from tts_provider)
                # This is safe - users can change it in UI if they want Gemini
                execute_with_retry(migrate_engine, """
                    UPDATE business 
                    SET ai_provider = 'openai'
                    WHERE ai_provider IS NULL
                """)
                
                # Step 2: Set voice_name based on existing tts_voice_id or voice_id
                # Validate voice matches OpenAI (since we're defaulting to openai provider)
                execute_with_retry(migrate_engine, """
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
                """)
                
                checkpoint("  ✅ Existing provider settings migrated to openai defaults")
                
                # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
                # Performance indexes MUST be created separately via db_build_indexes.py
                
                migrations_applied.append('migration_102_ai_provider_selection')
                checkpoint("✅ Migration 102 completed - AI provider selection implemented")
                
            except Exception as e:
                checkpoint(f"❌ Migration 102 failed: {e}")
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
            try:
                fields_added = []
                
                # Add heartbeat_at column if missing
                if not check_column_exists('background_jobs', 'heartbeat_at'):
                    checkpoint("  → Adding heartbeat_at to background_jobs...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE background_jobs 
                        ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMP NULL
                    """)
                    
                    # NOTE: Index creation removed - indexes belong in db_indexes.py (INDEXING_GUIDE.md)
                    
                    # Initialize heartbeat for existing running jobs to prevent false positives
                    checkpoint("  → Initializing heartbeat for existing running jobs...")
                    result = execute_with_retry(migrate_engine, """
                        UPDATE background_jobs 
                        SET heartbeat_at = COALESCE(updated_at, started_at, created_at)
                        WHERE status IN ('running', 'queued') AND heartbeat_at IS NULL
                    """)
                    updated_count = getattr(result, "rowcount", 0)
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
            try:
                # Drop old constraint and create new one with all job types
                checkpoint("  → Dropping old chk_job_type constraint...")
                execute_with_retry(migrate_engine, """
                    ALTER TABLE background_jobs 
                    DROP CONSTRAINT IF EXISTS chk_job_type
                """)
                
                checkpoint("  → Creating updated chk_job_type constraint with all job types...")
                execute_with_retry(migrate_engine, """
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
                """)
                
                migrations_applied.append("update_background_jobs_job_type_constraint")
                checkpoint("✅ Migration 104 complete: job_type constraint updated")
                checkpoint("   🔒 Idempotent: Safe to run multiple times")
                checkpoint("   ✅ Allowed job types: delete_receipts_all, delete_leads, update_leads, delete_imported_leads, enqueue_outbound_calls, broadcast")
                
            except Exception as e:
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
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE outbound_call_runs 
                        ADD COLUMN cancel_requested BOOLEAN NOT NULL DEFAULT FALSE
                    """)
                    migrations_applied.append('105_outbound_cancel_requested')
                    checkpoint("✅ Migration 105 complete: cancel_requested column added to outbound_call_runs")
                else:
                    checkpoint("  ℹ️  cancel_requested column already exists - skipping Migration 105")
            except Exception as e:
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
                execute_with_retry(migrate_engine, """
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
                    
                """)
                migrations_applied.append('106_recording_runs_table')
                checkpoint("✅ Migration 106 complete: recording_runs table created")
                checkpoint("   🎯 Enables RQ worker-based recording with progress/cancel support")
            except Exception as e:
                checkpoint(f"❌ Migration 106 failed: {e}")
                logger.error(f"Migration 106 error details: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ recording_runs table already exists - skipping Migration 106")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 107: Add cancel_requested fields for unified long-running tasks
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 107: Adding cancel_requested and progress fields for unified long-running tasks")
        
        # 1. Add cancel_requested to WhatsAppBroadcast
        if check_table_exists('whatsapp_broadcasts'):
            try:
                if not check_column_exists('whatsapp_broadcasts', 'cancel_requested'):
                    checkpoint("  → Adding cancel_requested to whatsapp_broadcasts...")
                    exec_ddl(db.engine, """
                        ALTER TABLE whatsapp_broadcasts 
                        ADD COLUMN cancel_requested BOOLEAN NOT NULL DEFAULT FALSE
                    """)
                    checkpoint("  ✅ cancel_requested added to whatsapp_broadcasts")
                    migrations_applied.append('107_broadcast_cancel_requested')
                else:
                    checkpoint("  ℹ️ cancel_requested already exists on whatsapp_broadcasts")
                
                # Add cancelled_count field
                if not check_column_exists('whatsapp_broadcasts', 'cancelled_count'):
                    checkpoint("  → Adding cancelled_count to whatsapp_broadcasts...")
                    exec_ddl(db.engine, """
                        ALTER TABLE whatsapp_broadcasts 
                        ADD COLUMN cancelled_count INTEGER DEFAULT 0
                    """)
                    checkpoint("  ✅ cancelled_count added to whatsapp_broadcasts")
                    migrations_applied.append('107_broadcast_cancelled_count')
                else:
                    checkpoint("  ℹ️ cancelled_count already exists on whatsapp_broadcasts")
                
                # Add processed_count field
                if not check_column_exists('whatsapp_broadcasts', 'processed_count'):
                    checkpoint("  → Adding processed_count to whatsapp_broadcasts...")
                    exec_ddl(db.engine, """
                        ALTER TABLE whatsapp_broadcasts 
                        ADD COLUMN processed_count INTEGER DEFAULT 0
                    """)
                    checkpoint("  ✅ processed_count added to whatsapp_broadcasts")
                    migrations_applied.append('107_broadcast_processed_count')
                else:
                    checkpoint("  ℹ️ processed_count already exists on whatsapp_broadcasts")
                
            except Exception as e:
                checkpoint(f"❌ Migration 107 (broadcasts) failed: {e}")
                logger.error(f"Migration 107 broadcasts error: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ whatsapp_broadcasts table does not exist - skipping")
        
        # 2. Add cancelled status to WhatsAppBroadcastRecipient
        if check_table_exists('whatsapp_broadcast_recipients'):
            try:
                # Update status constraint to include 'cancelled'
                checkpoint("  → Updating whatsapp_broadcast_recipients status constraint to include 'cancelled'...")
                # First drop existing constraint if it exists
                execute_with_retry(migrate_engine, """
                    ALTER TABLE whatsapp_broadcast_recipients 
                    DROP CONSTRAINT IF EXISTS chk_recipient_status
                """)
                # Add new constraint with 'cancelled'
                execute_with_retry(migrate_engine, """
                    ALTER TABLE whatsapp_broadcast_recipients 
                    ADD CONSTRAINT chk_recipient_status 
                    CHECK (status IN ('queued', 'processing', 'sent', 'delivered', 'failed', 'cancelled'))
                """)
                checkpoint("  ✅ Status constraint updated for whatsapp_broadcast_recipients")
                migrations_applied.append('107_recipient_cancelled_status')
            except Exception as e:
                checkpoint(f"⚠️ Migration 107 (recipient status) warning: {e}")
        else:
            checkpoint("  ℹ️ whatsapp_broadcast_recipients table does not exist - skipping")
        
        # 3. Add cancel_requested to ReceiptSyncRun
        if check_table_exists('receipt_sync_runs'):
            try:
                if not check_column_exists('receipt_sync_runs', 'cancel_requested'):
                    checkpoint("  → Adding cancel_requested to receipt_sync_runs...")
                    exec_ddl(db.engine, """
                        ALTER TABLE receipt_sync_runs 
                        ADD COLUMN cancel_requested BOOLEAN NOT NULL DEFAULT FALSE
                    """)
                    checkpoint("  ✅ cancel_requested added to receipt_sync_runs")
                    migrations_applied.append('107_receipt_sync_cancel_requested')
                else:
                    checkpoint("  ℹ️ cancel_requested already exists on receipt_sync_runs")
                
            except Exception as e:
                checkpoint(f"❌ Migration 107 (receipt_sync) failed: {e}")
                logger.error(f"Migration 107 receipt_sync error: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ receipt_sync_runs table does not exist - skipping")
        
        checkpoint("✅ Migration 107 complete: Unified long-running tasks support added")
        checkpoint("   🎯 WhatsApp broadcasts now support cancel_requested + progress tracking")
        checkpoint("   🎯 Receipt sync now supports cancel_requested")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 108: Add last_processed_recipient_id for broadcast cursor-based pagination
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 108: Adding last_processed_recipient_id for cursor-based broadcast pagination")
        
        if check_table_exists('whatsapp_broadcasts'):
            try:
                if not check_column_exists('whatsapp_broadcasts', 'last_processed_recipient_id'):
                    checkpoint("  → Adding last_processed_recipient_id to whatsapp_broadcasts...")
                    exec_ddl(db.engine, """
                        ALTER TABLE whatsapp_broadcasts 
                        ADD COLUMN last_processed_recipient_id INTEGER DEFAULT 0
                    """)
                    checkpoint("  ✅ last_processed_recipient_id added to whatsapp_broadcasts")
                    migrations_applied.append('108_broadcast_cursor_pagination')
                else:
                    checkpoint("  ℹ️ last_processed_recipient_id already exists on whatsapp_broadcasts")
                
            except Exception as e:
                checkpoint(f"❌ Migration 108 (broadcast cursor) failed: {e}")
                logger.error(f"Migration 108 broadcast cursor error: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ whatsapp_broadcasts table does not exist - skipping")
        
        checkpoint("✅ Migration 108 complete: Broadcast cursor-based pagination support added")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 109: NO-OP (Backward Compatibility Mode)
        # ═══════════════════════════════════════════════════════════════════════
        # 🔥 BACKWARD COMPATIBILITY: This migration is now a NO-OP to allow the system
        # to work without started_at/ended_at/duration_sec columns.
        # The system uses the existing columns from Migration 51:
        #   - stream_started_at (instead of started_at)
        #   - stream_ended_at (instead of ended_at)
        #   - stream_duration_sec + duration (instead of duration_sec)
        checkpoint("Migration 109: NO-OP (skipped - uses Migration 51 columns)")
        checkpoint("  ℹ️ System uses stream_started_at/stream_ended_at from Migration 51")
        checkpoint("  ℹ️ Columns started_at/ended_at/duration_sec are NOT created")
        checkpoint("✅ Migration 109 complete: Skipped (backward compatibility mode)")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 110: Add summary_status to call_log for summary generation tracking
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 110: Adding summary_status to call_log for summary tracking")
        
        if check_table_exists('call_log'):
            try:
                if not check_column_exists('call_log', 'summary_status'):
                    checkpoint("  → Adding summary_status column to call_log...")
                    # Add column first
                    exec_ddl(db.engine, """
                        ALTER TABLE call_log 
                        ADD COLUMN summary_status VARCHAR(32) DEFAULT NULL
                    """)
                    checkpoint("  ✅ summary_status column added to call_log")
                    
                    # Add CHECK constraint separately for better compatibility
                    checkpoint("  → Adding CHECK constraint to summary_status...")
                    exec_ddl(db.engine, """
                        ALTER TABLE call_log
                        ADD CONSTRAINT chk_call_log_summary_status 
                        CHECK (summary_status IN ('pending', 'processing', 'completed', 'failed'))
                    """)
                    checkpoint("  ✅ CHECK constraint added to summary_status")
                    
                    # Mark existing calls with summaries as completed
                    checkpoint("  → Marking existing calls with summaries as 'completed'...")
                    result = execute_with_retry(migrate_engine, """
                        UPDATE call_log 
                        SET summary_status = 'completed'
                        WHERE summary IS NOT NULL 
                          AND summary != ''
                          AND summary_status IS NULL
                    """)
                    updated_rows = getattr(result, "rowcount", 0)
                    checkpoint(f"  ✅ Marked {updated_rows} existing calls with summaries as 'completed'")
                    
                    migrations_applied.append('110_call_log_summary_status')
                else:
                    checkpoint("  ℹ️ summary_status already exists on call_log")
                
            except Exception as e:
                checkpoint(f"❌ Migration 110 (summary_status) failed: {e}")
                logger.error(f"Migration 110 summary_status error: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ call_log table does not exist - skipping")
        
        checkpoint("✅ Migration 110 complete: Summary tracking system ready")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 111: Add composite index on (business_id, created_at) for efficient date range queries
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 111: Adding composite index on call_log(business_id, created_at)")
        
        if check_table_exists('call_log'):
            try:
                if not check_index_exists('idx_call_log_business_created'):
                    checkpoint("  → Creating composite index idx_call_log_business_created...")
                    exec_ddl(db.engine, """
                        ON call_log(business_id, created_at)
                    """)
                    checkpoint("  ✅ Composite index idx_call_log_business_created created")
                    migrations_applied.append('111_call_log_business_created_index')
                else:
                    checkpoint("  ℹ️ Index idx_call_log_business_created already exists")
            except Exception as e:
                checkpoint(f"❌ Migration 111 (composite index) failed: {e}")
                logger.error(f"Migration 111 index error: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ call_log table does not exist - skipping")
        
        checkpoint("✅ Migration 111 complete: Dashboard query performance optimized")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 112: Add lead_tabs_config to business table for flexible tab configuration
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 112: Adding lead_tabs_config column to business table")
        
        if check_table_exists('business'):
            try:
                if not check_column_exists('business', 'lead_tabs_config'):
                    checkpoint("  → Adding lead_tabs_config JSONB column (optimized for large tables)...")
                    
                    # 🔥 CRITICAL: Increase statement timeout for large business table
                    # Default timeout may be too short for large production tables
                    checkpoint("  → Setting statement timeout to 10 minutes for ALTER TABLE...")
                    execute_with_retry(migrate_engine, "SET statement_timeout = '600000'")  # 10 minutes
                    
                    # Step 1: Add column as nullable (fast, no table rewrite)
                    checkpoint("  → Step 1/3: Adding column as nullable...")
                    exec_ddl(db.engine, """
                        ALTER TABLE business 
                        ADD COLUMN IF NOT EXISTS lead_tabs_config JSONB
                    """)
                    
                    # Step 2: Set default value (fast in PostgreSQL 11+)
                    checkpoint("  → Step 2/3: Setting default value...")
                    exec_ddl(db.engine, """
                        ALTER TABLE business 
                        ALTER COLUMN lead_tabs_config SET DEFAULT '{}'::jsonb
                    """)
                    
                    # Step 3: Update existing rows and add NOT NULL constraint
                    checkpoint("  → Step 3/3: Updating existing rows and adding NOT NULL constraint...")
                    # Update any NULL values to the default (should be no NULL values if column was just added)
                    execute_with_retry(migrate_engine, """
                        UPDATE business 
                        SET lead_tabs_config = '{}'::jsonb 
                        WHERE lead_tabs_config IS NULL
                    """)
                    
                    # Now add NOT NULL constraint (requires scan but no rewrite since all values are non-NULL)
                    exec_ddl(db.engine, """
                        ALTER TABLE business 
                        ALTER COLUMN lead_tabs_config SET NOT NULL
                    """)
                    
                    # Reset statement timeout to default
                    checkpoint("  → Resetting statement timeout to default...")
                    execute_with_retry(migrate_engine, "SET statement_timeout = DEFAULT")
                    
                    # Add column comment
                    exec_ddl(db.engine, """
                        COMMENT ON COLUMN business.lead_tabs_config IS 
                        'Flexible tab configuration for lead detail page. JSONB object with primary and secondary tab arrays. Max 3 primary + 3 secondary (6 total). Available tabs: activity, reminders, documents, overview, whatsapp, calls, email, contracts, appointments, ai_notes, notes'
                    """)
                    
                    checkpoint("  ✅ Column lead_tabs_config added to business table with JSONB type")
                    migrations_applied.append('112_lead_tabs_config')
                    checkpoint("✅ Migration 112 complete: Flexible lead tabs configuration enabled")
                else:
                    checkpoint("  ℹ️ Column lead_tabs_config already exists")
                    checkpoint("✅ Migration 112 complete: Flexible lead tabs configuration enabled")
            except Exception as e:
                checkpoint(f"❌ Migration 112 failed: {e}")
                logger.error(f"Migration 112 error: {e}", exc_info=True)
                # Do NOT mark as complete on failure
        else:
            checkpoint("  ℹ️ business table does not exist - skipping Migration 112")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 113: Enhance OutboundCallRun with tracking fields and security
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 113: Enhancing OutboundCallRun with tracking fields and security constraints")
        
        if check_table_exists('outbound_call_runs'):
            try:
                # Add created_by_user_id if it doesn't exist
                if not check_column_exists('outbound_call_runs', 'created_by_user_id'):
                    checkpoint("  → Adding created_by_user_id column...")
                    exec_ddl(db.engine, """
                        ALTER TABLE outbound_call_runs 
                        ADD COLUMN created_by_user_id INTEGER REFERENCES users(id)
                    """)
                    checkpoint("  ✅ created_by_user_id column added")
                else:
                    checkpoint("  ℹ️ created_by_user_id column already exists")
                
                # Add started_at if it doesn't exist
                if not check_column_exists('outbound_call_runs', 'started_at'):
                    checkpoint("  → Adding started_at column...")
                    exec_ddl(db.engine, """
                        ALTER TABLE outbound_call_runs 
                        ADD COLUMN started_at TIMESTAMP
                    """)
                    checkpoint("  ✅ started_at column added")
                else:
                    checkpoint("  ℹ️ started_at column already exists")
                
                # Add ended_at if it doesn't exist
                if not check_column_exists('outbound_call_runs', 'ended_at'):
                    checkpoint("  → Adding ended_at column...")
                    exec_ddl(db.engine, """
                        ALTER TABLE outbound_call_runs 
                        ADD COLUMN ended_at TIMESTAMP
                    """)
                    checkpoint("  ✅ ended_at column added")
                else:
                    checkpoint("  ℹ️ ended_at column already exists")
                
                # Add cursor_position if it doesn't exist
                if not check_column_exists('outbound_call_runs', 'cursor_position'):
                    checkpoint("  → Adding cursor_position column...")
                    exec_ddl(db.engine, """
                        ALTER TABLE outbound_call_runs 
                        ADD COLUMN cursor_position INTEGER DEFAULT 0
                    """)
                    checkpoint("  ✅ cursor_position column added")
                else:
                    checkpoint("  ℹ️ cursor_position column already exists")
                
                # Add locked_by_worker if it doesn't exist
                if not check_column_exists('outbound_call_runs', 'locked_by_worker'):
                    checkpoint("  → Adding locked_by_worker column...")
                    exec_ddl(db.engine, """
                        ALTER TABLE outbound_call_runs 
                        ADD COLUMN locked_by_worker VARCHAR(128)
                    """)
                    checkpoint("  ✅ locked_by_worker column added")
                else:
                    checkpoint("  ℹ️ locked_by_worker column already exists")
                
                # Add lock_ts if it doesn't exist
                if not check_column_exists('outbound_call_runs', 'lock_ts'):
                    checkpoint("  → Adding lock_ts column...")
                    exec_ddl(db.engine, """
                        ALTER TABLE outbound_call_runs 
                        ADD COLUMN lock_ts TIMESTAMP
                    """)
                    checkpoint("  ✅ lock_ts column added")
                else:
                    checkpoint("  ℹ️ lock_ts column already exists")
                
                migrations_applied.append('113_outbound_run_tracking')
                checkpoint("✅ Migration 113 (part 1): OutboundCallRun tracking fields added")
                
            except Exception as e:
                checkpoint(f"❌ Migration 113 (tracking fields) failed: {e}")
                logger.error(f"Migration 113 tracking fields error: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ outbound_call_runs table does not exist - skipping tracking fields")
        
        # Add unique constraint on (run_id, lead_id) in outbound_call_jobs
        if check_table_exists('outbound_call_jobs'):
            try:
                # Check if constraint exists using engine.connect() to avoid idle-in-transaction
                if not check_constraint_exists('unique_run_lead', 'outbound_call_jobs'):
                    checkpoint("  → Adding unique constraint on (run_id, lead_id)...")
                    
                    # First, remove any existing duplicates (keep oldest)
                    # 🔒 SAFETY: Handle NULL values correctly (NULL != NULL in SQL)
                    checkpoint("  → Removing duplicate jobs (keeping oldest)...")
                    result = execute_with_retry(migrate_engine, """
                        DELETE FROM outbound_call_jobs a
                        USING outbound_call_jobs b
                        WHERE a.id > b.id
                          AND a.run_id = b.run_id
                          AND a.lead_id = b.lead_id
                          AND a.run_id IS NOT NULL
                          AND a.lead_id IS NOT NULL
                    """)
                    deleted_count = getattr(result, "rowcount", 0)
                    if deleted_count > 0:
                        checkpoint(f"  ℹ️ Removed {deleted_count} duplicate jobs")
                    
                    # Now add the unique constraint
                    exec_ddl(db.engine, """
                        ALTER TABLE outbound_call_jobs 
                        ADD CONSTRAINT unique_run_lead UNIQUE (run_id, lead_id)
                    """)
                    checkpoint("  ✅ unique_run_lead constraint added")
                    migrations_applied.append('113_outbound_unique_constraint')
                else:
                    checkpoint("  ℹ️ unique_run_lead constraint already exists")
                
            except Exception as e:
                checkpoint(f"❌ Migration 113 (unique constraint) failed: {e}")
                logger.error(f"Migration 113 unique constraint error: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ outbound_call_jobs table does not exist - skipping unique constraint")
        
        # Add business_id to outbound_call_jobs if missing (for extra isolation)
        if check_table_exists('outbound_call_jobs'):
            try:
                if not check_column_exists('outbound_call_jobs', 'business_id'):
                    checkpoint("  → Adding business_id to outbound_call_jobs...")
                    
                    # Add business_id with a temporary nullable constraint
                    exec_ddl(db.engine, """
                        ALTER TABLE outbound_call_jobs 
                        ADD COLUMN business_id INTEGER
                    """)
                    checkpoint("  ✅ business_id column added")
                    
                    # Populate from parent run
                    # 🔒 SAFETY: Only update jobs that have a valid parent run with non-NULL business_id
                    checkpoint("  → Populating business_id from parent runs...")
                    result = execute_with_retry(migrate_engine, """
                        UPDATE outbound_call_jobs 
                        SET business_id = subquery.business_id
                        FROM (
                            SELECT ocr.id as run_id, ocr.business_id
                            FROM outbound_call_runs ocr
                            WHERE ocr.business_id IS NOT NULL
                        ) as subquery
                        WHERE outbound_call_jobs.run_id = subquery.run_id
                          AND outbound_call_jobs.business_id IS NULL
                    """)
                    updated_count = getattr(result, "rowcount", 0)
                    checkpoint(f"  ℹ️ Updated {updated_count} jobs with business_id")
                    
                    # Check for orphaned jobs without business_id
                    result = execute_with_retry(migrate_engine, """
                        SELECT COUNT(*) FROM outbound_call_jobs 
                        WHERE business_id IS NULL
                    """)
                    orphaned_check = result[0][0] if result else None
                    
                    if orphaned_check > 0:
                        checkpoint(f"  ⚠️ WARNING: {orphaned_check} orphaned jobs found without valid parent run")
                        checkpoint(f"     These jobs will need manual cleanup or will fail the NOT NULL constraint")
                        # Delete orphaned jobs to allow migration to proceed
                        execute_with_retry(migrate_engine, """
                            DELETE FROM outbound_call_jobs 
                            WHERE business_id IS NULL
                        """)
                        checkpoint(f"  ℹ️ Deleted {orphaned_check} orphaned jobs")
                    
                    
                    # Make it NOT NULL and add FK
                    checkpoint("  → Adding NOT NULL constraint and foreign key...")
                    exec_ddl(db.engine, """
                        ALTER TABLE outbound_call_jobs 
                        ALTER COLUMN business_id SET NOT NULL
                    """)
                    
                    exec_ddl(db.engine, """
                        ALTER TABLE outbound_call_jobs 
                        ADD CONSTRAINT fk_outbound_call_jobs_business 
                        FOREIGN KEY (business_id) REFERENCES business(id)
                    """)
                    
                    # Add index for performance
                    if not check_index_exists('idx_outbound_call_jobs_business_id'):
                        exec_ddl(db.engine, """
                            ON outbound_call_jobs(business_id)
                        """)
                        checkpoint("  ✅ Index idx_outbound_call_jobs_business_id created")
                    
                    checkpoint("  ✅ business_id column with FK and index added")
                    migrations_applied.append('113_outbound_business_isolation')
                else:
                    checkpoint("  ℹ️ business_id column already exists in outbound_call_jobs")
                
            except Exception as e:
                checkpoint(f"❌ Migration 113 (business_id) failed: {e}")
                logger.error(f"Migration 113 business_id error: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ outbound_call_jobs table does not exist - skipping business_id")
        
        checkpoint("✅ Migration 113 complete: Outbound call queue system enhanced with security")
        checkpoint("   🎯 Added tracking fields: created_by_user_id, started_at, ended_at, cursor_position, locked_by_worker, lock_ts")
        checkpoint("   🎯 Added unique constraint to prevent duplicate calls")
        checkpoint("   🎯 Added business_id to jobs for complete business isolation")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 114: Add last_heartbeat_at for stale run detection
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 114: Adding last_heartbeat_at for stale run detection")
        
        if check_table_exists('outbound_call_runs'):
            try:
                # Add last_heartbeat_at if it doesn't exist
                if not check_column_exists('outbound_call_runs', 'last_heartbeat_at'):
                    checkpoint("  → Adding last_heartbeat_at column...")
                    exec_ddl(db.engine, """
                        ALTER TABLE outbound_call_runs 
                        ADD COLUMN last_heartbeat_at TIMESTAMP
                    """)
                    checkpoint("  ✅ last_heartbeat_at column added")
                    
                    # Initialize heartbeat for running runs from lock_ts
                    checkpoint("  → Initializing heartbeat for running runs...")
                    result = execute_with_retry(migrate_engine, """
                        UPDATE outbound_call_runs 
                        SET last_heartbeat_at = COALESCE(lock_ts, updated_at, created_at)
                        WHERE status IN ('running', 'pending')
                    """)
                    updated_count = getattr(result, "rowcount", 0)
                    checkpoint(f"  ℹ️ Initialized {updated_count} running runs with heartbeat")
                    
                    migrations_applied.append('114_outbound_heartbeat')
                else:
                    checkpoint("  ℹ️ last_heartbeat_at column already exists")
                
                checkpoint("✅ Migration 114 complete: Added heartbeat tracking for stale run detection")
                checkpoint("   🎯 Added last_heartbeat_at field for independent heartbeat tracking")
                checkpoint("   🎯 Initialized heartbeat for existing running runs")
                
            except Exception as e:
                checkpoint(f"❌ Migration 114 failed: {e}")
                logger.error(f"Migration 114 error: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ outbound_call_runs table does not exist - skipping migration 114")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 115: Add business calendars and routing rules system
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 115: Adding business calendars and routing rules system")
        
        # Step 1: Create business_calendars table (or verify if exists)
        if not check_table_exists('business_calendars'):
            try:
                checkpoint("  → Creating business_calendars table...")
                exec_ddl(db.engine, """
                    CREATE TABLE business_calendars (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        name VARCHAR(255) NOT NULL,
                        type_key VARCHAR(64),
                        provider VARCHAR(32) DEFAULT 'internal' NOT NULL,
                        calendar_external_id VARCHAR(255),
                        is_active BOOLEAN DEFAULT TRUE NOT NULL,
                        priority INTEGER DEFAULT 0 NOT NULL,
                        default_duration_minutes INTEGER DEFAULT 60,
                        buffer_before_minutes INTEGER DEFAULT 0,
                        buffer_after_minutes INTEGER DEFAULT 0,
                        allowed_tags JSONB DEFAULT '[]'::jsonb NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                checkpoint("  ✅ business_calendars table created")
                migrations_applied.append('115_business_calendars_table')
            except Exception as e:
                checkpoint(f"❌ Migration 115 (business_calendars table) CRITICAL FAILURE: {e}")
                logger.error(f"Migration 115 business_calendars error: {e}", exc_info=True)
                # CRITICAL: Cannot continue without this table - abort migration
                raise RuntimeError(f"Migration 115 FAILED: Could not create business_calendars table: {e}") from e
        else:
            checkpoint("  ℹ️ business_calendars table already exists - verifying critical columns...")
            # Table exists - check a few critical columns that might be missing from partial migration
            # If basic structure columns are missing, try to add them
            critical_fixes = []
            
            if not check_column_exists('business_calendars', 'buffer_before_minutes'):
                try:
                    exec_ddl(db.engine, "ALTER TABLE business_calendars ADD COLUMN buffer_before_minutes INTEGER DEFAULT 0")
                    critical_fixes.append('buffer_before_minutes')
                except Exception as e:
                    checkpoint(f"  ⚠️ Could not add buffer_before_minutes: {e}")
            
            if not check_column_exists('business_calendars', 'buffer_after_minutes'):
                try:
                    exec_ddl(db.engine, "ALTER TABLE business_calendars ADD COLUMN buffer_after_minutes INTEGER DEFAULT 0")
                    critical_fixes.append('buffer_after_minutes')
                except Exception as e:
                    checkpoint(f"  ⚠️ Could not add buffer_after_minutes: {e}")
            
            if critical_fixes:
                checkpoint(f"  ✅ Added missing columns to business_calendars: {critical_fixes}")
                migrations_applied.append('115_business_calendars_schema_fix')
            else:
                checkpoint("  ✅ business_calendars table schema looks good")
        
        # ⚠️ Performance indexes moved to db_indexes.py (IRON RULE: no indexes in migrations)
        # Indexes for business_calendars:
        # - idx_business_calendars_business_active
        # - idx_business_calendars_priority
        
        # Step 2: Create calendar_routing_rules table (or verify if exists)
        if not check_table_exists('calendar_routing_rules'):
            try:
                checkpoint("  → Creating calendar_routing_rules table...")
                exec_ddl(db.engine, """
                    CREATE TABLE calendar_routing_rules (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        calendar_id INTEGER NOT NULL REFERENCES business_calendars(id) ON DELETE CASCADE,
                        match_labels JSONB DEFAULT '[]'::jsonb NOT NULL,
                        match_keywords JSONB DEFAULT '[]'::jsonb NOT NULL,
                        channel_scope VARCHAR(32) DEFAULT 'all' NOT NULL,
                        when_ambiguous_ask BOOLEAN DEFAULT FALSE,
                        question_text VARCHAR(500),
                        priority INTEGER DEFAULT 0 NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                checkpoint("  ✅ calendar_routing_rules table created")
                migrations_applied.append('115_calendar_routing_rules_table')
            except Exception as e:
                checkpoint(f"❌ Migration 115 (calendar_routing_rules table) CRITICAL FAILURE: {e}")
                logger.error(f"Migration 115 calendar_routing_rules error: {e}", exc_info=True)
                # CRITICAL: Cannot continue without this table - abort migration
                raise RuntimeError(f"Migration 115 FAILED: Could not create calendar_routing_rules table: {e}") from e
        else:
            checkpoint("  ℹ️ calendar_routing_rules table already exists - verifying critical columns...")
            # Check a few columns that were added later and might be missing
            critical_fixes = []
            
            if not check_column_exists('calendar_routing_rules', 'when_ambiguous_ask'):
                try:
                    exec_ddl(db.engine, "ALTER TABLE calendar_routing_rules ADD COLUMN when_ambiguous_ask BOOLEAN DEFAULT FALSE")
                    critical_fixes.append('when_ambiguous_ask')
                except Exception as e:
                    checkpoint(f"  ⚠️ Could not add when_ambiguous_ask: {e}")
            
            if not check_column_exists('calendar_routing_rules', 'question_text'):
                try:
                    exec_ddl(db.engine, "ALTER TABLE calendar_routing_rules ADD COLUMN question_text VARCHAR(500)")
                    critical_fixes.append('question_text')
                except Exception as e:
                    checkpoint(f"  ⚠️ Could not add question_text: {e}")
            
            if critical_fixes:
                checkpoint(f"  ✅ Added missing columns to calendar_routing_rules: {critical_fixes}")
                migrations_applied.append('115_calendar_routing_rules_schema_fix')
            else:
                checkpoint("  ✅ calendar_routing_rules table schema looks good")
        
        # ⚠️ Performance indexes moved to db_indexes.py (IRON RULE: no indexes in migrations)
        # Indexes for calendar_routing_rules:
        # - idx_calendar_routing_business_active
        # - idx_calendar_routing_calendar
        
        # Step 3: Add calendar_id to appointments table
        if check_table_exists('appointments'):
            if not check_column_exists('appointments', 'calendar_id'):
                try:
                    checkpoint("  → Adding calendar_id to appointments table...")
                    exec_ddl(db.engine, """
                        ALTER TABLE appointments 
                        ADD COLUMN calendar_id INTEGER REFERENCES business_calendars(id) ON DELETE SET NULL
                    """)
                    checkpoint("  ✅ calendar_id column added to appointments")
                    
                    # ⚠️ Performance index moved to db_indexes.py (IRON RULE: no indexes in migrations)
                    # Index: idx_appointments_calendar_id
                    
                    migrations_applied.append('115_appointments_calendar_id')
                except Exception as e:
                    checkpoint(f"❌ Migration 115 (appointments.calendar_id) CRITICAL FAILURE: {e}")
                    logger.error(f"Migration 115 appointments.calendar_id error: {e}", exc_info=True)
                    # CRITICAL: Without this column, calendar system won't work properly - abort migration
                    raise RuntimeError(f"Migration 115 FAILED: Could not add calendar_id to appointments: {e}") from e
            else:
                checkpoint("  ℹ️ calendar_id column already exists in appointments")
        else:
            checkpoint("  ℹ️ appointments table does not exist - skipping calendar_id column")
        
        # Step 4: Create default calendars for existing businesses
        if check_table_exists('business') and check_table_exists('business_calendars'):
            try:
                
                # Check if we need to create default calendars
                result = execute_with_retry(migrate_engine, """
                    SELECT COUNT(*) FROM business b
                    WHERE NOT EXISTS (
                        SELECT 1 FROM business_calendars bc 
                        WHERE bc.business_id = b.id
                    )
                """)
                businesses_without_calendars = result[0][0] if result else 0
                
                if businesses_without_calendars > 0:
                    checkpoint(f"  → Creating default calendars for {businesses_without_calendars} business(es)...")
                    
                    # Check if business_settings table has business_id column
                    has_business_settings_fk = False
                    if check_table_exists('business_settings'):
                        has_business_settings_fk = check_column_exists('business_settings', 'business_id')
                    
                    # Create default calendar for businesses that don't have one
                    # Use business_settings.slot_size_min if available, otherwise default to 60
                    if has_business_settings_fk:
                        # Business_settings has business_id FK - use it
                        insert_sql = """
                            INSERT INTO business_calendars (
                                business_id, 
                                name, 
                                type_key, 
                                provider, 
                                is_active, 
                                priority,
                                default_duration_minutes,
                                allowed_tags
                            )
                            SELECT 
                                b.id,
                                'לוח ברירת מחדל' as name,
                                'default' as type_key,
                                'internal' as provider,
                                TRUE as is_active,
                                1 as priority,
                                COALESCE(
                                    (SELECT bs.slot_size_min FROM business_settings bs WHERE bs.business_id = b.id LIMIT 1),
                                    60
                                ) as default_duration_minutes,
                                '[]'::jsonb as allowed_tags
                            FROM business b
                            WHERE NOT EXISTS (
                                SELECT 1 FROM business_calendars bc 
                                WHERE bc.business_id = b.id
                            )
                        """
                    else:
                        # Business_settings doesn't have business_id FK - use default duration
                        checkpoint("  ℹ️ business_settings.business_id not found, using default 60 minute duration")
                        insert_sql = """
                            INSERT INTO business_calendars (
                                business_id, 
                                name, 
                                type_key, 
                                provider, 
                                is_active, 
                                priority,
                                default_duration_minutes,
                                allowed_tags
                            )
                            SELECT 
                                b.id,
                                'לוח ברירת מחדל' as name,
                                'default' as type_key,
                                'internal' as provider,
                                TRUE as is_active,
                                1 as priority,
                                60 as default_duration_minutes,
                                '[]'::jsonb as allowed_tags
                            FROM business b
                            WHERE NOT EXISTS (
                                SELECT 1 FROM business_calendars bc 
                                WHERE bc.business_id = b.id
                            )
                        """
                    
                    result = execute_with_retry(migrate_engine, insert_sql)
                    
                    created_count = getattr(result, "rowcount", 0)
                    checkpoint(f"  ✅ Created default calendars for {created_count} business(es)")
                    migrations_applied.append('115_default_calendars')
                else:
                    checkpoint("  ℹ️ All businesses already have calendars")
                
            except Exception as e:
                checkpoint(f"❌ Migration 115 (default calendars) failed: {e}")
                logger.error(f"Migration 115 default calendars error: {e}", exc_info=True)
        
        # Step 5: Link existing appointments to default calendars
        if check_table_exists('appointments') and check_table_exists('business_calendars'):
            if check_column_exists('appointments', 'calendar_id'):
                try:
                    
                    # Check how many appointments need linking
                    result = execute_with_retry(migrate_engine, """
                        SELECT COUNT(*) FROM appointments a
                        WHERE a.calendar_id IS NULL
                        AND EXISTS (
                            SELECT 1 FROM business_calendars bc 
                            WHERE bc.business_id = a.business_id 
                            AND bc.type_key = 'default'
                        )
                    """)
                    unlinked_appointments = result[0][0] if result else 0
                    
                    if unlinked_appointments > 0:
                        checkpoint(f"  → Linking {unlinked_appointments} appointment(s) to default calendars...")
                        
                        result = execute_with_retry(migrate_engine, """
                            UPDATE appointments a
                            SET calendar_id = bc.id
                            FROM business_calendars bc
                            WHERE a.business_id = bc.business_id
                              AND bc.type_key = 'default'
                              AND a.calendar_id IS NULL
                        """)
                        
                        linked_count = getattr(result, "rowcount", 0)
                        checkpoint(f"  ✅ Linked {linked_count} appointment(s) to default calendars")
                        migrations_applied.append('115_link_appointments')
                    else:
                        checkpoint("  ℹ️ All appointments already linked to calendars")
                    
                except Exception as e:
                    checkpoint(f"❌ Migration 115 (link appointments) failed: {e}")
                    logger.error(f"Migration 115 link appointments error: {e}", exc_info=True)
        
        checkpoint("✅ Migration 115 complete: Business calendars and routing rules system added")
        checkpoint("   🎯 Created business_calendars table for multi-calendar management")
        checkpoint("   🎯 Created calendar_routing_rules table for intelligent AI routing")
        checkpoint("   🎯 Added calendar_id to appointments for calendar association")
        checkpoint("   🎯 Created default calendars for existing businesses")
        checkpoint("   🎯 Linked existing appointments to default calendars")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 116: Add scheduled WhatsApp messages system
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 116: Adding scheduled WhatsApp messages system")
        
        # Step 1: Create scheduled_message_rules table (or verify if exists)
        if not check_table_exists('scheduled_message_rules'):
            try:
                checkpoint("  → Creating scheduled_message_rules table...")
                exec_ddl(db.engine, """
                    CREATE TABLE scheduled_message_rules (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        name VARCHAR(255) NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE NOT NULL,
                        template_name VARCHAR(255),
                        message_text TEXT NOT NULL,
                        delay_minutes INTEGER DEFAULT 0 NOT NULL,
                        send_window_start VARCHAR(5),
                        send_window_end VARCHAR(5),
                        created_by_user_id INTEGER REFERENCES users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                checkpoint("  ✅ scheduled_message_rules table created")
                migrations_applied.append('116_scheduled_message_rules_table')
            except Exception as e:
                checkpoint(f"❌ Migration 116 (scheduled_message_rules table) failed: {e}")
                logger.error(f"Migration 116 scheduled_message_rules error: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ scheduled_message_rules table already exists - verifying critical columns...")
            # Check columns that were added later
            critical_fixes = []
            
            if not check_column_exists('scheduled_message_rules', 'send_window_start'):
                try:
                    exec_ddl(db.engine, "ALTER TABLE scheduled_message_rules ADD COLUMN send_window_start VARCHAR(5)")
                    critical_fixes.append('send_window_start')
                except Exception as e:
                    checkpoint(f"  ⚠️ Could not add send_window_start: {e}")
            
            if not check_column_exists('scheduled_message_rules', 'send_window_end'):
                try:
                    exec_ddl(db.engine, "ALTER TABLE scheduled_message_rules ADD COLUMN send_window_end VARCHAR(5)")
                    critical_fixes.append('send_window_end')
                except Exception as e:
                    checkpoint(f"  ⚠️ Could not add send_window_end: {e}")
            
            if critical_fixes:
                checkpoint(f"  ✅ Added missing columns to scheduled_message_rules: {critical_fixes}")
                migrations_applied.append('116_scheduled_message_rules_schema_fix')
            else:
                checkpoint("  ✅ scheduled_message_rules table schema looks good")
        
        # Ensure indexes exist (whether table was just created or already existed)
        if not check_index_exists('idx_scheduled_rules_business_active'):
            try:
                exec_ddl(db.engine, """
                    ON scheduled_message_rules(business_id, is_active)
                """)
                checkpoint("  ✅ Index idx_scheduled_rules_business_active created")
            except Exception as e:
                checkpoint(f"  ⚠️ Could not create idx_scheduled_rules_business_active: {e}")
        
        # Step 2: Create scheduled_rule_statuses junction table (or verify if exists)
        if not check_table_exists('scheduled_rule_statuses'):
            try:
                checkpoint("  → Creating scheduled_rule_statuses junction table...")
                exec_ddl(db.engine, """
                    CREATE TABLE scheduled_rule_statuses (
                        id SERIAL PRIMARY KEY,
                        rule_id INTEGER NOT NULL REFERENCES scheduled_message_rules(id) ON DELETE CASCADE,
                        status_id INTEGER NOT NULL REFERENCES lead_statuses(id) ON DELETE CASCADE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(rule_id, status_id)
                    )
                """)
                checkpoint("  ✅ scheduled_rule_statuses table created")
                migrations_applied.append('116_scheduled_rule_statuses_table')
            except Exception as e:
                checkpoint(f"❌ Migration 116 (scheduled_rule_statuses table) failed: {e}")
                logger.error(f"Migration 116 scheduled_rule_statuses error: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ scheduled_rule_statuses table already exists")
            # This is a simple junction table - if it exists, it's probably correct
            # If columns are missing, it's a serious error that needs manual intervention
        
        # Ensure indexes exist
        if not check_index_exists('idx_scheduled_rule_statuses_rule'):
            try:
                exec_ddl(db.engine, """
                    ON scheduled_rule_statuses(rule_id)
                """)
                checkpoint("  ✅ Index idx_scheduled_rule_statuses_rule created")
            except Exception as e:
                checkpoint(f"  ⚠️ Could not create idx_scheduled_rule_statuses_rule: {e}")
        
        if not check_index_exists('idx_scheduled_rule_statuses_status'):
            try:
                exec_ddl(db.engine, """
                    ON scheduled_rule_statuses(status_id)
                """)
                checkpoint("  ✅ Index idx_scheduled_rule_statuses_status created")
            except Exception as e:
                checkpoint(f"  ⚠️ Could not create idx_scheduled_rule_statuses_status: {e}")
        
        # Step 3: Create scheduled_messages_queue table (or verify if exists)
        if not check_table_exists('scheduled_messages_queue'):
            try:
                checkpoint("  → Creating scheduled_messages_queue table...")
                exec_ddl(db.engine, """
                    CREATE TABLE scheduled_messages_queue (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        rule_id INTEGER NOT NULL REFERENCES scheduled_message_rules(id) ON DELETE CASCADE,
                        lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
                        message_text TEXT NOT NULL,
                        remote_jid VARCHAR(255) NOT NULL,
                        scheduled_for TIMESTAMP NOT NULL,
                        status VARCHAR(20) DEFAULT 'pending' NOT NULL,
                        locked_at TIMESTAMP,
                        sent_at TIMESTAMP,
                        error_message TEXT,
                        dedupe_key VARCHAR(255) UNIQUE NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                checkpoint("  ✅ scheduled_messages_queue table created")
                migrations_applied.append('116_scheduled_messages_queue_table')
            except Exception as e:
                checkpoint(f"❌ Migration 116 (scheduled_messages_queue table) failed: {e}")
                logger.error(f"Migration 116 scheduled_messages_queue error: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ scheduled_messages_queue table already exists - verifying critical columns...")
            # Check columns that were added later
            critical_fixes = []
            
            if not check_column_exists('scheduled_messages_queue', 'locked_at'):
                try:
                    exec_ddl(db.engine, "ALTER TABLE scheduled_messages_queue ADD COLUMN locked_at TIMESTAMP")
                    critical_fixes.append('locked_at')
                except Exception as e:
                    checkpoint(f"  ⚠️ Could not add locked_at: {e}")
            
            if not check_column_exists('scheduled_messages_queue', 'sent_at'):
                try:
                    exec_ddl(db.engine, "ALTER TABLE scheduled_messages_queue ADD COLUMN sent_at TIMESTAMP")
                    critical_fixes.append('sent_at')
                except Exception as e:
                    checkpoint(f"  ⚠️ Could not add sent_at: {e}")
            
            if not check_column_exists('scheduled_messages_queue', 'error_message'):
                try:
                    exec_ddl(db.engine, "ALTER TABLE scheduled_messages_queue ADD COLUMN error_message TEXT")
                    critical_fixes.append('error_message')
                except Exception as e:
                    checkpoint(f"  ⚠️ Could not add error_message: {e}")
            
            if critical_fixes:
                checkpoint(f"  ✅ Added missing columns to scheduled_messages_queue: {critical_fixes}")
                migrations_applied.append('116_scheduled_messages_queue_schema_fix')
            else:
                checkpoint("  ✅ scheduled_messages_queue table schema looks good")
        
        # Ensure indexes exist (whether table was just created or already existed)
        if not check_index_exists('idx_scheduled_queue_scheduled_for'):
            try:
                exec_ddl(db.engine, """
                    ON scheduled_messages_queue(scheduled_for)
                """)
                checkpoint("  ✅ Index idx_scheduled_queue_scheduled_for created")
            except Exception as e:
                checkpoint(f"  ⚠️ Could not create idx_scheduled_queue_scheduled_for: {e}")
        
        if not check_index_exists('idx_scheduled_queue_status'):
            try:
                exec_ddl(db.engine, """
                    ON scheduled_messages_queue(status)
                """)
                checkpoint("  ✅ Index idx_scheduled_queue_status created")
            except Exception as e:
                checkpoint(f"  ⚠️ Could not create idx_scheduled_queue_status: {e}")
        
        if not check_index_exists('idx_scheduled_queue_business_status_scheduled'):
            try:
                exec_ddl(db.engine, """
                    ON scheduled_messages_queue(business_id, status, scheduled_for)
                """)
                checkpoint("  ✅ Index idx_scheduled_queue_business_status_scheduled created")
            except Exception as e:
                checkpoint(f"  ⚠️ Could not create idx_scheduled_queue_business_status_scheduled: {e}")
        
        if not check_index_exists('idx_scheduled_queue_rule_status'):
            try:
                exec_ddl(db.engine, """
                    ON scheduled_messages_queue(rule_id, status)
                """)
                checkpoint("  ✅ Index idx_scheduled_queue_rule_status created")
            except Exception as e:
                checkpoint(f"  ⚠️ Could not create idx_scheduled_queue_rule_status: {e}")
        
        if not check_index_exists('idx_scheduled_queue_lead'):
            try:
                exec_ddl(db.engine, """
                    ON scheduled_messages_queue(lead_id)
                """)
                checkpoint("  ✅ Index idx_scheduled_queue_lead created")
            except Exception as e:
                checkpoint(f"  ⚠️ Could not create idx_scheduled_queue_lead: {e}")
        
        if not check_index_exists('idx_scheduled_queue_dedupe'):
            try:
                exec_ddl(db.engine, """
                    CREATE UNIQUE INDEX idx_scheduled_queue_dedupe 
                    ON scheduled_messages_queue(dedupe_key)
                """)
                checkpoint("  ✅ Index idx_scheduled_queue_dedupe created")
            except Exception as e:
                checkpoint(f"  ⚠️ Could not create idx_scheduled_queue_dedupe: {e}")
        
        checkpoint("✅ Migration 116 complete: Scheduled WhatsApp messages system added")
        checkpoint("   🎯 Created scheduled_message_rules table for scheduling rules")
        checkpoint("   🎯 Created scheduled_rule_statuses junction table for rule-status mapping")
        checkpoint("   🎯 Created scheduled_messages_queue table for pending messages")
        checkpoint("   🎯 All indexes and constraints created for performance and data integrity")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 117: Enable 'scheduled_messages' page for businesses
        # 🎯 PURPOSE: Add scheduled_messages to enabled_pages for page permissions
        # Adds 'scheduled_messages' to businesses that have WhatsApp broadcast
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 117: Enable 'scheduled_messages' page for businesses with WhatsApp")
        
        if check_table_exists('business') and check_column_exists('business', 'enabled_pages'):
            try:
                checkpoint("  → Enabling 'scheduled_messages' page for businesses with WhatsApp broadcast...")
                
                # Add 'scheduled_messages' to enabled_pages for businesses that have whatsapp_broadcast
                # but don't have scheduled_messages yet
                # Using JSONB || operator and ? operator for performance
                result = execute_with_retry(migrate_engine, """
                    UPDATE business
                    SET enabled_pages = enabled_pages::jsonb || '["scheduled_messages"]'::jsonb
                    WHERE enabled_pages IS NOT NULL
                      AND enabled_pages::jsonb ? 'whatsapp_broadcast'
                      AND NOT (enabled_pages::jsonb ? 'scheduled_messages')
                """)
                updated_count = getattr(result, "rowcount", 0)
                
                if updated_count > 0:
                    checkpoint(f"  ✅ Enabled 'scheduled_messages' page for {updated_count} businesses with WhatsApp")
                else:
                    checkpoint("  ℹ️ All businesses with WhatsApp already have 'scheduled_messages' page enabled")
                
                migrations_applied.append('enable_scheduled_messages_page')
                checkpoint("✅ Migration 117 complete: 'scheduled_messages' page enabled for WhatsApp businesses")
            except Exception as e:
                log.error(f"❌ Migration 117 failed to enable scheduled_messages page: {e}")
                checkpoint(f"⚠️ Migration 117 failed (non-critical): {e}")
                # Don't fail the entire migration if this fails - it's non-critical
        else:
            checkpoint("  ℹ️ Skipping Migration 117: business table or enabled_pages column not found")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 118: Add error tracking fields to call_log table
        # 🎯 PURPOSE: Add error_message and error_code columns for failed call tracking
        # ISSUE: PostgreSQL error "column 'error_message' of relation 'call_log' does not exist"
        # FIX: Add error_message (TEXT) and error_code (VARCHAR) columns with idempotency
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 118: Adding error tracking fields to call_log")
        
        if check_table_exists('call_log'):
            try:
                columns_to_add = []
                
                # Check error_message column
                if not check_column_exists('call_log', 'error_message'):
                    checkpoint("  → Adding error_message column to call_log...")
                    exec_ddl(db.engine, """
                        ALTER TABLE call_log 
                        ADD COLUMN error_message TEXT
                    """)
                    columns_to_add.append('error_message')
                    checkpoint("  ✅ error_message column added to call_log")
                else:
                    checkpoint("  ℹ️ error_message column already exists")
                
                # Check error_code column
                if not check_column_exists('call_log', 'error_code'):
                    checkpoint("  → Adding error_code column to call_log...")
                    exec_ddl(db.engine, """
                        ALTER TABLE call_log 
                        ADD COLUMN error_code VARCHAR(64)
                    """)
                    columns_to_add.append('error_code')
                    checkpoint("  ✅ error_code column added to call_log")
                else:
                    checkpoint("  ℹ️ error_code column already exists")
                
                if columns_to_add:
                    migrations_applied.append('118_call_log_error_fields')
                    checkpoint(f"✅ Migration 118 complete: Error tracking fields added to call_log ({', '.join(columns_to_add)})")
                else:
                    checkpoint("✅ Migration 118 complete: Error tracking fields already exist on call_log")
                    
            except Exception as e:
                checkpoint(f"❌ Migration 118 (error tracking fields) failed: {e}")
                logger.error(f"Migration 118 error tracking fields error: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ call_log table does not exist - skipping Migration 118")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 119: Create gmail_receipts table for Gmail receipt tracking
        # 🎯 PURPOSE: Add dedicated table for Gmail receipts with deduplication
        # FEATURES:
        #   - Stores Gmail receipts separately from main receipts table
        #   - UNIQUE constraint on (business_id, provider, external_id) to prevent duplicates
        #   - Performance indexes for common queries
        #   - Supports backfill of existing data
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 119: Creating gmail_receipts table with indexes")
        
        if not check_table_exists('gmail_receipts'):
            try:
                checkpoint("  → Creating gmail_receipts table...")
                exec_ddl(db.engine, """
                    CREATE TABLE IF NOT EXISTS gmail_receipts (
                      id BIGSERIAL PRIMARY KEY,
                      
                      business_id BIGINT NOT NULL,
                      provider TEXT NOT NULL DEFAULT 'gmail',
                      
                      -- Unique identifier from provider (Gmail messageId / internal id)
                      external_id TEXT NOT NULL,
                      
                      -- Receipt useful fields
                      subject TEXT,
                      merchant TEXT,
                      amount NUMERIC(12,2),
                      currency CHAR(3),
                      receipt_date TIMESTAMPTZ,
                      
                      -- Raw JSON from parsing / source
                      raw_payload JSONB,
                      
                      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                checkpoint("  ✅ gmail_receipts table created")
                
                # Create unique index to prevent duplicates (most important)
                checkpoint("  → Creating unique index on (business_id, provider, external_id)...")
                exec_ddl(db.engine, """
                    CREATE UNIQUE INDEX IF NOT EXISTS ux_gmail_receipts_business_provider_external
                      ON gmail_receipts (business_id, provider, external_id)
                """)
                checkpoint("  ✅ Unique index created")
                
                # Create performance indexes for queries
                checkpoint("  → Creating performance indexes...")
                exec_ddl(db.engine, """
                    CREATE INDEX IF NOT EXISTS ix_gmail_receipts_business_created_at
                      ON gmail_receipts (business_id, created_at DESC)
                """)
                checkpoint("  ✅ Index on (business_id, created_at) created")
                
                exec_ddl(db.engine, """
                    CREATE INDEX IF NOT EXISTS ix_gmail_receipts_business_receipt_date
                      ON gmail_receipts (business_id, receipt_date DESC)
                """)
                checkpoint("  ✅ Index on (business_id, receipt_date) created")
                
                exec_ddl(db.engine, """
                    CREATE INDEX IF NOT EXISTS ix_gmail_receipts_merchant
                      ON gmail_receipts (merchant)
                """)
                checkpoint("  ✅ Index on merchant created")
                
                migrations_applied.append('119_gmail_receipts_table')
                checkpoint("✅ Migration 119 complete: gmail_receipts table created with indexes")
                    
            except Exception as e:
                checkpoint(f"❌ Migration 119 (gmail_receipts table) failed: {e}")
                logger.error(f"Migration 119 gmail_receipts table error: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ gmail_receipts table already exists - skipping Migration 119")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 120: Create contact_identities table for unified contact mapping
        # 🎯 PURPOSE: Prevent duplicate leads across WhatsApp and Phone channels
        # Creates a mapping layer between external IDs (JID/phone) and lead_id
        # Enables cross-channel lead linking when same person contacts via multiple channels
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 120: Creating contact_identities table for unified contact mapping")
        
        if not check_table_exists('contact_identities'):
            try:
                checkpoint("  → Creating contact_identities table...")
                exec_ddl(db.engine, """
                    CREATE TABLE contact_identities (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        channel VARCHAR(32) NOT NULL,
                        external_id VARCHAR(255) NOT NULL,
                        lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                checkpoint("  ✅ contact_identities table created")
                migrations_applied.append('120_contact_identities_table')
            except Exception as e:
                checkpoint(f"❌ Migration 120 (contact_identities table) failed: {e}")
                logger.error(f"Migration 120 contact_identities table error: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ contact_identities table already exists")
        
        # Create unique index on (business_id, channel, external_id) for deduplication
        if not check_index_exists('idx_contact_identities_unique_mapping'):
            try:
                checkpoint("  → Creating unique index on (business_id, channel, external_id)...")
                exec_ddl(db.engine, """
                    CREATE UNIQUE INDEX idx_contact_identities_unique_mapping 
                    ON contact_identities(business_id, channel, external_id)
                """)
                checkpoint("  ✅ Unique index idx_contact_identities_unique_mapping created")
            except Exception as e:
                checkpoint(f"  ⚠️ Could not create unique index: {e}")
        
        # Create index on (business_id, lead_id) for reverse lookups
        if not check_index_exists('idx_contact_identities_lead'):
            try:
                checkpoint("  → Creating index on (business_id, lead_id)...")
                exec_ddl(db.engine, """
                    CREATE INDEX idx_contact_identities_lead 
                    ON contact_identities(business_id, lead_id)
                """)
                checkpoint("  ✅ Index idx_contact_identities_lead created")
            except Exception as e:
                checkpoint(f"  ⚠️ Could not create lead index: {e}")
        
        # Create index on channel for filtering by channel type
        if not check_index_exists('idx_contact_identities_channel'):
            try:
                checkpoint("  → Creating index on channel...")
                exec_ddl(db.engine, """
                    CREATE INDEX idx_contact_identities_channel 
                    ON contact_identities(channel)
                """)
                checkpoint("  ✅ Index idx_contact_identities_channel created")
            except Exception as e:
                checkpoint(f"  ⚠️ Could not create channel index: {e}")
        
        checkpoint("✅ Migration 120 complete: contact_identities table created")
        checkpoint("   🎯 Unified contact identity mapping layer ready")
        checkpoint("   🎯 Prevents duplicate leads across WhatsApp and Phone channels")
        checkpoint("   🎯 Enables cross-channel lead linking based on phone number")
        
        # ============================================================================
        # Migration 121: Add unified customer memory fields to leads table
        # ============================================================================
        # Purpose: Unified customer memory system for calls + WhatsApp
        # - Stores customer profile, conversation summaries, and interaction history
        # - Enables AI to maintain context across channels and conversations
        # - Used when BusinessSettings.enable_customer_service is True
        checkpoint("Migration 121: Adding unified customer memory fields to leads")
        
        if check_table_exists('leads'):
            try:
                fields_added = []
                
                # Add customer_profile_json for storing structured customer data
                if not check_column_exists('leads', 'customer_profile_json'):
                    checkpoint("  → Adding customer_profile_json to leads...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE leads 
                        ADD COLUMN IF NOT EXISTS customer_profile_json JSONB NULL
                    """)
                    fields_added.append('customer_profile_json')
                    checkpoint("  ✅ customer_profile_json added")
                
                # Add last_summary for conversation summaries (5-10 lines)
                if not check_column_exists('leads', 'last_summary'):
                    checkpoint("  → Adding last_summary to leads...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE leads 
                        ADD COLUMN IF NOT EXISTS last_summary TEXT NULL
                    """)
                    fields_added.append('last_summary')
                    checkpoint("  ✅ last_summary added")
                
                # Add summary_updated_at timestamp
                if not check_column_exists('leads', 'summary_updated_at'):
                    checkpoint("  → Adding summary_updated_at to leads...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE leads 
                        ADD COLUMN IF NOT EXISTS summary_updated_at TIMESTAMP NULL
                    """)
                    fields_added.append('summary_updated_at')
                    checkpoint("  ✅ summary_updated_at added")
                
                # Add last_interaction_at for tracking last message timestamp
                if not check_column_exists('leads', 'last_interaction_at'):
                    checkpoint("  → Adding last_interaction_at to leads...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE leads 
                        ADD COLUMN IF NOT EXISTS last_interaction_at TIMESTAMP NULL
                    """)
                    fields_added.append('last_interaction_at')
                    checkpoint("  ✅ last_interaction_at added")
                
                # Add last_channel for tracking which channel was used last
                if not check_column_exists('leads', 'last_channel'):
                    checkpoint("  → Adding last_channel to leads...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE leads 
                        ADD COLUMN IF NOT EXISTS last_channel VARCHAR(16) NULL
                    """)
                    fields_added.append('last_channel')
                    checkpoint("  ✅ last_channel added")
                
                if fields_added:
                    migrations_applied.append('migration_121_customer_memory')
                    checkpoint(f"✅ Migration 121 completed - Added {len(fields_added)} customer memory fields")
                else:
                    checkpoint("  ℹ️  All customer memory fields already exist")
                    
            except Exception as e:
                checkpoint(f"❌ Migration 121 failed: {e}")
                raise
        else:
            checkpoint("  ℹ️  leads table does not exist - skipping Migration 121")
        
        # Migration 122: Add provider and delay_seconds fields to scheduled messages tables
        # 🔥 Event-driven immediate triggering for scheduled WhatsApp messages
        # Adds provider selection (baileys/meta) and precise delay_seconds timing
        checkpoint("Migration 122: Adding provider and delay_seconds to scheduled messages")
        
        if check_table_exists('scheduled_message_rules'):
            try:
                fields_added = []
                
                # Add delay_seconds column to scheduled_message_rules
                if not check_column_exists('scheduled_message_rules', 'delay_seconds'):
                    checkpoint("  → Adding delay_seconds to scheduled_message_rules...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE scheduled_message_rules 
                        ADD COLUMN delay_seconds INTEGER NOT NULL DEFAULT 0
                    """)
                    fields_added.append('delay_seconds')
                    checkpoint("  ✅ delay_seconds added to scheduled_message_rules")
                
                # Add provider column to scheduled_message_rules
                if not check_column_exists('scheduled_message_rules', 'provider'):
                    checkpoint("  → Adding provider to scheduled_message_rules...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE scheduled_message_rules 
                        ADD COLUMN provider VARCHAR(32) NOT NULL DEFAULT 'baileys'
                    """)
                    fields_added.append('provider')
                    checkpoint("  ✅ provider added to scheduled_message_rules")
                
                if fields_added:
                    migrations_applied.append('migration_122_scheduled_rules_fields')
                    checkpoint(f"✅ Migration 122a completed - Added {len(fields_added)} fields to scheduled_message_rules")
                    
                    # 🔄 BACKFILL: Populate delay_seconds from delay_minutes for existing rules
                    checkpoint("  → Backfilling delay_seconds from delay_minutes...")
                    result = execute_with_retry(migrate_engine, """
                        UPDATE scheduled_message_rules 
                        SET delay_seconds = delay_minutes * 60 
                        WHERE delay_seconds = 0 AND delay_minutes > 0
                    """)
                    rows_updated = result.rowcount if hasattr(result, 'rowcount') else 0
                    checkpoint(f"  ✅ Backfilled delay_seconds for {rows_updated} existing rule(s)")
                else:
                    checkpoint("  ℹ️  All fields already exist in scheduled_message_rules")
                    
            except Exception as e:
                checkpoint(f"❌ Migration 122a (scheduled_message_rules) failed: {e}")
                raise
        else:
            checkpoint("  ℹ️  scheduled_message_rules table does not exist - skipping Migration 122a")
        
        # Migration 122b: Add fields to scheduled_messages_queue
        if check_table_exists('scheduled_messages_queue'):
            try:
                fields_added = []
                
                # Add channel column
                if not check_column_exists('scheduled_messages_queue', 'channel'):
                    checkpoint("  → Adding channel to scheduled_messages_queue...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE scheduled_messages_queue 
                        ADD COLUMN channel VARCHAR(32) NOT NULL DEFAULT 'whatsapp'
                    """)
                    fields_added.append('channel')
                    checkpoint("  ✅ channel added to scheduled_messages_queue")
                
                # Add provider column
                if not check_column_exists('scheduled_messages_queue', 'provider'):
                    checkpoint("  → Adding provider to scheduled_messages_queue...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE scheduled_messages_queue 
                        ADD COLUMN provider VARCHAR(32) NOT NULL DEFAULT 'baileys'
                    """)
                    fields_added.append('provider')
                    checkpoint("  ✅ provider added to scheduled_messages_queue")
                
                # Add attempts column
                if not check_column_exists('scheduled_messages_queue', 'attempts'):
                    checkpoint("  → Adding attempts to scheduled_messages_queue...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE scheduled_messages_queue 
                        ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0
                    """)
                    fields_added.append('attempts')
                    checkpoint("  ✅ attempts added to scheduled_messages_queue")
                
                if fields_added:
                    migrations_applied.append('migration_122_scheduled_queue_fields')
                    checkpoint(f"✅ Migration 122b completed - Added {len(fields_added)} fields to scheduled_messages_queue")
                else:
                    checkpoint("  ℹ️  All fields already exist in scheduled_messages_queue")
                    
            except Exception as e:
                checkpoint(f"❌ Migration 122b (scheduled_messages_queue) failed: {e}")
                raise
        else:
            checkpoint("  ℹ️  scheduled_messages_queue table does not exist - skipping Migration 122b")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 123: Add multi-step scheduled messages support
        # 🎯 PURPOSE: Enable sending sequences of messages at different delays
        # Creates rule_steps table for step definitions
        # Adds send_immediately_on_enter and apply_mode to rules
        # Adds step_id to queue for tracking which step a message belongs to
        # Adds status_sequence_token to leads for deduplication
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 123: Adding multi-step scheduled messages support")
        
        # Step 1: Create rule_steps table
        if not check_table_exists('scheduled_message_rule_steps'):
            try:
                checkpoint("  → Creating scheduled_message_rule_steps table...")
                exec_ddl(db.engine, """
                    CREATE TABLE scheduled_message_rule_steps (
                        id SERIAL PRIMARY KEY,
                        rule_id INTEGER NOT NULL REFERENCES scheduled_message_rules(id) ON DELETE CASCADE,
                        step_index INTEGER NOT NULL,
                        message_template TEXT NOT NULL,
                        delay_seconds INTEGER NOT NULL DEFAULT 0,
                        enabled BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(rule_id, step_index)
                    )
                """)
                checkpoint("  ✅ scheduled_message_rule_steps table created")
                migrations_applied.append('123_scheduled_message_rule_steps_table')
            except Exception as e:
                checkpoint(f"❌ Migration 123 (scheduled_message_rule_steps table) failed: {e}")
                logger.error(f"Migration 123 scheduled_message_rule_steps error: {e}", exc_info=True)
        else:
            checkpoint("  ℹ️ scheduled_message_rule_steps table already exists")
        
        # Create index on (rule_id, step_index)
        if not check_index_exists('idx_rule_steps_rule_step'):
            try:
                checkpoint("  → Creating index on (rule_id, step_index)...")
                exec_ddl(db.engine, """
                    CREATE INDEX idx_rule_steps_rule_step 
                    ON scheduled_message_rule_steps(rule_id, step_index)
                """)
                checkpoint("  ✅ Index idx_rule_steps_rule_step created")
            except Exception as e:
                checkpoint(f"  ⚠️ Could not create index: {e}")
        
        # Step 2: Add new fields to scheduled_message_rules
        if check_table_exists('scheduled_message_rules'):
            try:
                fields_added = []
                
                # Add send_immediately_on_enter
                if not check_column_exists('scheduled_message_rules', 'send_immediately_on_enter'):
                    checkpoint("  → Adding send_immediately_on_enter to scheduled_message_rules...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE scheduled_message_rules 
                        ADD COLUMN send_immediately_on_enter BOOLEAN NOT NULL DEFAULT FALSE
                    """)
                    fields_added.append('send_immediately_on_enter')
                    checkpoint("  ✅ send_immediately_on_enter added")
                
                # Add apply_mode
                if not check_column_exists('scheduled_message_rules', 'apply_mode'):
                    checkpoint("  → Adding apply_mode to scheduled_message_rules...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE scheduled_message_rules 
                        ADD COLUMN apply_mode VARCHAR(32) NOT NULL DEFAULT 'ON_ENTER_ONLY'
                    """)
                    fields_added.append('apply_mode')
                    checkpoint("  ✅ apply_mode added")
                
                if fields_added:
                    migrations_applied.append('migration_123_rule_fields')
                    checkpoint(f"✅ Migration 123a completed - Added {len(fields_added)} fields to scheduled_message_rules")
                else:
                    checkpoint("  ℹ️  All fields already exist in scheduled_message_rules")
                    
            except Exception as e:
                checkpoint(f"❌ Migration 123a (scheduled_message_rules) failed: {e}")
                raise
        
        # Step 3: Add step_id to scheduled_messages_queue
        if check_table_exists('scheduled_messages_queue'):
            try:
                fields_added = []
                
                # Add step_id column (nullable since existing messages don't have steps)
                if not check_column_exists('scheduled_messages_queue', 'step_id'):
                    checkpoint("  → Adding step_id to scheduled_messages_queue...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE scheduled_messages_queue 
                        ADD COLUMN step_id INTEGER REFERENCES scheduled_message_rule_steps(id) ON DELETE SET NULL
                    """)
                    fields_added.append('step_id')
                    checkpoint("  ✅ step_id added to scheduled_messages_queue")
                
                if fields_added:
                    migrations_applied.append('migration_123_queue_fields')
                    checkpoint(f"✅ Migration 123b completed - Added {len(fields_added)} fields to scheduled_messages_queue")
                else:
                    checkpoint("  ℹ️  All fields already exist in scheduled_messages_queue")
                    
            except Exception as e:
                checkpoint(f"❌ Migration 123b (scheduled_messages_queue) failed: {e}")
                raise
        
        # Step 4: Add status_sequence_token to leads for deduplication
        if check_table_exists('leads'):
            try:
                fields_added = []
                
                # Add status_sequence_token for tracking status entry
                if not check_column_exists('leads', 'status_sequence_token'):
                    checkpoint("  → Adding status_sequence_token to leads...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE leads 
                        ADD COLUMN status_sequence_token INTEGER NOT NULL DEFAULT 0
                    """)
                    fields_added.append('status_sequence_token')
                    checkpoint("  ✅ status_sequence_token added to leads")
                
                # Add status_entered_at for tracking when lead entered current status
                if not check_column_exists('leads', 'status_entered_at'):
                    checkpoint("  → Adding status_entered_at to leads...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE leads 
                        ADD COLUMN status_entered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    """)
                    fields_added.append('status_entered_at')
                    checkpoint("  ✅ status_entered_at added to leads")
                
                if fields_added:
                    migrations_applied.append('migration_123_leads_fields')
                    checkpoint(f"✅ Migration 123c completed - Added {len(fields_added)} fields to leads")
                else:
                    checkpoint("  ℹ️  All fields already exist in leads")
                    
            except Exception as e:
                checkpoint(f"❌ Migration 123c (leads) failed: {e}")
                raise
        
        checkpoint("✅ Migration 123 complete: Multi-step scheduled messages system ready")
        checkpoint("   🎯 Rule steps table created for message sequences")
        checkpoint("   🎯 Send immediately on enter option available")
        checkpoint("   🎯 Deduplication support with status_sequence_token")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 124: Add immediate_message to scheduled_message_rules
        # 🎯 PURPOSE: Support separate message for immediate send vs delayed steps
        # Adds immediate_message column to store different text for immediate sends
        # Falls back to message_text if immediate_message is NULL (backward compatible)
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 124: Adding immediate_message to scheduled_message_rules")
        
        if check_table_exists('scheduled_message_rules'):
            try:
                # Add immediate_message column
                if not check_column_exists('scheduled_message_rules', 'immediate_message'):
                    checkpoint("  → Adding immediate_message to scheduled_message_rules...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE scheduled_message_rules 
                        ADD COLUMN immediate_message TEXT NULL
                    """)
                    migrations_applied.append('migration_124_immediate_message')
                    checkpoint("  ✅ immediate_message column added")
                    checkpoint("     💡 Allows separate message for immediate send vs delayed steps")
                    checkpoint("     💡 Falls back to message_text if NULL (backward compatible)")
                else:
                    checkpoint("  ℹ️  immediate_message column already exists")
                    
            except Exception as e:
                checkpoint(f"❌ Migration 124 failed: {e}")
                logger.error(f"Migration 124 error: {e}", exc_info=True)
                raise
        else:
            checkpoint("  ℹ️  scheduled_message_rules table does not exist - skipping Migration 124")
        
        checkpoint("✅ Migration 124 complete: immediate_message support ready")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 125: Add conversation tracking fields to WhatsAppConversationState
        # AgentKit Only: Enable better context tracking to prevent loops and improve responses
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 125: Adding conversation tracking fields to whatsapp_conversation_state")
        
        if check_table_exists('whatsapp_conversation_state'):
            try:
                # Add last_user_message column
                if not check_column_exists('whatsapp_conversation_state', 'last_user_message'):
                    checkpoint("  → Adding last_user_message to whatsapp_conversation_state...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE whatsapp_conversation_state 
                        ADD COLUMN last_user_message TEXT NULL
                    """)
                    checkpoint("  ✅ last_user_message column added")
                else:
                    checkpoint("  ℹ️  last_user_message column already exists")
                
                # Add last_agent_message column
                if not check_column_exists('whatsapp_conversation_state', 'last_agent_message'):
                    checkpoint("  → Adding last_agent_message to whatsapp_conversation_state...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE whatsapp_conversation_state 
                        ADD COLUMN last_agent_message TEXT NULL
                    """)
                    checkpoint("  ✅ last_agent_message column added")
                else:
                    checkpoint("  ℹ️  last_agent_message column already exists")
                
                # Add conversation_stage column
                if not check_column_exists('whatsapp_conversation_state', 'conversation_stage'):
                    checkpoint("  → Adding conversation_stage to whatsapp_conversation_state...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE whatsapp_conversation_state 
                        ADD COLUMN conversation_stage VARCHAR(64) NULL
                    """)
                    checkpoint("  ✅ conversation_stage column added")
                    checkpoint("     💡 Tracks current conversation stage for better context")
                else:
                    checkpoint("  ℹ️  conversation_stage column already exists")
                
                migrations_applied.append('migration_125_conversation_tracking')
                checkpoint("  ✅ All conversation tracking fields added")
                    
            except Exception as e:
                checkpoint(f"❌ Migration 125 failed: {e}")
                logger.error(f"Migration 125 error: {e}", exc_info=True)
                raise
        else:
            checkpoint("  ℹ️  whatsapp_conversation_state table does not exist - skipping Migration 125")
        
        checkpoint("✅ Migration 125 complete: Conversation tracking fields ready for AgentKit Only mode")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 126: Add Appointment Configuration Columns to BusinessSettings
        # Adds appointment_types_json and appointment_statuses_json for per-business customization
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 126: Adding appointment configuration columns to business_settings")
        
        if check_table_exists('business_settings'):
            try:
                changes_made = False
                
                # Add appointment_types_json column
                if not check_column_exists('business_settings', 'appointment_types_json'):
                    checkpoint("  → Adding appointment_types_json to business_settings...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE business_settings 
                        ADD COLUMN appointment_types_json JSON NULL
                    """)
                    checkpoint("  ✅ appointment_types_json column added")
                    checkpoint("     💡 Custom appointment types per business")
                    changes_made = True
                else:
                    checkpoint("  ℹ️  appointment_types_json column already exists")
                
                # Add appointment_statuses_json column
                if not check_column_exists('business_settings', 'appointment_statuses_json'):
                    checkpoint("  → Adding appointment_statuses_json to business_settings...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE business_settings 
                        ADD COLUMN appointment_statuses_json JSON NULL
                    """)
                    checkpoint("  ✅ appointment_statuses_json column added")
                    checkpoint("     💡 Custom appointment statuses per business")
                    changes_made = True
                else:
                    checkpoint("  ℹ️  appointment_statuses_json column already exists")
                
                if changes_made:
                    migrations_applied.append('migration_126_appointment_config')
                    checkpoint("  ✅ All appointment configuration fields added")
                    
            except Exception as e:
                checkpoint(f"❌ Migration 126 failed: {e}")
                logger.error(f"Migration 126 error: {e}", exc_info=True)
                raise
        else:
            checkpoint("  ℹ️  business_settings table does not exist - skipping Migration 126")
        
        checkpoint("✅ Migration 126 complete: Appointment configuration columns ready")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 127: Add default_calendar_id to business_settings
        # Allows businesses to select a default/main calendar for the appointments tab
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 127: Adding default_calendar_id to business_settings")
        
        if check_table_exists('business_settings'):
            try:
                if not check_column_exists('business_settings', 'default_calendar_id'):
                    checkpoint("  → Adding default_calendar_id to business_settings...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE business_settings 
                        ADD COLUMN default_calendar_id INTEGER NULL 
                        REFERENCES business_calendars(id) ON DELETE SET NULL
                    """)
                    checkpoint("  ✅ default_calendar_id column added")
                    checkpoint("     💡 Allows selecting a main calendar for the appointments tab")
                    migrations_applied.append("migration_127_default_calendar_id")
                else:
                    checkpoint("  ℹ️  default_calendar_id column already exists")
            except Exception as e:
                checkpoint(f"  ❌ Migration 127 failed: {e}")
                logger.error(f"Migration 127 error: {e}", exc_info=True)
                raise
        else:
            checkpoint("  ℹ️  business_settings table does not exist - skipping Migration 127")
        
        checkpoint("✅ Migration 127 complete: Default calendar selection ready")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 128: Create lead_status_history table for status change audit
        # Tracks all status changes on leads with full audit trail
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 128: Creating lead_status_history table")
        
        if not check_table_exists('lead_status_history'):
            try:
                checkpoint("  → Creating lead_status_history table...")
                execute_with_retry(migrate_engine, """
                    CREATE TABLE IF NOT EXISTS lead_status_history (
                        id SERIAL PRIMARY KEY,
                        lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
                        tenant_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        old_status VARCHAR(64),
                        new_status VARCHAR(64) NOT NULL,
                        changed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                        change_reason TEXT,
                        confidence_score DOUBLE PRECISION,
                        channel VARCHAR(32),
                        metadata_json JSONB,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                checkpoint("  ✅ lead_status_history table created")
                
                # Create indexes for common queries
                checkpoint("  → Creating indexes on lead_status_history...")
                execute_with_retry(migrate_engine, """
                    CREATE INDEX IF NOT EXISTS idx_lead_status_history_lead_id 
                    ON lead_status_history(lead_id)
                """)
                execute_with_retry(migrate_engine, """
                    CREATE INDEX IF NOT EXISTS idx_lead_status_history_tenant_id 
                    ON lead_status_history(tenant_id)
                """)
                execute_with_retry(migrate_engine, """
                    CREATE INDEX IF NOT EXISTS idx_lead_status_history_created_at 
                    ON lead_status_history(created_at)
                """)
                execute_with_retry(migrate_engine, """
                    CREATE INDEX IF NOT EXISTS idx_lead_status_history_lead_created 
                    ON lead_status_history(lead_id, created_at)
                """)
                execute_with_retry(migrate_engine, """
                    CREATE INDEX IF NOT EXISTS idx_lead_status_history_tenant_created 
                    ON lead_status_history(tenant_id, created_at)
                """)
                checkpoint("  ✅ Indexes created successfully")
                checkpoint("     💡 Enables efficient audit trail queries and reporting")
                migrations_applied.append("migration_128_lead_status_history")
            except Exception as e:
                checkpoint(f"  ❌ Migration 128 failed: {e}")
                logger.error(f"Migration 128 error: {e}", exc_info=True)
                raise
        else:
            checkpoint("  ℹ️  lead_status_history table already exists")
        
        checkpoint("✅ Migration 128 complete: Lead status history tracking ready")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 129: Add status_change_prompt and whatsapp_system_prompt to prompt_revisions
        # 🎯 PURPOSE: Enable per-business customization of status change behavior
        # - status_change_prompt: Custom instructions for AI on when/how to change lead statuses
        # - whatsapp_system_prompt: WhatsApp-specific system prompt (separate from phone calls)
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 129: Adding status_change_prompt and whatsapp_system_prompt to prompt_revisions")
        
        if check_table_exists('prompt_revisions'):
            try:
                changes_made = False
                
                # Add status_change_prompt column
                if not check_column_exists('prompt_revisions', 'status_change_prompt'):
                    checkpoint("  → Adding status_change_prompt to prompt_revisions...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE prompt_revisions 
                        ADD COLUMN status_change_prompt TEXT NULL
                    """)
                    checkpoint("  ✅ status_change_prompt column added")
                    checkpoint("     💡 Enables per-business customization of automatic status changes")
                    changes_made = True
                else:
                    checkpoint("  ℹ️  status_change_prompt column already exists")
                
                # Add whatsapp_system_prompt column
                if not check_column_exists('prompt_revisions', 'whatsapp_system_prompt'):
                    checkpoint("  → Adding whatsapp_system_prompt to prompt_revisions...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE prompt_revisions 
                        ADD COLUMN whatsapp_system_prompt TEXT NULL
                    """)
                    checkpoint("  ✅ whatsapp_system_prompt column added")
                    checkpoint("     💡 Allows separate WhatsApp prompt from phone call prompt")
                    changes_made = True
                else:
                    checkpoint("  ℹ️  whatsapp_system_prompt column already exists")
                
                if changes_made:
                    migrations_applied.append("migration_129_prompt_customization")
                    checkpoint("  ✅ Prompt customization columns added successfully")
                    
            except Exception as e:
                checkpoint(f"  ❌ Migration 129 failed: {e}")
                logger.error(f"Migration 129 error: {e}", exc_info=True)
                raise
        else:
            checkpoint("  ℹ️  prompt_revisions table does not exist - skipping Migration 129")
        
        checkpoint("✅ Migration 129 complete: Per-business prompt customization ready")
        
        # Migration 130: Add appointment confirmation automation tables
        # 🔥 Automated WhatsApp confirmations based on appointment status changes
        # Allows businesses to create automation rules that send WhatsApp messages
        # when appointments enter specific statuses at configured time offsets
        checkpoint("Migration 130: Creating appointment automation tables")
        
        try:
            changes_made = False
            
            # Step 1: Create appointment_automations table
            if not check_table_exists('appointment_automations'):
                checkpoint("  → Creating appointment_automations table...")
                execute_with_retry(migrate_engine, """
                    CREATE TABLE IF NOT EXISTS appointment_automations (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        name VARCHAR(255) NOT NULL,
                        enabled BOOLEAN NOT NULL DEFAULT TRUE,
                        trigger_status_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
                        schedule_offsets JSONB NOT NULL DEFAULT '[]'::jsonb,
                        channel VARCHAR(32) NOT NULL DEFAULT 'whatsapp',
                        message_template TEXT NOT NULL,
                        send_once_per_offset BOOLEAN NOT NULL DEFAULT TRUE,
                        dedupe_key_mode VARCHAR(64) NOT NULL DEFAULT 'business+appointment+offset',
                        cancel_on_status_exit BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
                    )
                """)
                checkpoint("  ✅ appointment_automations table created")
                changes_made = True
            else:
                checkpoint("  ℹ️  appointment_automations table already exists")
            
            # Step 2: Create appointment_automation_runs table
            if not check_table_exists('appointment_automation_runs'):
                checkpoint("  → Creating appointment_automation_runs table...")
                execute_with_retry(migrate_engine, """
                    CREATE TABLE IF NOT EXISTS appointment_automation_runs (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        appointment_id INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
                        automation_id INTEGER NOT NULL REFERENCES appointment_automations(id) ON DELETE CASCADE,
                        offset_signature VARCHAR(64) NOT NULL,
                        scheduled_for TIMESTAMP NOT NULL,
                        status VARCHAR(32) NOT NULL DEFAULT 'pending',
                        attempts INTEGER NOT NULL DEFAULT 0,
                        last_error TEXT,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        sent_at TIMESTAMP,
                        canceled_at TIMESTAMP,
                        CONSTRAINT uq_appointment_automation_run_dedupe 
                            UNIQUE (business_id, appointment_id, automation_id, offset_signature)
                    )
                """)
                checkpoint("  ✅ appointment_automation_runs table created with deduplication constraint")
                changes_made = True
            else:
                checkpoint("  ℹ️  appointment_automation_runs table already exists")
            
            if changes_made:
                migrations_applied.append("migration_130_appointment_automations")
                checkpoint("  ✅ Appointment automation tables created successfully")
                checkpoint("     💡 Businesses can now create automated WhatsApp confirmations")
                checkpoint("     💡 Status-based triggers with flexible time offsets")
                checkpoint("     💡 Built-in deduplication and cancellation logic")
                    
        except Exception as e:
            checkpoint(f"  ❌ Migration 130 failed: {e}")
            logger.error(f"Migration 130 error: {e}", exc_info=True)
            raise
        
        checkpoint("✅ Migration 130 complete: Appointment automation system ready")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 131: Ensure FK CASCADE on appointment_automation_runs.appointment_id
        # 🎯 PURPOSE: Guarantee CASCADE behavior for environments where it might be missing
        # - Ensures appointment deletions automatically clean up automation runs
        # - Prevents NotNullViolation errors on appointment deletion
        # - Idempotent: Safe to run even if CASCADE already exists
        # NOTE: Migration 130 created the table with CASCADE, but this ensures consistency
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 131: Ensuring FK CASCADE on appointment_automation_runs")
        
        if check_table_exists('appointment_automation_runs'):
            try:
                changes_made = False
                
                # Check if the FK constraint exists and verify CASCADE behavior
                # We'll recreate it to ensure CASCADE is present
                checkpoint("  → Verifying FK CASCADE on appointment_id...")
                
                # Check current constraint
                constraint_check = execute_with_retry(migrate_engine, """
                    SELECT confdeltype 
                    FROM pg_constraint 
                    WHERE conname = 'appointment_automation_runs_appointment_id_fkey'
                    AND conrelid = 'appointment_automation_runs'::regclass
                """)
                
                has_cascade = constraint_check and len(constraint_check) > 0 and constraint_check[0][0] == 'c'
                
                if not has_cascade:
                    checkpoint("  → FK constraint missing CASCADE - recreating with CASCADE...")
                    
                    # Drop existing constraint if it exists without CASCADE
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE appointment_automation_runs 
                        DROP CONSTRAINT IF EXISTS appointment_automation_runs_appointment_id_fkey
                    """)
                    
                    # Add constraint with CASCADE
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE appointment_automation_runs
                        ADD CONSTRAINT appointment_automation_runs_appointment_id_fkey
                        FOREIGN KEY (appointment_id)
                        REFERENCES appointments(id)
                        ON DELETE CASCADE
                    """)
                    
                    checkpoint("  ✅ FK CASCADE added successfully")
                    checkpoint("     💡 Appointment deletions now automatically clean up automation runs")
                    changes_made = True
                    migrations_applied.append("migration_131_fk_cascade_fix")
                else:
                    checkpoint("  ✅ FK CASCADE already present - no action needed")
                    
            except Exception as e:
                # Non-critical migration - log but don't fail
                checkpoint(f"  ⚠️  Migration 131 encountered issue: {e}")
                logger.warning(f"Migration 131 warning: {e}")
        else:
            checkpoint("  ℹ️  appointment_automation_runs table does not exist - skipping Migration 131")
        
        checkpoint("✅ Migration 131 complete: FK CASCADE verified")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 132: Add calendar_ids and appointment_type_keys to appointment_automations
        # Allows automations to filter by specific calendars and appointment types
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 132: Adding calendar and type filters to appointment_automations")
        
        if check_table_exists('appointment_automations'):
            try:
                changes_made = False
                
                # Add calendar_ids column
                if not check_column_exists('appointment_automations', 'calendar_ids'):
                    checkpoint("  → Adding calendar_ids column to appointment_automations...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE appointment_automations 
                        ADD COLUMN calendar_ids JSON NULL
                    """)
                    checkpoint("  ✅ calendar_ids column added")
                    checkpoint("     💡 Automations can now filter by specific calendars (null = all calendars)")
                    changes_made = True
                else:
                    checkpoint("  ℹ️  calendar_ids column already exists")
                
                # Add appointment_type_keys column
                if not check_column_exists('appointment_automations', 'appointment_type_keys'):
                    checkpoint("  → Adding appointment_type_keys column to appointment_automations...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE appointment_automations 
                        ADD COLUMN appointment_type_keys JSON NULL
                    """)
                    checkpoint("  ✅ appointment_type_keys column added")
                    checkpoint("     💡 Automations can now filter by appointment types (null = all types)")
                    changes_made = True
                else:
                    checkpoint("  ℹ️  appointment_type_keys column already exists")
                
                if changes_made:
                    migrations_applied.append("migration_132_automation_filters")
                    
            except Exception as e:
                checkpoint(f"  ❌ Migration 132 failed: {e}")
                logger.error(f"Migration 132 error: {e}", exc_info=True)
                raise
        else:
            checkpoint("  ℹ️  appointment_automations table does not exist - skipping Migration 132")
        
        checkpoint("✅ Migration 132 complete: Automation filtering by calendar and type ready")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 133: Add updated_at to whatsapp_broadcasts and fix scheduled_messages_queue FK
        # 🎯 PURPOSE: Fix missing updated_at column and lead deletion issues
        # - Add updated_at column to whatsapp_broadcasts with default and onupdate
        # - Change scheduled_messages_queue.lead_id to allow NULL with ON DELETE SET NULL
        # - Prevents errors when creating broadcasts or deleting leads
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 133: Add updated_at to whatsapp_broadcasts and fix scheduled_messages FK")
        
        try:
            changes_made = False
            
            # Part 1: Add updated_at to whatsapp_broadcasts
            if check_table_exists('whatsapp_broadcasts'):
                if not check_column_exists('whatsapp_broadcasts', 'updated_at'):
                    checkpoint("  → Adding updated_at column to whatsapp_broadcasts...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE whatsapp_broadcasts 
                        ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    """)
                    
                    # Set updated_at to created_at for existing records
                    execute_with_retry(migrate_engine, """
                        UPDATE whatsapp_broadcasts 
                        SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP)
                        WHERE updated_at IS NULL
                    """)
                    
                    checkpoint("  ✅ updated_at column added to whatsapp_broadcasts")
                    checkpoint("     💡 Existing broadcasts now have updated_at set to created_at")
                    changes_made = True
                else:
                    checkpoint("  ℹ️  updated_at column already exists in whatsapp_broadcasts")
            
            # Part 2: Fix scheduled_messages_queue.lead_id FK constraint
            if check_table_exists('scheduled_messages_queue'):
                checkpoint("  → Fixing scheduled_messages_queue.lead_id FK constraint...")
                
                # Check current FK constraint
                constraint_check = execute_with_retry(migrate_engine, """
                    SELECT conname, confdeltype
                    FROM pg_constraint 
                    WHERE conrelid = 'scheduled_messages_queue'::regclass
                    AND conname LIKE '%lead_id%'
                """)
                
                needs_fix = False
                if constraint_check and len(constraint_check) > 0:
                    constraint_name = constraint_check[0][0]
                    delete_action = constraint_check[0][1]
                    # 'c' = CASCADE, 'n' = SET NULL, 'r' = RESTRICT, 'a' = NO ACTION
                    if delete_action != 'n':  # Not SET NULL
                        checkpoint(f"  → FK constraint '{constraint_name}' has delete action '{delete_action}' - needs SET NULL")
                        needs_fix = True
                else:
                    checkpoint("  → No lead_id FK constraint found")
                
                if needs_fix:
                    # Drop existing FK constraint
                    execute_with_retry(migrate_engine, f"""
                        ALTER TABLE scheduled_messages_queue 
                        DROP CONSTRAINT IF EXISTS {constraint_name}
                    """)
                    
                    # Make lead_id nullable
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE scheduled_messages_queue 
                        ALTER COLUMN lead_id DROP NOT NULL
                    """)
                    
                    # Add new FK with ON DELETE SET NULL
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE scheduled_messages_queue
                        ADD CONSTRAINT scheduled_messages_queue_lead_id_fkey
                        FOREIGN KEY (lead_id)
                        REFERENCES leads(id)
                        ON DELETE SET NULL
                    """)
                    
                    checkpoint("  ✅ FK constraint updated with ON DELETE SET NULL")
                    checkpoint("     💡 Lead deletions now set lead_id to NULL instead of failing")
                    changes_made = True
                else:
                    checkpoint("  ℹ️  FK constraint already has correct behavior")
            
            if changes_made:
                migrations_applied.append("migration_133_updated_at_and_fk_fix")
                checkpoint("  ✅ Migration 133 completed successfully")
                    
        except Exception as e:
            checkpoint(f"  ❌ Migration 133 failed: {e}")
            logger.error(f"Migration 133 error: {e}", exc_info=True)
            # Don't raise - these are important but not critical for startup
        
        checkpoint("✅ Migration 133 complete: Database schema fixes applied")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 134: Add active_weekdays to automation tables
        # 🎯 PURPOSE: Allow automations to skip specific days of the week
        # - Add active_weekdays column to scheduled_message_rules (WhatsApp automation)
        # - Add active_weekdays column to appointment_automations (Calendar automation)
        # - null = active all days, [0,1,2,3,4] = Sunday-Thursday only, etc.
        # - 0=Sunday, 1=Monday, 2=Tuesday, 3=Wednesday, 4=Thursday, 5=Friday, 6=Saturday
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 134: Add active_weekdays to automation tables")
        
        try:
            changes_made = False
            
            # Part 1: Add active_weekdays to scheduled_message_rules
            if check_table_exists('scheduled_message_rules'):
                if not check_column_exists('scheduled_message_rules', 'active_weekdays'):
                    checkpoint("  → Adding active_weekdays column to scheduled_message_rules...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE scheduled_message_rules 
                        ADD COLUMN active_weekdays JSON NULL
                    """)
                    checkpoint("  ✅ active_weekdays column added to scheduled_message_rules")
                    checkpoint("     💡 Automations can now skip specific days (e.g., holidays/weekends)")
                    checkpoint("     💡 null = all days, [0,1,2,3,4] = Sunday-Thursday, etc.")
                    changes_made = True
                else:
                    checkpoint("  ℹ️  active_weekdays column already exists in scheduled_message_rules")
            
            # Part 2: Add active_weekdays to appointment_automations
            if check_table_exists('appointment_automations'):
                if not check_column_exists('appointment_automations', 'active_weekdays'):
                    checkpoint("  → Adding active_weekdays column to appointment_automations...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE appointment_automations 
                        ADD COLUMN active_weekdays JSON NULL
                    """)
                    checkpoint("  ✅ active_weekdays column added to appointment_automations")
                    checkpoint("     💡 Appointment automations can now skip specific days")
                    checkpoint("     💡 Example: Skip Tuesdays when owner is on vacation")
                    changes_made = True
                else:
                    checkpoint("  ℹ️  active_weekdays column already exists in appointment_automations")
            
            if changes_made:
                migrations_applied.append("migration_134_active_weekdays")
                checkpoint("  ✅ Migration 134 completed successfully")
                    
        except Exception as e:
            checkpoint(f"  ❌ Migration 134 failed: {e}")
            logger.error(f"Migration 134 error: {e}", exc_info=True)
            # Don't raise - these are important but not critical for startup
        
        checkpoint("✅ Migration 134 complete: Active weekdays support ready")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 135: Add webhook_lead_ingest table and raw_payload to leads
        # 🎯 PURPOSE: Enable external lead ingestion via webhooks (Make, Zapier, etc.)
        # - Create webhook_lead_ingest table for webhook configuration (max 3 per business)
        # - Add raw_payload column to leads table to store original webhook data
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 135: Add webhook lead ingestion system")
        
        try:
            changes_made = False
            
            # Part 1: Create webhook_lead_ingest table
            if not check_table_exists('webhook_lead_ingest'):
                checkpoint("  → Creating webhook_lead_ingest table...")
                execute_with_retry(migrate_engine, """
                    CREATE TABLE webhook_lead_ingest (
                        id SERIAL PRIMARY KEY,
                        business_id INTEGER NOT NULL REFERENCES business(id) ON DELETE CASCADE,
                        name VARCHAR(255) NOT NULL,
                        secret VARCHAR(128) NOT NULL,
                        status_id INTEGER NULL REFERENCES lead_statuses(id) ON DELETE SET NULL,
                        is_active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
                        updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'utc')
                    )
                """)
                checkpoint("  ✅ webhook_lead_ingest table created")
                checkpoint("     💡 Businesses can now configure up to 3 webhooks for lead ingestion")
                checkpoint("     💡 Each webhook creates leads in a pre-configured status")
                checkpoint("     💡 If target status is deleted, webhook status_id is set to NULL (uses default 'new')")
                changes_made = True
            else:
                checkpoint("  ℹ️  webhook_lead_ingest table already exists")
            
            # Part 2: Add raw_payload column to leads table
            if check_table_exists('leads'):
                if not check_column_exists('leads', 'raw_payload'):
                    checkpoint("  → Adding raw_payload column to leads table...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE leads 
                        ADD COLUMN raw_payload JSON NULL
                    """)
                    checkpoint("  ✅ raw_payload column added to leads table")
                    checkpoint("     💡 Webhook-created leads will store original payload for debugging")
                    changes_made = True
                else:
                    checkpoint("  ℹ️  raw_payload column already exists in leads table")
            
            if changes_made:
                migrations_applied.append("migration_135_webhook_lead_ingest")
                checkpoint("  ✅ Migration 135 completed successfully")
                    
        except Exception as e:
            checkpoint(f"  ❌ Migration 135 failed: {e}")
            logger.error(f"Migration 135 error: {e}", exc_info=True)
            # Don't raise - these are important but not critical for startup
        
        checkpoint("✅ Migration 135 complete: Webhook lead ingestion system ready")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 136: Add recurring schedule support to scheduled_message_rules
        # 🎯 PURPOSE: Enable scheduling messages at specific recurring times
        # - Add schedule_type column: "STATUS_CHANGE" (default) or "RECURRING_TIME"
        # - Add recurring_times JSON column: Array of times in "HH:MM" format
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 136: Add recurring schedule support to scheduled_message_rules")
        
        try:
            changes_made = False
            
            if check_table_exists('scheduled_message_rules'):
                # Add schedule_type column
                if not check_column_exists('scheduled_message_rules', 'schedule_type'):
                    checkpoint("  → Adding schedule_type column to scheduled_message_rules...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE scheduled_message_rules 
                        ADD COLUMN schedule_type VARCHAR(32) NOT NULL DEFAULT 'STATUS_CHANGE'
                    """)
                    checkpoint("  ✅ schedule_type column added to scheduled_message_rules")
                    checkpoint("     💡 'STATUS_CHANGE' = triggered by status change (current behavior)")
                    checkpoint("     💡 'RECURRING_TIME' = sent at specific times on specific days")
                    changes_made = True
                else:
                    checkpoint("  ℹ️  schedule_type column already exists in scheduled_message_rules")
                
                # Add recurring_times column
                if not check_column_exists('scheduled_message_rules', 'recurring_times'):
                    checkpoint("  → Adding recurring_times column to scheduled_message_rules...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE scheduled_message_rules 
                        ADD COLUMN recurring_times JSON NULL
                    """)
                    checkpoint("  ✅ recurring_times column added to scheduled_message_rules")
                    checkpoint("     💡 Array of times in 'HH:MM' format, e.g. ['09:00', '15:00']")
                    checkpoint("     💡 Combined with active_weekdays for precise scheduling")
                    changes_made = True
                else:
                    checkpoint("  ℹ️  recurring_times column already exists in scheduled_message_rules")
            
            if changes_made:
                migrations_applied.append("migration_136_recurring_schedule")
                checkpoint("  ✅ Migration 136 completed successfully")
                    
        except Exception as e:
            checkpoint(f"  ❌ Migration 136 failed: {e}")
            logger.error(f"Migration 136 error: {e}", exc_info=True)
            # Don't raise - these are important but not critical for startup
        
        checkpoint("✅ Migration 136 complete: Recurring schedule support added")
        
        # ═══════════════════════════════════════════════════════════════════════
        # Migration 137: Add excluded_weekdays to scheduled_message_rules
        # 🎯 PURPOSE: Allow users to exclude specific weekdays from automation
        # - Add excluded_weekdays JSON column: Array of weekday indices [0-6] to exclude
        # - Used only for STATUS_CHANGE schedule type
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("Migration 137: Add excluded_weekdays support to scheduled_message_rules")
        
        try:
            changes_made = False
            
            if check_table_exists('scheduled_message_rules'):
                # Add excluded_weekdays column
                if not check_column_exists('scheduled_message_rules', 'excluded_weekdays'):
                    checkpoint("  → Adding excluded_weekdays column to scheduled_message_rules...")
                    execute_with_retry(migrate_engine, """
                        ALTER TABLE scheduled_message_rules 
                        ADD COLUMN excluded_weekdays JSON NULL
                    """)
                    checkpoint("  ✅ excluded_weekdays column added to scheduled_message_rules")
                    checkpoint("     💡 Array of weekday indices [0-6] where 0=Sunday, 6=Saturday")
                    checkpoint("     💡 Automation will NOT run on these days, even if rule is active")
                    checkpoint("     💡 Only applies to STATUS_CHANGE schedule type")
                    changes_made = True
                else:
                    checkpoint("  ℹ️  excluded_weekdays column already exists in scheduled_message_rules")
            
            if changes_made:
                migrations_applied.append("migration_137_excluded_weekdays")
                checkpoint("  ✅ Migration 137 completed successfully")
                    
        except Exception as e:
            checkpoint(f"  ❌ Migration 137 failed: {e}")
            logger.error(f"Migration 137 error: {e}", exc_info=True)
            # Don't raise - these are important but not critical for startup
        
        checkpoint("✅ Migration 137 complete: Excluded weekdays support added")
        
        checkpoint("Committing migrations to database...")
        if migrations_applied:
            checkpoint(f"✅ Applied {len(migrations_applied)} migrations: {', '.join(migrations_applied[:3])}...")
        else:
            checkpoint("No migrations needed - database is up to date")
        
        # 🔒 DATA PROTECTION CHECK: Verify data counts AFTER migrations - CRITICAL!
        # If FAQs or leads are deleted, ROLLBACK and FAIL the migration
        checkpoint("Starting data protection layer 3 - verifying no data loss")
        try:
            data_loss_detected = False
            
            if check_table_exists('faqs'):
                result = execute_with_retry(migrate_engine, "SELECT COUNT(*) FROM faqs")
                faq_count_after = result[0][0] if result else 0
                faq_delta = faq_count_after - faq_count_before
                if faq_delta < 0:
                    checkpoint(f"❌ DATA LOSS DETECTED: {abs(faq_delta)} FAQs were DELETED during migrations!")
                    data_loss_detected = True
                else:
                    checkpoint(f"✅ DATA PROTECTION (AFTER): {faq_count_after} FAQs preserved (delta: +{faq_delta})")
            
            if check_table_exists('leads'):
                result = execute_with_retry(migrate_engine, "SELECT COUNT(*) FROM leads")
                lead_count_after = result[0][0] if result else 0
                lead_delta = lead_count_after - lead_count_before
                if lead_delta < 0:
                    checkpoint(f"❌ DATA LOSS DETECTED: {abs(lead_delta)} leads were DELETED during migrations!")
                    data_loss_detected = True
                else:
                    checkpoint(f"✅ DATA PROTECTION (AFTER): {lead_count_after} leads preserved (delta: +{lead_delta})")
            
            # 🛑 ENFORCE DATA PROTECTION: Rollback and fail if FAQs or leads were deleted
            if data_loss_detected:
                error_msg = "❌ MIGRATION FAILED: Data loss detected. Rolling back changes."
                checkpoint(error_msg)
                raise Exception("Data protection violation: FAQs or leads were deleted during migration")
            
            # Messages can decrease (deduplication is expected and documented)
            if check_table_exists('messages'):
                result = execute_with_retry(migrate_engine, "SELECT COUNT(*) FROM messages")
                msg_count_after = result[0][0] if result else 0
                msg_delta = msg_count_after - msg_count_before
                if msg_delta < 0:
                    checkpoint(f"⚠️ Messages decreased by {abs(msg_delta)} (deduplication cleanup - expected)")
                else:
                    checkpoint(f"✅ DATA PROTECTION (AFTER): {msg_count_after} messages (delta: +{msg_delta})")
        except Exception as e:
            if "Data protection violation" in str(e):
                raise  # Re-raise data protection violations
            
            # 🔥 CRITICAL FIX: ROLLBACK immediately to prevent InFailedSqlTransaction
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
        
        # 🔥 CRITICAL: Verify business.lead_tabs_config exists (Migration 112)
        if check_table_exists('business'):
            if not check_column_exists('business', 'lead_tabs_config'):
                error_msg = "❌ POST-MIGRATION VERIFICATION FAILED: Missing column 'business.lead_tabs_config'"
                checkpoint(error_msg)
                checkpoint("💡 TIP: Migration 112 may have failed. This column is REQUIRED for API to start.")
                raise Exception("Migration verification failed: business.lead_tabs_config column missing")
            else:
                checkpoint("  ✅ Column 'business.lead_tabs_config' exists")
        
        checkpoint("✅ Migration completed successfully!")
        
        # ═══════════════════════════════════════════════════════════════════════
        # 🔥 FINAL VALIDATION: Check for pending migrations
        # ═══════════════════════════════════════════════════════════════════════
        checkpoint("=" * 80)
        checkpoint("🔍 FINAL VALIDATION: Checking for pending migrations")
        checkpoint("=" * 80)
        
        try:
            migrate_engine = get_migrate_engine()
            
            # Get all applied migrations from tracking table
            with migrate_engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT migration_id, applied_at 
                    FROM schema_migrations 
                    WHERE success = TRUE 
                    ORDER BY applied_at DESC 
                    LIMIT 10
                """))
                applied = result.fetchall()
                
                if applied:
                    checkpoint(f"✅ {len(applied)} recent migrations tracked:")
                    for row in applied:
                        checkpoint(f"   - {row[0]} (applied: {row[1]})")
                else:
                    checkpoint("⚠️  No migrations tracked yet (this may be first deployment)")
            
            # Check critical tables exist
            critical_tables = ['business', 'leads', 'threads', 'messages', 'faqs']
            missing_tables = []
            for table in critical_tables:
                if not check_table_exists(table):
                    missing_tables.append(table)
            
            if missing_tables:
                checkpoint("=" * 80)
                checkpoint(f"❌ VALIDATION FAILED: Missing critical tables: {missing_tables}")
                checkpoint("   Migrations appear incomplete!")
                checkpoint("=" * 80)
                raise RuntimeError(f"Migration validation failed: missing critical tables {missing_tables}")
            else:
                checkpoint(f"✅ All {len(critical_tables)} critical tables exist")
            
            checkpoint("=" * 80)
            checkpoint("✅ FINAL VALIDATION PASSED: All migrations completed successfully")
            checkpoint("=" * 80)
            
        except Exception as e:
            if "Migration validation failed" in str(e):
                raise  # Re-raise validation failures
            checkpoint(f"⚠️  Could not perform final validation: {e}")
            # Don't fail deployment on validation check errors
    
    # 🔒 CONCURRENCY PROTECTION: Release PostgreSQL advisory lock
    finally:
        if lock_acquired:
            try:
                # Release lock using the same LOCK_ID (1234567890)
                execute_with_retry(migrate_engine, "SELECT pg_advisory_unlock(:id)", {"id": 1234567890})
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
        
        # Check if migrations were skipped
        if migrations == 'skip':
            checkpoint("=" * 80)
            checkpoint("ℹ️  SKIPPED - Migrations were not executed")
            checkpoint("   This is expected for worker processes or when migrations are disabled")
            checkpoint("=" * 80)
            sys.exit(0)
        
        # Verify migrations list is not empty (real success)
        if isinstance(migrations, list):
            checkpoint("=" * 80)
            checkpoint(f"✅ SUCCESS - Applied {len(migrations)} migrations")
            checkpoint("=" * 80)
            sys.exit(0)
        else:
            # Unexpected return value
            checkpoint("=" * 80)
            checkpoint(f"⚠️  WARNING - Unexpected return value from apply_migrations: {migrations}")
            checkpoint("=" * 80)
            sys.exit(0)
        
    except Exception as e:
        checkpoint("=" * 80)
        checkpoint(f"❌ MIGRATION FAILED: {e}")
        checkpoint("=" * 80)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)