"""
Backfill Registry - Single Source of Truth for Data Backfills
==============================================================

This module defines all data backfill operations that must run separately from migrations.

DESIGN PRINCIPLES:
- Each backfill is idempotent (safe to run multiple times)
- Each backfill uses small batches with SKIP LOCKED
- Each backfill can be run independently
- Each backfill tracks its own progress
- Never fail deployment - always exit gracefully

REGISTRY STRUCTURE:
Each backfill definition contains:
- key: Unique identifier
- migration_number: Which migration added the schema
- description: What this backfill does
- tables: List of tables affected
- batch_size: Rows per batch (default: 100)
- max_runtime_seconds: Time limit (default: 600)
- priority: HIGH/MEDIUM/LOW
- safe_to_run_online: Whether it can run while services are up
- function: The actual backfill function
"""

from typing import List, Dict, Callable, Optional
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
import logging
import time

logger = logging.getLogger(__name__)


# ============================================================================
# BACKFILL FUNCTIONS
# ============================================================================

def backfill_last_call_direction(engine, batch_size=100, max_time_seconds=600):
    """
    Backfill last_call_direction for Migration 36.
    
    Sets last_call_direction on leads table based on the FIRST call
    from call_log table.
    """
    logger.info("=" * 80)
    logger.info("Backfill: last_call_direction (Migration 36)")
    logger.info("=" * 80)
    
    start_time = time.time()
    deadline = start_time + max_time_seconds
    total_updated = 0
    
    # Get tenants needing backfill
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
        logger.error(f"Failed to query tenants: {e}")
        return 0, False
    
    if not tenant_data:
        logger.info("✅ All leads already have last_call_direction")
        return 0, True
    
    logger.info(f"Found {len(tenant_data)} business(es) needing backfill")
    total_pending = sum(count for _, count in tenant_data)
    logger.info(f"Total pending leads: {total_pending}")
    
    # Process each business
    for tenant_id, pending_count in tenant_data:
        if time.time() >= deadline:
            logger.warning(f"⏰ Time limit reached. Processed {total_updated}/{total_pending}")
            return total_updated, False
        
        business_total = 0
        iteration = 0
        max_iterations = 1000
        
        logger.info(f"\nProcessing business {tenant_id} ({pending_count} pending)")
        
        while iteration < max_iterations:
            if time.time() >= deadline:
                break
            
            try:
                with engine.begin() as conn:
                    # POOLER-SAFE timeout policy for backfill operations
                    # These settings work well with connection poolers like Supabase
                    conn.execute(text("SET lock_timeout = '15s'"))  # Max wait for locks on POOLER
                    conn.execute(text("SET statement_timeout = '120s'"))  # Allow time for batch operations
                    conn.execute(text("SET idle_in_transaction_session_timeout = '120s'"))  # Prevent stuck transactions
                    
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
                    logger.info(f"  ✅ Business {tenant_id} complete: {business_total} rows")
                    break
                
                if iteration % 10 == 0:
                    logger.info(f"  Progress: {business_total} rows updated")
                
                if rows_updated == batch_size:
                    time.sleep(0.05)
                    
            except OperationalError as e:
                if 'lock_timeout' in str(e).lower():
                    logger.warning(f"  Lock timeout on batch {iteration} - skipping")
                    iteration += 1
                    time.sleep(1.0)
                    continue
                else:
                    logger.error(f"  Error on batch {iteration}: {e}")
                    break
            except Exception as e:
                logger.error(f"  Unexpected error: {e}")
                break
        
        if iteration >= max_iterations:
            logger.warning(f"  Max iterations reached for business {tenant_id}")
    
    elapsed = time.time() - start_time
    logger.info(f"\n✅ Backfill complete: {total_updated} rows in {elapsed:.1f}s")
    
    return total_updated, (total_updated >= total_pending)


def backfill_96_lead_name(engine, batch_size=200, max_time_seconds=600):
    """
    Backfill lead names for Migration 96.
    
    Migrates existing lead names from first_name/last_name to the unified name field.
    This is the DATA MIGRATION that was removed from migration 96.
    
    POOLER-SAFE:
    - Uses batches of 200 rows
    - FOR UPDATE SKIP LOCKED
    - Commits per batch
    - Retry logic for connection errors
    """
    logger.info("=" * 80)
    logger.info("Backfill: lead names (Migration 96)")
    logger.info("=" * 80)
    logger.info("Migrating first_name + last_name → name field")
    
    start_time = time.time()
    deadline = start_time + max_time_seconds
    total_updated = 0
    iteration = 0
    max_iterations = 10000  # Safety limit
    retry_count = 0
    max_retries_per_batch = 3  # Prevent infinite retry loop
    
    while iteration < max_iterations:
        if time.time() >= deadline:
            logger.warning(f"⏰ Time limit reached. Processed {total_updated} rows")
            return total_updated, False
        
        try:
            with engine.begin() as conn:
                # POOLER-SAFE timeout policy
                conn.execute(text("SET lock_timeout = '15s'"))
                conn.execute(text("SET statement_timeout = '120s'"))
                conn.execute(text("SET idle_in_transaction_session_timeout = '120s'"))
                
                # Batch update with SKIP LOCKED for POOLER safety
                result = conn.execute(text("""
                    WITH batch AS (
                        SELECT id
                        FROM leads
                        WHERE name IS NULL
                          AND (first_name IS NOT NULL OR last_name IS NOT NULL)
                        LIMIT :batch_size
                        FOR UPDATE SKIP LOCKED
                    )
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
                        name_updated_at = COALESCE(updated_at, NOW())
                    FROM batch
                    WHERE leads.id = batch.id
                """), {"batch_size": batch_size})
                
                rows_updated = result.rowcount if hasattr(result, 'rowcount') else 0
            
            # Success - reset retry count and move to next iteration
            retry_count = 0
            total_updated += rows_updated
            iteration += 1
            
            # Log progress every 10 iterations
            if iteration % 10 == 0:
                logger.info(f"  Progress: {total_updated} rows migrated")
            
            # If no more rows to update, we're done
            if rows_updated == 0:
                logger.info(f"✅ Backfill complete: {total_updated} rows migrated")
                elapsed = time.time() - start_time
                logger.info(f"   Time: {elapsed:.1f}s")
                return total_updated, True
            
            # Small sleep between batches to be nice to POOLER
            if rows_updated == batch_size:
                time.sleep(0.05)
                
        except OperationalError as e:
            error_str = str(e).lower()
            
            # Handle connection errors - retry with limit
            if any(x in error_str for x in ['ssl connection', 'connection reset', 'timeout']):
                retry_count += 1
                if retry_count > max_retries_per_batch:
                    logger.error(f"  Max retries ({max_retries_per_batch}) exceeded for batch {iteration}")
                    logger.error(f"  Stopping backfill. Progress: {total_updated} rows")
                    break
                
                logger.warning(f"  Connection error on batch {iteration} (retry {retry_count}/{max_retries_per_batch}): {e}")
                logger.warning(f"  Retrying in 2 seconds...")
                time.sleep(2.0)
                # Don't increment iteration - retry this batch
                continue
            
            # Handle lock timeout - skip and continue
            if 'lock_timeout' in error_str:
                logger.warning(f"  Lock timeout on batch {iteration} - skipping")
                iteration += 1
                retry_count = 0  # Reset retry count for next batch
                time.sleep(1.0)
                continue
            
            # Unknown error - log and break
            logger.error(f"  Error on batch {iteration}: {e}")
            break
            
        except Exception as e:
            logger.error(f"  Unexpected error on batch {iteration}: {e}")
            break
    
    if iteration >= max_iterations:
        logger.warning(f"⚠️  Max iterations reached")
    
    elapsed = time.time() - start_time
    logger.info(f"⚠️  Backfill incomplete: {total_updated} rows in {elapsed:.1f}s")
    logger.info(f"   Run again to continue")
    
    return total_updated, False


# ============================================================================
# BACKFILL REGISTRY
# ============================================================================

BACKFILL_DEFS: List[Dict] = [
    {
        'key': 'migration_36_last_call_direction',
        'migration_number': '36',
        'description': 'Populate last_call_direction on leads from first call in call_log',
        'tables': ['leads', 'call_log'],
        'batch_size': 200,  # Balanced: not too small (100) nor too large (1000)
        'max_runtime_seconds': 600,
        'priority': 'HIGH',
        'safe_to_run_online': True,  # Uses SKIP LOCKED
        'function': backfill_last_call_direction,
        'status': 'active',  # active, deprecated, completed
    },
    {
        'key': 'migration_96_lead_name',
        'migration_number': '96',
        'description': 'Migrate first_name + last_name to unified name field on leads',
        'tables': ['leads'],
        'batch_size': 200,  # POOLER-optimized batch size
        'max_runtime_seconds': 600,
        'priority': 'HIGH',
        'safe_to_run_online': True,  # Uses SKIP LOCKED + small batches
        'function': backfill_96_lead_name,
        'status': 'active',
    },
    # Additional backfills will be added here as they are migrated from migrations
]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_backfill_by_key(key: str) -> Optional[Dict]:
    """Get a backfill definition by its key."""
    for bf in BACKFILL_DEFS:
        if bf['key'] == key:
            return bf
    return None


def get_active_backfills() -> List[Dict]:
    """Get all active backfill definitions."""
    return [bf for bf in BACKFILL_DEFS if bf.get('status') == 'active']


def get_backfills_by_priority(priority: str) -> List[Dict]:
    """Get backfills by priority (HIGH/MEDIUM/LOW)."""
    return [bf for bf in BACKFILL_DEFS if bf.get('priority') == priority]


def get_backfills_for_migration(migration_number: str) -> List[Dict]:
    """Get all backfills associated with a specific migration."""
    return [bf for bf in BACKFILL_DEFS if bf.get('migration_number') == migration_number]
