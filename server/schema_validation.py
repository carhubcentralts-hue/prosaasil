"""
Schema validation for receipt_sync_runs table

This module provides validation that runs at API startup to ensure
the receipt_sync_runs table has all required columns before any code tries to use them.

This prevents UndefinedColumn errors at runtime.
"""
import logging
from typing import List

logger = logging.getLogger(__name__)

# Required columns for receipt_sync_runs (matches Migration 89)
from server.db_migrate import MIGRATION_89_REQUIRED_COLUMNS


def validate_receipt_sync_schema(db) -> bool:
    """
    Validate that receipt_sync_runs table has all required columns.
    
    This runs at API startup to fail fast if schema is incomplete.
    
    Args:
        db: SQLAlchemy database instance
        
    Returns:
        True if validation passes
        
    Raises:
        RuntimeError if validation fails
    """
    from sqlalchemy import text, inspect
    
    logger.info("🔍 Validating receipt_sync_runs schema...")
    
    # Check if table exists
    inspector = inspect(db.engine)
    if 'receipt_sync_runs' not in inspector.get_table_names():
        logger.info("  ℹ️  receipt_sync_runs table doesn't exist yet - skipping validation")
        return True
    
    # Check all required columns exist
    missing_columns = []
    with db.engine.connect() as conn:
        for col in MIGRATION_89_REQUIRED_COLUMNS:
            result = conn.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'receipt_sync_runs' 
                AND column_name = :column_name
            """), {"column_name": col})
            
            if result.fetchone() is None:
                missing_columns.append(col)
                logger.error(f"  ❌ Missing column: receipt_sync_runs.{col}")
            else:
                logger.debug(f"  ✅ Column exists: receipt_sync_runs.{col}")
    
    if missing_columns:
        error_msg = (
            f"❌ CRITICAL: receipt_sync_runs table is missing required columns: {', '.join(missing_columns)}\n"
            f"   The ORM expects these columns but they don't exist in the database.\n"
            f"   This will cause 'UndefinedColumn' errors when syncing receipts.\n"
            f"   \n"
            f"   Run migrations to add missing columns:\n"
            f"     python -c 'from server.db_migrate import apply_migrations; apply_migrations()'\n"
        )
        logger.error("=" * 80)
        logger.error(error_msg)
        logger.error("=" * 80)
        raise RuntimeError(error_msg)
    
    logger.info("  ✅ receipt_sync_runs schema validation passed - all required columns exist")
    return True
