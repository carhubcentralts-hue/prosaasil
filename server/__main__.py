#!/usr/bin/env python3
"""
Database Migration Runner - Standalone execution without eventlet or background workers

Usage:
    python -m server.db_migrate
    
Or in Docker:
    docker exec <container> python -m server.db_migrate

This module runs database migrations in isolation:
- NO eventlet monkey patching
- NO background threads  
- NO warmup logic
- NO workers
- Clean exit after completion
"""
import os
import sys
import logging

# CRITICAL: Set migration mode BEFORE any imports
os.environ['MIGRATION_MODE'] = '1'

# Disable eventlet-based async logging
os.environ['ASYNC_LOG_QUEUE'] = '0'

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stderr,
    force=True
)

logger = logging.getLogger(__name__)

def main():
    """Run database migrations standalone"""
    logger.info("=" * 80)
    logger.info("DATABASE MIGRATION RUNNER - Standalone Mode")
    logger.info("=" * 80)
    logger.info("Mode: MIGRATION_MODE=1 (no eventlet, no background threads)")
    
    # Validate DATABASE_URL is set
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL environment variable is not set!")
        sys.exit(1)
    
    logger.info(f"Database: {database_url.split('@')[0]}@***")  # Hide credentials
    
    try:
        # Import Flask and create minimal app
        logger.info("Creating minimal Flask app context...")
        from server.app_factory import create_minimal_app
        app = create_minimal_app()
        
        # Run migrations within app context
        logger.info("Running migrations...")
        with app.app_context():
            from server.db_migrate import apply_migrations
            migrations_applied = apply_migrations()
            
        logger.info("=" * 80)
        logger.info(f"✅ SUCCESS - Applied {len(migrations_applied)} migrations")
        logger.info("=" * 80)
        
        # Exit cleanly
        sys.exit(0)
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ MIGRATION FAILED: {e}")
        logger.error("=" * 80)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
