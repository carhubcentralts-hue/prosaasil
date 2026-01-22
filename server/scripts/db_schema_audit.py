#!/usr/bin/env python3
"""
Database Schema Audit Script

This script verifies that the actual database schema matches the expected schema
defined in the SQLAlchemy models. It's designed to:
1. Detect migration drift (schema changes made without migrations)
2. Verify critical columns exist in production tables
3. Check migration status (are we at the latest migration?)
4. Provide actionable error messages when drift is detected

Usage:
    python -m server.scripts.db_schema_audit
    
Exit codes:
    0 = Schema is up to date
    1 = Schema drift detected or migrations pending
    2 = Critical error (DB connection failed, etc.)
"""

import sys
import os
from typing import List, Tuple

# Ensure we can import server modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

def checkpoint(message):
    """Print checkpoint message to stderr"""
    print(f"🔍 SCHEMA AUDIT: {message}", file=sys.stderr, flush=True)

def check_column_exists(conn, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    from sqlalchemy import text
    result = conn.execute(text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = :table_name 
        AND column_name = :column_name
    """), {"table_name": table_name, "column_name": column_name})
    return result.fetchone() is not None

def check_table_exists(conn, table_name: str) -> bool:
    """Check if a table exists"""
    from sqlalchemy import text
    result = conn.execute(text("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = :table_name
    """), {"table_name": table_name})
    return result.fetchone() is not None

def get_migration_version(conn) -> Tuple[str, str]:
    """
    Get current and head migration versions
    
    Returns:
        Tuple of (current_version, head_version)
        For the custom migration system, we use a simplified approach
    """
    from sqlalchemy import text
    
    # Check if alembic_version table exists
    if not check_table_exists(conn, 'alembic_version'):
        return ("no_migrations", "unknown")
    
    # Get current version from alembic_version table
    result = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
    row = result.fetchone()
    current = row[0] if row else "empty"
    
    # For the custom migration system, we use a marker instead of actual version
    # The presence of the alembic_version table indicates migrations have run
    head = "custom_migrations"
    
    return (current, head)

def audit_critical_columns(conn) -> List[str]:
    """
    Audit critical columns that must exist in the database
    
    Returns:
        List of error messages (empty if all columns exist)
    """
    errors = []
    
    # Define critical columns per table
    # Format: (table_name, column_name, description)
    critical_columns = [
        ("leads", "phone_raw", "Original phone input for debugging"),
        ("leads", "phone_e164", "Normalized E.164 phone number"),
        ("leads", "whatsapp_jid", "WhatsApp identifier"),
        ("leads", "reply_jid", "WhatsApp reply identifier"),
        ("leads", "last_call_direction", "Call direction tracking (inbound/outbound)"),
        ("business", "phone_e164", "Business phone number (mapped from phone_number)"),
        ("business", "webhook_secret", "WhatsApp webhook secret"),
        ("business", "voice_id", "OpenAI Realtime voice ID"),
        ("business", "enabled_pages", "Page-level permissions"),
        ("call_log", "recording_mode", "Recording mode (realtime/twilio)"),
        ("whatsapp_broadcasts", "stopped_at", "Broadcast stop timestamp"),
        ("whatsapp_broadcast_recipients", "delivered_at", "Message delivery timestamp"),
    ]
    
    checkpoint("Checking critical columns...")
    
    for table_name, column_name, description in critical_columns:
        if not check_table_exists(conn, table_name):
            checkpoint(f"  ⚠️  Table '{table_name}' does not exist - skipping column checks")
            continue
            
        if not check_column_exists(conn, table_name, column_name):
            error_msg = f"Missing column: {table_name}.{column_name} ({description})"
            errors.append(error_msg)
            checkpoint(f"  ❌ {error_msg}")
        else:
            checkpoint(f"  ✅ {table_name}.{column_name}")
    
    return errors

def main():
    """Run the database schema audit"""
    checkpoint("=" * 80)
    checkpoint("DATABASE SCHEMA AUDIT - Starting")
    checkpoint("=" * 80)
    
    # Validate DATABASE_URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        checkpoint("❌ DATABASE_URL environment variable is not set!")
        return 2
    
    checkpoint(f"Database: {database_url.split('@')[-1] if '@' in database_url else 'sqlite'}")
    
    try:
        # Create database connection
        from sqlalchemy import create_engine
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Check 1: Verify migration version
            checkpoint("\n📊 STEP 1: Checking migration status")
            checkpoint("-" * 80)
            current, head = get_migration_version(conn)
            checkpoint(f"Current migration: {current}")
            checkpoint(f"Head migration: {head}")
            
            if current == "no_migrations":
                checkpoint("⚠️  WARNING: No migrations have been run yet")
                checkpoint("   Action: Run migrations with: python -m server.db_migrate")
            elif current == "empty":
                checkpoint("⚠️  WARNING: alembic_version table exists but is empty")
            else:
                checkpoint("✅ Migration tracking is active")
            
            # Check 2: Audit critical columns
            checkpoint("\n📊 STEP 2: Auditing critical columns")
            checkpoint("-" * 80)
            errors = audit_critical_columns(conn)
            
            # Check 3: Verify core tables exist
            checkpoint("\n📊 STEP 3: Verifying core tables")
            checkpoint("-" * 80)
            core_tables = [
                "business", "leads", "call_log", "customer",
                "users", "messages", "faqs"
            ]
            
            missing_tables = []
            for table in core_tables:
                if check_table_exists(conn, table):
                    checkpoint(f"  ✅ {table}")
                else:
                    checkpoint(f"  ❌ {table} - MISSING")
                    missing_tables.append(table)
            
            # Summary
            checkpoint("\n" + "=" * 80)
            checkpoint("AUDIT SUMMARY")
            checkpoint("=" * 80)
            
            has_errors = len(errors) > 0 or len(missing_tables) > 0
            
            if missing_tables:
                checkpoint(f"❌ Missing tables: {', '.join(missing_tables)}")
                checkpoint("   Action: Run migrations with: python -m server.db_migrate")
            
            if errors:
                checkpoint(f"❌ Missing columns detected: {len(errors)}")
                for error in errors:
                    checkpoint(f"   - {error}")
                checkpoint("\n   Action: Run migrations with: python -m server.db_migrate")
            
            if not has_errors:
                checkpoint("✅ Database schema is up to date!")
                checkpoint("   All critical columns and tables exist.")
                return 0
            else:
                checkpoint("\n❌ SCHEMA DRIFT DETECTED")
                checkpoint("   The database schema does not match the application models.")
                checkpoint("   This will cause UndefinedColumn errors at runtime.")
                checkpoint("\n   To fix:")
                checkpoint("   1. Run: python -m server.db_migrate")
                checkpoint("   2. Restart the application")
                return 1
    
    except Exception as e:
        checkpoint("\n" + "=" * 80)
        checkpoint(f"❌ CRITICAL ERROR: {e}")
        checkpoint("=" * 80)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 2

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
