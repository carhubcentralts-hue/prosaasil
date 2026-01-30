"""
Database URL Configuration - Pooler vs Direct Connection
=========================================================
This module provides separate database connections for different use cases:

- POOLER: For API/Worker traffic (uses connection pooler like pgbouncer)
- DIRECT: For migrations/DDL operations (bypasses pooler for lock safety)

For Supabase:
- DATABASE_URL_POOLER should point to *.pooler.supabase.com
- DATABASE_URL_DIRECT should point to *.db.supabase.com

For other databases (Railway, Neon, local), both can be the same value.

This ensures DDL operations avoid "ghost locks" and SSL issues from poolers.
"""
import os
import logging

logger = logging.getLogger(__name__)


def get_database_url(connection_type: str = "pooler", verbose: bool = True) -> str:
    """
    Get database URL based on connection type.
    
    Args:
        connection_type: Either "pooler" (default) for API traffic or "direct" for DDL/migrations
        verbose: If True, logs which connection type and host is being used
    
    Priority:
    1. DATABASE_URL_{POOLER|DIRECT} environment variable (preferred)
    2. DATABASE_URL environment variable (legacy fallback)
    3. Construct from DB_POSTGRESDB_* variables (fallback)
    4. Raise error if none available
    
    Returns:
        str: PostgreSQL database URL
        
    Raises:
        RuntimeError: If no database configuration is found
    """
    connection_type = connection_type.lower()
    
    # Priority 1: Use DATABASE_URL_POOLER or DATABASE_URL_DIRECT
    if connection_type == "direct":
        url = os.getenv("DATABASE_URL_DIRECT")
        source = "DATABASE_URL_DIRECT"
    elif connection_type == "pooler":
        url = os.getenv("DATABASE_URL_POOLER")
        source = "DATABASE_URL_POOLER"
    else:
        raise ValueError(f"Invalid connection_type: {connection_type}. Must be 'pooler' or 'direct'")
    
    if url:
        # Fix postgres:// → postgresql:// (Heroku compatibility)
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        
        # Extract and log host (without password)
        if verbose:
            _log_connection_info(connection_type, url, source)
        
        return url

    # Priority 2: Fallback to legacy DATABASE_URL (for backwards compatibility)
    url = os.getenv("DATABASE_URL")
    if url:
        # Fix postgres:// → postgresql:// (Heroku compatibility)
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        
        if verbose:
            logger.warning(f"⚠️  Using DATABASE_URL fallback for {connection_type.upper()} connection")
            _log_connection_info(connection_type, url, "DATABASE_URL (fallback)")
        
        return url

    # Priority 3: Fallback to DB_POSTGRESDB_* variables
    host = os.getenv("DB_POSTGRESDB_HOST")
    user = os.getenv("DB_POSTGRESDB_USER")
    password = os.getenv("DB_POSTGRESDB_PASSWORD")
    db = os.getenv("DB_POSTGRESDB_DATABASE", "postgres")
    port = os.getenv("DB_POSTGRESDB_PORT", "5432")
    ssl = os.getenv("DB_POSTGRESDB_SSL", "true")

    if host and user and password:
        # Construct URL from individual components
        qs = "?sslmode=require" if ssl.lower() in ("1", "true", "yes") else ""
        url = f"postgresql://{user}:{password}@{host}:{port}/{db}{qs}"
        
        if verbose:
            logger.warning(f"⚠️  Using DB_POSTGRESDB_* fallback for {connection_type.upper()} connection")
            _log_connection_info(connection_type, url, "DB_POSTGRESDB_* (fallback)")
        
        return url

    # Priority 4: Error if nothing is configured
    raise RuntimeError(
        "❌ CRITICAL: No database configuration found!\n"
        "   Either set DATABASE_URL_POOLER and DATABASE_URL_DIRECT (recommended),\n"
        "   or set DATABASE_URL (legacy),\n"
        "   or set all of: DB_POSTGRESDB_HOST, DB_POSTGRESDB_USER, DB_POSTGRESDB_PASSWORD"
    )


def _log_connection_info(connection_type: str, url: str, source: str):
    """
    Log connection information (host only, no password).
    
    Args:
        connection_type: Type of connection (pooler/direct)
        url: Database URL
        source: Source of the URL (which env var)
    """
    try:
        # Extract host from URL (format: postgresql://user:pass@host:port/db)
        import re
        match = re.search(r'@([^:/@]+)', url)
        if match:
            host = match.group(1)
            
            # Determine if using pooler or direct based on hostname
            if 'pooler' in host.lower():
                connection_method = "POOLER"
                emoji = "🔄"
            elif '.db.' in host.lower() or 'direct' in host.lower():
                connection_method = "DIRECT"
                emoji = "🎯"
            else:
                connection_method = "UNKNOWN"
                emoji = "❓"
            
            logger.info(f"{emoji} Using {connection_type.upper()} connection ({source})")
            logger.info(f"   Host: {host}")
            logger.info(f"   Connection method: {connection_method}")
            
            # 🔥 HARD GUARD: Prevent migrations from running on POOLER
            # This is a critical safety check - migrations MUST use direct connection
            service_role = os.getenv('SERVICE_ROLE', '')
            if service_role in ['migrate', 'indexer', 'backfill']:
                if connection_type == 'direct' and 'pooler' in host.lower():
                    logger.error("=" * 80)
                    logger.error("🚨 CRITICAL ERROR: MIGRATION RUNNING ON POOLER CONNECTION!")
                    logger.error("=" * 80)
                    logger.error(f"Service: {service_role}")
                    logger.error(f"Requested: DIRECT connection")
                    logger.error(f"Got host: {host} (contains 'pooler')")
                    logger.error("")
                    logger.error("This will cause 'ghost locks' and migration timeouts!")
                    logger.error("Set DATABASE_URL_DIRECT to point to *.db.supabase.com")
                    logger.error("=" * 80)
                    raise RuntimeError(
                        f"FATAL: {service_role.upper()} service cannot use POOLER connection! "
                        f"Host '{host}' contains 'pooler' but DATABASE_URL_DIRECT should point to "
                        f"direct database connection (e.g., *.db.supabase.com)"
                    )
            
            # Warn if mismatch (but don't fail for other services)
            if connection_type == "direct" and "pooler" in host.lower():
                logger.warning("⚠️  WARNING: Requested DIRECT but host contains 'pooler'!")
            elif connection_type == "pooler" and ".db." in host.lower():
                logger.warning("⚠️  WARNING: Requested POOLER but host contains '.db.'!")
    except RuntimeError:
        # Re-raise hard guard errors
        raise
    except Exception as e:
        logger.debug(f"Could not parse connection info: {e}")
