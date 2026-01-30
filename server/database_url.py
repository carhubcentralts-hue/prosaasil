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
        
        # ✅ SOFT PREFER: If DIRECT not available, fall back to POOLER automatically
        # This ensures deployment doesn't fail when DIRECT is unreachable
        if not url:
            if verbose:
                logger.warning("⚠️  DATABASE_URL_DIRECT not set, falling back to POOLER")
                logger.warning("   💡 Migrations will use POOLER with appropriate timeouts")
            url = os.getenv("DATABASE_URL_POOLER")
            source = "DATABASE_URL_POOLER (auto-fallback from DIRECT)"
            
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
            
            # ✅ SOFT PREFER: Warn about mismatches, but don't fail deployment
            # The goal is to prefer DIRECT for migrations but allow POOLER fallback
            service_role = os.getenv('SERVICE_ROLE', '')
            
            if service_role == 'migrate' and 'pooler' in host.lower():
                logger.warning("=" * 80)
                logger.warning("⚠️  NOTICE: Migration running on POOLER (DIRECT not available)")
                logger.warning("=" * 80)
                logger.warning(f"   This is acceptable but not optimal")
                logger.warning(f"   For best results, set DATABASE_URL_DIRECT to *.db.supabase.com")
                logger.warning(f"   Migration will use extended timeouts and retries on POOLER")
                logger.warning("=" * 80)
            
            # Info logging for indexer/backfill using POOLER (this is ideal)
            if service_role in ['indexer', 'backfill'] and 'pooler' in host.lower():
                logger.info(f"✅ {service_role.upper()} running on POOLER (optimal configuration)")
                
            # Warn about other mismatches (informational only)
            if connection_type == "direct" and "pooler" in host.lower() and service_role not in ['migrate', 'indexer', 'backfill']:
                logger.warning("⚠️  INFO: Requested DIRECT but using POOLER (this is OK with fallback)")
            elif connection_type == "pooler" and ".db." in host.lower():
                logger.warning("⚠️  INFO: Requested POOLER but using DIRECT (this works but inefficient)")
                
    except Exception as e:
        logger.debug(f"Could not parse connection info: {e}")
