"""
Unified Database URL Validation

Used by all services (api, worker, calls) to validate DATABASE_URL on startup.
This prevents DNS errors and ensures fail-fast behavior.

Usage:
    from server.database_validation import validate_database_url
    validate_database_url()  # Exits with error if invalid
"""
import os
import sys
import logging

logger = logging.getLogger(__name__)

def validate_database_url():
    """
    Validate DATABASE_URL environment variable.
    
    Performs the following checks:
    1. DATABASE_URL is set and not empty
    2. DATABASE_URL is not using SQLite in production
    3. DATABASE_URL has valid format
    
    Exits with error code 1 if validation fails.
    """
    DATABASE_URL = os.getenv('DATABASE_URL', '')
    IS_PRODUCTION = os.getenv('PRODUCTION', '0') == '1' or os.getenv('FLASK_ENV') == 'production'
    
    # Check 1: DATABASE_URL must be set
    if not DATABASE_URL:
        logger.error("=" * 80)
        logger.error("❌ CRITICAL: DATABASE_URL environment variable is not set!")
        logger.error("=" * 80)
        logger.error("All services require DATABASE_URL to access the database.")
        logger.error("Set DATABASE_URL in your .env file or environment.")
        logger.error("")
        logger.error("Example:")
        logger.error("  DATABASE_URL=postgresql://user:pass@host:5432/dbname")
        logger.error("")
        logger.error("=" * 80)
        sys.exit(1)
    
    # Check 2: SQLite not allowed in production
    if IS_PRODUCTION and DATABASE_URL.startswith('sqlite'):
        logger.error("=" * 80)
        logger.error("❌ FATAL: SQLite is not allowed in production!")
        logger.error("=" * 80)
        logger.error("Production requires PostgreSQL for:")
        logger.error("  - Concurrent access from multiple services")
        logger.error("  - ACID transactions")
        logger.error("  - Better performance")
        logger.error("")
        logger.error("Set DATABASE_URL to a PostgreSQL connection string.")
        logger.error("=" * 80)
        sys.exit(1)
    
    # Check 3: Basic format validation
    if not ('://' in DATABASE_URL and '@' in DATABASE_URL):
        logger.error("=" * 80)
        logger.error("❌ FATAL: DATABASE_URL has invalid format!")
        logger.error("=" * 80)
        logger.error(f"Current value: {DATABASE_URL[:50]}...")
        logger.error("")
        logger.error("Expected format:")
        logger.error("  postgresql://user:password@host:port/database")
        logger.error("=" * 80)
        sys.exit(1)
    
    # Normalize postgres:// to postgresql://
    if DATABASE_URL.startswith('postgres://'):
        logger.warning("⚠️  DATABASE_URL uses deprecated 'postgres://' scheme")
        logger.warning("   Auto-converting to 'postgresql://'")
        os.environ['DATABASE_URL'] = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    # Mask password for logging
    masked_url = DATABASE_URL
    try:
        if '@' in DATABASE_URL and '://' in DATABASE_URL:
            parts = DATABASE_URL.split('://', 1)
            if len(parts) == 2 and '@' in parts[1]:
                auth_and_host = parts[1].split('@', 1)
                if ':' in auth_and_host[0]:
                    user = auth_and_host[0].split(':', 1)[0]
                    masked_url = f"{parts[0]}://{user}:***@{auth_and_host[1]}"
    except Exception:
        masked_url = DATABASE_URL[:20] + "***"
    
    logger.info(f"✅ DATABASE_URL validated: {masked_url}")
    return True


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    validate_database_url()
    print("\n✅ DATABASE_URL validation passed")
