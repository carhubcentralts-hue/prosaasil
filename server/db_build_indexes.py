#!/usr/bin/env python3
"""
Database Index Builder - Idempotent and Safe
============================================

This script builds performance indexes defined in db_indexes.py.

It is designed to:
1. Run idempotently (safe to run multiple times)
2. Never fail deployment (exits 0 even on errors, with warnings)
3. Use CONCURRENTLY to avoid blocking table writes
4. Retry on lock conflicts with exponential backoff
5. Provide clear progress reporting

Usage:
    python server/db_build_indexes.py

Exit codes:
    0 - Always (even if some indexes fail, deployment should continue)
"""

import os
import sys
import time
import logging
from typing import Dict, List, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import SQLAlchemy components
try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError, ProgrammingError
except ImportError as e:
    logger.error(f"❌ Failed to import SQLAlchemy: {e}")
    logger.error("Please install required dependencies: pip install sqlalchemy psycopg2-binary")
    sys.exit(0)  # Exit 0 to not block deployment

# Import index definitions
try:
    from server.db_indexes import INDEX_DEFS
except ImportError as e:
    logger.error(f"❌ Failed to import INDEX_DEFS: {e}")
    logger.error("Please ensure server/db_indexes.py exists and is properly configured")
    sys.exit(0)  # Exit 0 to not block deployment


def get_database_url() -> str:
    """
    Get database URL from environment.
    
    Uses DIRECT connection (not pooler) for index building operations.
    This avoids lock contention issues with pooler connections.
    """
    # Import here to avoid circular dependency
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from server.database_url import get_database_url as get_db_url
    
    try:
        return get_db_url(connection_type="direct")
    except RuntimeError as e:
        logger.error(f"❌ {e}")
        sys.exit(0)  # Exit 0 to not block deployment


def create_db_engine(database_url: str):
    """Create database engine with proper settings."""
    try:
        # Create engine with pool_pre_ping to handle stale connections
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False
        )
        return engine
    except Exception as e:
        logger.error(f"❌ Failed to create database engine: {e}")
        sys.exit(0)  # Exit 0 to not block deployment


def index_exists(conn, index_name: str) -> bool:
    """Check if an index already exists."""
    try:
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes 
                WHERE indexname = :index_name
            )
        """), {"index_name": index_name})
        return result.scalar()
    except Exception as e:
        logger.warning(f"⚠️  Could not check existence of {index_name}: {e}")
        return False


def create_index_with_retry(
    engine,
    index_def: Dict[str, str],
    max_retries: int = 10,
    initial_backoff: float = 5.0
) -> Tuple[bool, str]:
    """
    Create an index with retry logic on lock conflicts.
    
    Returns:
        (success: bool, message: str)
    """
    index_name = index_def["name"]
    index_sql = index_def["sql"]
    
    for attempt in range(max_retries):
        try:
            # Use AUTOCOMMIT isolation level for CREATE INDEX CONCURRENTLY
            # This is required because CONCURRENTLY cannot run inside a transaction
            with engine.connect().execution_options(
                isolation_level="AUTOCOMMIT"
            ) as conn:
                # Set generous timeouts for index creation
                # lock_timeout: 5 minutes (300 seconds) - time to wait for locks
                # statement_timeout: 0 (unlimited) - index creation can take long
                conn.execute(text("SET lock_timeout = '300s'"))
                conn.execute(text("SET statement_timeout = 0"))
                
                # Execute the index creation
                conn.execute(text(index_sql))
                
                return True, f"✅ Created index {index_name}"
                
        except OperationalError as e:
            error_msg = str(e)
            
            # Check if it's a lock timeout or deadlock
            if "lock" in error_msg.lower() or "timeout" in error_msg.lower():
                backoff = initial_backoff * (2 ** attempt)
                logger.warning(
                    f"⚠️  Index {index_name} blocked (attempt {attempt + 1}/{max_retries}). "
                    f"Retrying in {backoff:.1f}s..."
                )
                time.sleep(backoff)
                continue
            else:
                # Some other operational error
                return False, f"❌ Failed to create {index_name}: {error_msg}"
                
        except ProgrammingError as e:
            error_msg = str(e)
            
            # Check if index already exists (this is OK)
            if "already exists" in error_msg.lower():
                return True, f"✅ Index {index_name} already exists (skipped)"
            else:
                return False, f"❌ SQL error creating {index_name}: {error_msg}"
                
        except Exception as e:
            # Unexpected error
            return False, f"❌ Unexpected error creating {index_name}: {e}"
    
    # Exhausted all retries
    return False, f"❌ Failed to create {index_name} after {max_retries} attempts (lock timeout)"


def build_indexes():
    """Main function to build all indexes."""
    logger.info("=" * 60)
    logger.info("Database Index Builder")
    logger.info("=" * 60)
    logger.info("")
    
    # Get database connection
    database_url = get_database_url()
    logger.info(f"Connecting to database...")
    
    engine = create_db_engine(database_url)
    
    # Test connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Database connection successful")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        logger.error("⚠️  Index build skipped, but deployment will continue")
        return
    
    logger.info("")
    logger.info(f"Found {len(INDEX_DEFS)} index(es) to process")
    logger.info("")
    
    # Track results
    created = []
    skipped = []
    failed = []
    
    # Process each index
    for i, index_def in enumerate(INDEX_DEFS, 1):
        index_name = index_def["name"]
        description = index_def.get("description", "No description")
        critical = index_def.get("critical", False)
        
        logger.info(f"[{i}/{len(INDEX_DEFS)}] Processing: {index_name}")
        logger.info(f"    Description: {description}")
        logger.info(f"    Critical: {critical}")
        
        # Check if index already exists
        try:
            with engine.connect() as conn:
                if index_exists(conn, index_name):
                    logger.info(f"    ⏭️  Already exists, skipping")
                    skipped.append(index_name)
                    logger.info("")
                    continue
        except Exception as e:
            logger.warning(f"    ⚠️  Could not check existence: {e}")
            # Continue anyway and let CREATE INDEX IF NOT EXISTS handle it
        
        # Try to create the index
        logger.info(f"    🔨 Creating index (this may take a while)...")
        success, message = create_index_with_retry(engine, index_def)
        
        logger.info(f"    {message}")
        
        if success:
            created.append(index_name)
        else:
            failed.append(index_name)
            if critical:
                logger.error(f"    ⚠️  CRITICAL INDEX FAILED!")
        
        logger.info("")
    
    # Print summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("=" * 60)
    logger.info("INDEX BUILD SUMMARY - FINAL REPORT")
    logger.info("=" * 60)
    logger.info("=" * 60)
    logger.info("")
    logger.info(f"Total indexes:  {len(INDEX_DEFS)}")
    logger.info(f"✅ Created:     {len(created)}")
    logger.info(f"⏭️  Skipped:     {len(skipped)} (already existed)")
    logger.info(f"❌ Failed:      {len(failed)}")
    logger.info("")
    
    if created:
        logger.info("✅ Successfully created indexes:")
        for name in created:
            logger.info(f"   • {name}")
        logger.info("")
    
    if skipped:
        logger.info("⏭️  Skipped indexes (already exist):")
        for name in skipped:
            logger.info(f"   • {name}")
        logger.info("")
    
    if failed:
        logger.warning("=" * 60)
        logger.warning("⚠️  ATTENTION: SOME INDEXES FAILED TO BUILD")
        logger.warning("=" * 60)
        logger.warning("")
        logger.warning(f"❌ {len(failed)} index(es) failed:")
        for name in failed:
            logger.warning(f"   • {name}")
        logger.warning("")
        logger.warning("⚠️  This is NOT critical - deployment will continue successfully.")
        logger.warning("⚠️  The application will work, but queries may be slower without these indexes.")
        logger.warning("")
        logger.warning("🔧 TO RETRY FAILED INDEXES:")
        logger.warning("    Run this command during low traffic:")
        logger.warning("")
        logger.warning("    docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm indexer")
        logger.warning("")
        logger.warning("    Or in development:")
        logger.warning("    python server/db_build_indexes.py")
        logger.warning("")
        logger.warning("=" * 60)
    else:
        logger.info("=" * 60)
        logger.info("🎉 SUCCESS: All indexes processed successfully!")
        logger.info("=" * 60)
        logger.info("")
    
    # Clean up
    engine.dispose()
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("Index build complete - Deployment continuing")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        build_indexes()
        # ALWAYS exit 0, even if some indexes failed
        # This ensures deployment continues regardless of index build status
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Unexpected error in index builder: {e}")
        logger.error("⚠️  Deployment will continue despite this error")
        # ALWAYS exit 0
        sys.exit(0)
