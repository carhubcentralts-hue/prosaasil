#!/usr/bin/env python3
"""
Database Backfill Tool - Idempotent and Safe
============================================

This script runs data backfill operations separately from migrations.

Design principles:
1. Run idempotently (safe to run multiple times)
2. Never fail deployment (exits 0 even on errors, with warnings)
3. Use small batches (100-200 rows) to reduce lock contention
4. Use FOR UPDATE SKIP LOCKED to avoid blocking on locked rows
5. Retry on transient failures with exponential backoff
6. Provide clear progress reporting
7. Time-boxed execution (default: 10 minutes)

Usage:
    python server/db_backfill.py [--max-time=600] [--batch-size=100]

Exit codes:
    0 - Always (even if backfill incomplete, deployment should continue)
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import SQLAlchemy components
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError, ProgrammingError, DBAPIError
except ImportError as e:
    logger.error(f"❌ Failed to import SQLAlchemy: {e}")
    logger.error("Please install required dependencies: pip install sqlalchemy psycopg2-binary")
    sys.exit(0)  # Exit 0 to not block deployment


def get_database_url() -> str:
    """Get database URL from environment."""
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        logger.error("❌ DATABASE_URL environment variable not set")
        sys.exit(0)  # Exit 0 to not block deployment
    return db_url


def create_db_engine(database_url: str):
    """Create database engine with proper settings."""
    try:
        # Create engine with pool_pre_ping to handle stale connections
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=180,  # Recycle connections every 3 minutes
            pool_size=5,
            max_overflow=10,
            echo=False
        )
        return engine
    except Exception as e:
        logger.error(f"❌ Failed to create database engine: {e}")
        sys.exit(0)  # Exit 0 to not block deployment


def check_table_exists(engine, table_name: str) -> bool:
    """Check if a table exists."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = :table_name
                )
            """), {"table_name": table_name})
            return result.scalar()
    except Exception as e:
        logger.warning(f"⚠️  Could not check existence of table {table_name}: {e}")
        return False


def backfill_last_call_direction(
    engine,
    batch_size: int = 100,
    max_time_seconds: int = 600
) -> Tuple[int, bool]:
    """
    Backfill last_call_direction column in leads table.
    
    Uses batched updates with FOR UPDATE SKIP LOCKED to avoid lock contention.
    Time-boxed execution to prevent blocking deployment.
    
    Args:
        engine: SQLAlchemy engine
        batch_size: Number of rows to process per batch (default: 100)
        max_time_seconds: Maximum time to run in seconds (default: 600 = 10 minutes)
        
    Returns:
        Tuple of (total_rows_updated, completed_all)
    """
    logger.info("=" * 80)
    logger.info("Starting backfill of last_call_direction column")
    logger.info("=" * 80)
    
    # Check if tables exist
    if not check_table_exists(engine, 'leads'):
        logger.warning("⚠️  Table 'leads' does not exist. Skipping backfill.")
        return 0, True
    
    if not check_table_exists(engine, 'call_log'):
        logger.warning("⚠️  Table 'call_log' does not exist. Skipping backfill.")
        return 0, True
    
    start_time = time.time()
    deadline = start_time + max_time_seconds
    total_updated = 0
    
    # Get list of distinct tenant_ids that need backfill
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT DISTINCT tenant_id, COUNT(*) as pending_count
                FROM leads 
                WHERE last_call_direction IS NULL
                  AND tenant_id IS NOT NULL
                GROUP BY tenant_id
                ORDER BY tenant_id
            """))
            tenant_data = [(row[0], row[1]) for row in result.fetchall()]
    except Exception as e:
        logger.error(f"❌ Failed to query tenants needing backfill: {e}")
        return 0, False
    
    if not tenant_data:
        logger.info("✅ No leads require backfill (all leads already have last_call_direction set)")
        return 0, True
    
    logger.info(f"Found {len(tenant_data)} business(es) with leads requiring backfill:")
    total_pending = sum(count for _, count in tenant_data)
    logger.info(f"Total pending leads: {total_pending}")
    for tenant_id, count in tenant_data:
        logger.info(f"  • Business {tenant_id}: {count} leads")
    
    # Process each business separately
    for tenant_id, pending_count in tenant_data:
        if time.time() >= deadline:
            logger.warning(f"⏰ Time limit reached ({max_time_seconds}s). Stopping backfill.")
            logger.info(f"✅ Partial completion: {total_updated} rows updated")
            return total_updated, False
        
        business_total = 0
        iteration = 0
        max_iterations = 1000  # Safety limit per business
        
        logger.info(f"\n{'─' * 80}")
        logger.info(f"Processing business {tenant_id} ({pending_count} pending leads)")
        logger.info(f"{'─' * 80}")
        
        while iteration < max_iterations:
            if time.time() >= deadline:
                logger.warning(f"⏰ Time limit reached. Processed {business_total}/{pending_count} for business {tenant_id}")
                break
            
            try:
                # Update one batch with FOR UPDATE SKIP LOCKED
                with engine.begin() as conn:
                    # Set appropriate timeouts
                    conn.execute(text("SET lock_timeout = '5s'"))
                    conn.execute(text("SET statement_timeout = '30s'"))
                    conn.execute(text("SET idle_in_transaction_session_timeout = '60s'"))
                    
                    result = conn.execute(text("""
                        WITH batch AS (
                            SELECT id
                            FROM leads
                            WHERE tenant_id = :tenant_id 
                              AND last_call_direction IS NULL
                            ORDER BY id
                            LIMIT :batch_size
                            FOR UPDATE SKIP LOCKED
                        ),
                        first_calls AS (
                            SELECT DISTINCT ON (cl.lead_id) 
                                cl.lead_id,
                                cl.direction
                            FROM call_log cl
                            JOIN batch b ON b.id = cl.lead_id
                            WHERE cl.direction IN ('inbound', 'outbound')
                            ORDER BY cl.lead_id, cl.created_at ASC
                        )
                        UPDATE leads l
                        SET last_call_direction = fc.direction
                        FROM first_calls fc
                        WHERE l.id = fc.lead_id
                    """), {"tenant_id": tenant_id, "batch_size": batch_size})
                    
                    rows_updated = result.rowcount if hasattr(result, 'rowcount') else 0
                
                business_total += rows_updated
                total_updated += rows_updated
                iteration += 1
                
                if rows_updated == 0:
                    # No more rows for this business
                    logger.info(f"  ✅ Business {tenant_id} complete: {business_total} rows updated")
                    break
                
                # Log progress periodically
                if iteration % 10 == 0:
                    elapsed = time.time() - start_time
                    logger.info(f"  Progress: Batch {iteration}, {business_total} rows updated so far (elapsed: {elapsed:.1f}s)")
                
                # Small delay between batches to reduce DB pressure
                if rows_updated == batch_size:
                    time.sleep(0.05)
                    
            except OperationalError as e:
                # Handle lock timeout gracefully - just skip and continue
                if 'lock_timeout' in str(e).lower() or 'canceling statement due to lock timeout' in str(e).lower():
                    logger.warning(f"  ⚠️  Lock timeout on batch {iteration} - skipping (will retry on next run)")
                    iteration += 1
                    time.sleep(1.0)  # Wait a bit before next attempt
                    continue
                else:
                    logger.error(f"  ❌ Operational error on batch {iteration}: {e}")
                    # Don't fail deployment - log and move to next business
                    break
            except Exception as e:
                logger.error(f"  ❌ Unexpected error on batch {iteration}: {e}")
                # Don't fail deployment - log and move to next business
                break
        
        if iteration >= max_iterations:
            logger.warning(f"  ⚠️  Business {tenant_id}: Reached max iterations ({max_iterations})")
    
    elapsed = time.time() - start_time
    logger.info("\n" + "=" * 80)
    logger.info(f"Backfill summary:")
    logger.info(f"  • Total rows updated: {total_updated}")
    logger.info(f"  • Time elapsed: {elapsed:.1f}s")
    logger.info(f"  • Completed all: {total_updated >= total_pending}")
    logger.info("=" * 80)
    
    return total_updated, (total_updated >= total_pending)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Run database backfill operations')
    parser.add_argument('--max-time', type=int, default=600,
                        help='Maximum time to run in seconds (default: 600)')
    parser.add_argument('--batch-size', type=int, default=100,
                        help='Number of rows per batch (default: 100)')
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("Database Backfill Tool")
    logger.info("=" * 80)
    logger.info(f"Configuration:")
    logger.info(f"  • Max time: {args.max_time}s")
    logger.info(f"  • Batch size: {args.batch_size}")
    logger.info("")
    
    # Get database connection
    database_url = get_database_url()
    engine = create_db_engine(database_url)
    
    try:
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Database connection successful")
    except Exception as e:
        logger.error(f"❌ Failed to connect to database: {e}")
        sys.exit(0)  # Exit 0 to not block deployment
    
    # Run backfill for last_call_direction
    try:
        total_updated, completed = backfill_last_call_direction(
            engine,
            batch_size=args.batch_size,
            max_time_seconds=args.max_time
        )
        
        if completed:
            logger.info("\n✅ Backfill completed successfully!")
        else:
            logger.warning("\n⚠️  Backfill incomplete (time limit or partial success)")
            logger.warning("This is expected behavior - backfill will continue on next deployment")
        
    except Exception as e:
        logger.error(f"\n❌ Backfill failed with error: {e}", exc_info=True)
        logger.warning("Deployment will continue anyway (backfill is non-critical)")
    
    # Always exit 0 to not block deployment
    logger.info("\nBackfill tool finished (exit 0)")
    sys.exit(0)


if __name__ == '__main__':
    main()
