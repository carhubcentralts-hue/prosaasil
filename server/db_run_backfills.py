#!/usr/bin/env python3
"""
Central Backfill Runner
=======================

Runs data backfill operations from the backfill registry.

This tool:
- Runs all or specific backfills from db_backfills.py
- Provides progress reporting
- Never fails deployment (always exits 0)
- Supports dry-run mode
- Time-boxed execution
- Resume capability (idempotent backfills)

Usage:
    python server/db_run_backfills.py --all                    # Run all active backfills
    python server/db_run_backfills.py --only <key>             # Run specific backfill
    python server/db_run_backfills.py --all --dry-run          # See what would run
    python server/db_run_backfills.py --all --max-minutes=20   # Time limit
    python server/db_run_backfills.py --priority HIGH          # Run by priority
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime
from typing import List, Dict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import SQLAlchemy
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError
except ImportError as e:
    logger.error(f"❌ Failed to import SQLAlchemy: {e}")
    sys.exit(0)

# Import backfill registry
try:
    from server.db_backfills import (
        BACKFILL_DEFS,
        get_backfill_by_key,
        get_active_backfills,
        get_backfills_by_priority
    )
except ImportError as e:
    logger.error(f"❌ Failed to import backfill registry: {e}")
    sys.exit(0)


def get_database_url() -> str:
    """
    Get database URL from environment.
    
    Uses POOLER connection for backfill operations.
    Pooler is safe with proper batch sizes, SKIP LOCKED, and timeouts.
    """
    # Add parent directory to path for server imports
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from server.database_url import get_database_url as get_db_url
    
    try:
        return get_db_url(connection_type="pooler")
    except RuntimeError as e:
        logger.error(f"❌ {e}")
        sys.exit(0)


def create_db_engine(database_url: str):
    """Create database engine with proper settings."""
    try:
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=180,
            pool_size=5,
            max_overflow=10,
            echo=False
        )
        return engine
    except Exception as e:
        logger.error(f"❌ Failed to create database engine: {e}")
        sys.exit(0)


def run_backfill(engine, backfill_def: Dict, dry_run: bool = False) -> bool:
    """
    Run a single backfill operation.
    
    Returns:
        True if successful or partially successful, False on error
    """
    key = backfill_def['key']
    description = backfill_def['description']
    
    logger.info("\n" + "=" * 80)
    logger.info(f"Backfill: {key}")
    logger.info("=" * 80)
    logger.info(f"Description: {description}")
    logger.info(f"Tables: {', '.join(backfill_def['tables'])}")
    logger.info(f"Batch size: {backfill_def['batch_size']}")
    logger.info(f"Max runtime: {backfill_def['max_runtime_seconds']}s")
    logger.info(f"Priority: {backfill_def['priority']}")
    
    if dry_run:
        logger.info("🔍 DRY RUN - Would execute backfill")
        return True
    
    # Run the backfill function
    try:
        function = backfill_def['function']
        batch_size = backfill_def.get('batch_size', 100)
        max_time = backfill_def.get('max_runtime_seconds', 600)
        
        rows_updated, completed = function(engine, batch_size=batch_size, max_time_seconds=max_time)
        
        if completed:
            logger.info(f"✅ Backfill {key} completed successfully ({rows_updated} rows)")
            return True
        else:
            logger.warning(f"⚠️  Backfill {key} partially complete ({rows_updated} rows)")
            logger.warning("Will continue on next run")
            return True  # Still considered success (partial progress)
            
    except Exception as e:
        logger.error(f"❌ Backfill {key} failed: {e}", exc_info=True)
        logger.warning("Continuing with next backfill (this one will retry on next run)")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Run database backfill operations',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --all                    # Run all active backfills
  %(prog)s --only migration_36_last_call_direction
  %(prog)s --priority HIGH          # Run only HIGH priority backfills
  %(prog)s --all --dry-run          # See what would run
  %(prog)s --all --max-minutes 20   # Time limit
        """
    )
    
    # Mode selection (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--all', action='store_true',
                            help='Run all active backfills')
    mode_group.add_argument('--only', type=str,
                            help='Run only the specified backfill (by key)')
    mode_group.add_argument('--priority', type=str, choices=['HIGH', 'MEDIUM', 'LOW'],
                            help='Run all backfills of specified priority')
    
    # Options
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would run without executing')
    parser.add_argument('--max-minutes', type=int,
                        help='Maximum total time in minutes (overrides individual backfill limits)')
    
    args = parser.parse_args()
    
    # Print header
    logger.info("=" * 80)
    logger.info("Database Backfill Runner")
    logger.info("=" * 80)
    logger.info(f"Started: {datetime.now().isoformat()}")
    
    if args.dry_run:
        logger.info("Mode: DRY RUN")
    
    # Get database connection
    database_url = get_database_url()
    engine = create_db_engine(database_url)
    
    # Test connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Database connection successful\n")
    except Exception as e:
        logger.error(f"❌ Failed to connect to database: {e}")
        sys.exit(0)
    
    # Determine which backfills to run
    backfills_to_run: List[Dict] = []
    
    if args.all:
        backfills_to_run = get_active_backfills()
        logger.info(f"Running all {len(backfills_to_run)} active backfills\n")
    elif args.only:
        backfill = get_backfill_by_key(args.only)
        if not backfill:
            logger.error(f"❌ Backfill '{args.only}' not found in registry")
            sys.exit(0)
        backfills_to_run = [backfill]
        logger.info(f"Running single backfill: {args.only}\n")
    elif args.priority:
        backfills_to_run = get_backfills_by_priority(args.priority)
        logger.info(f"Running {len(backfills_to_run)} {args.priority} priority backfills\n")
    
    if not backfills_to_run:
        logger.info("✅ No backfills to run")
        sys.exit(0)
    
    # Run backfills
    start_time = time.time()
    deadline = start_time + (args.max_minutes * 60) if args.max_minutes else None
    
    results = {
        'success': [],
        'failed': [],
        'skipped': []
    }
    
    for i, backfill_def in enumerate(backfills_to_run, 1):
        key = backfill_def['key']
        
        # Check time limit
        if deadline and time.time() >= deadline:
            logger.warning(f"\n⏰ Global time limit reached. Skipping remaining backfills.")
            results['skipped'].append(key)
            continue
        
        logger.info(f"\n[{i}/{len(backfills_to_run)}] Running backfill: {key}")
        
        success = run_backfill(engine, backfill_def, dry_run=args.dry_run)
        
        if success:
            results['success'].append(key)
        else:
            results['failed'].append(key)
    
    # Print summary
    elapsed = time.time() - start_time
    
    logger.info("\n" + "=" * 80)
    logger.info("BACKFILL SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total backfills: {len(backfills_to_run)}")
    logger.info(f"Successful: {len(results['success'])}")
    logger.info(f"Failed: {len(results['failed'])}")
    logger.info(f"Skipped: {len(results['skipped'])}")
    logger.info(f"Time elapsed: {elapsed:.1f}s")
    
    if results['success']:
        logger.info(f"\n✅ Successful:")
        for key in results['success']:
            logger.info(f"  • {key}")
    
    if results['failed']:
        logger.warning(f"\n❌ Failed:")
        for key in results['failed']:
            logger.warning(f"  • {key}")
        logger.warning("Failed backfills will retry on next run")
    
    if results['skipped']:
        logger.warning(f"\n⏭️  Skipped (time limit):")
        for key in results['skipped']:
            logger.warning(f"  • {key}")
    
    logger.info("\n" + "=" * 80)
    
    # Always exit 0 to not block deployment
    if results['failed']:
        logger.warning("⚠️  Some backfills failed, but deployment will continue")
        logger.warning("Failed backfills will retry on next deployment")
    else:
        logger.info("✅ All backfills completed successfully")
    
    logger.info("Backfill runner finished (exit 0)")
    sys.exit(0)


if __name__ == '__main__':
    main()
