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

Connection Policy (per requirements):
- Default: Work on POOLER
- At migration start: Try DIRECT once with 3-5s timeout
- If DIRECT succeeds: Use DIRECT for entire run (locked)
- If DIRECT fails: Use POOLER for entire run (locked)
- Never retry DIRECT in the middle of a run
"""
import os
import logging

logger = logging.getLogger(__name__)

# Global connection lock - once decided, never change during run
_CONNECTION_LOCKED = False
_LOCKED_CONNECTION_TYPE = None
_LOCKED_URL = None
_CONNECTION_LOGGED = False  # Track if we've logged the connection choice


def _try_connect_direct(url: str, timeout: int = 5) -> bool:
    """
    Try to connect to DIRECT database with short timeout.
    
    Args:
        url: Database URL to test
        timeout: Connection timeout in seconds (default 5)
        
    Returns:
        True if connection successful, False otherwise
    """
    try:
        from sqlalchemy import create_engine, text
        
        # Create temporary engine with short timeout
        engine = create_engine(
            url,
            pool_pre_ping=False,  # Don't need pre-ping for test
            connect_args={
                'connect_timeout': timeout,
            }
        )
        
        # Try to execute simple query
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        engine.dispose()
        return True
        
    except Exception as e:
        logger.debug(f"DIRECT connection test failed: {e}")
        return False


def get_database_url(connection_type: str = "pooler", verbose: bool = True, try_direct_first: bool = False) -> str:
    """
    Get database URL based on connection type.
    
    Connection Policy (per requirements):
    - Default: Work on POOLER
    - When try_direct_first=True (at migration start): Try DIRECT once with 5s timeout
    - If DIRECT succeeds: Use DIRECT for entire run (locked)
    - If DIRECT fails: Use POOLER for entire run (locked)
    - Never retry DIRECT in the middle of a run
    
    Args:
        connection_type: Either "pooler" (default) for API traffic or "direct" for DDL/migrations
        verbose: If True, logs which connection type and host is being used
        try_direct_first: If True, tries DIRECT with timeout before falling back to POOLER
    
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
    global _CONNECTION_LOCKED, _LOCKED_CONNECTION_TYPE, _LOCKED_URL, _CONNECTION_LOGGED
    
    connection_type = connection_type.lower()
    
    # ✅ LOCK ENFORCEMENT: Once connection is chosen, stick to it for entire run
    if _CONNECTION_LOCKED:
        if verbose and not _CONNECTION_LOGGED:
            logger.info(f"🔒 Using LOCKED connection: {_LOCKED_CONNECTION_TYPE.upper()}")
            _CONNECTION_LOGGED = True
        return _LOCKED_URL
    
    # For non-migration requests (pooler), just return pooler without trying DIRECT
    if connection_type == "pooler" and not try_direct_first:
        url = _get_url_by_type("pooler", verbose=verbose)
        return url
    
    # For DIRECT requests with try_direct_first=True: Try DIRECT once with timeout
    if connection_type == "direct" and try_direct_first:
        direct_url_raw = os.getenv("DATABASE_URL_DIRECT")
        
        if direct_url_raw:
            # Fix postgres:// → postgresql://
            direct_url = direct_url_raw.replace('postgres://', 'postgresql://', 1) if direct_url_raw.startswith('postgres://') else direct_url_raw
            
            if verbose:
                logger.info("=" * 80)
                logger.info("🔍 Attempting DIRECT connection (one-time check with 5s timeout)...")
            
            # Try to connect with 5 second timeout
            if _try_connect_direct(direct_url, timeout=5):
                # Success! Lock to DIRECT
                _CONNECTION_LOCKED = True
                _LOCKED_CONNECTION_TYPE = "direct"
                _LOCKED_URL = direct_url
                _CONNECTION_LOGGED = False  # Will log on next call
                
                if verbose:
                    logger.info("=" * 80)
                    logger.info("✅ Using DIRECT")
                    logger.info("=" * 80)
                    _log_connection_info("direct", direct_url, "DATABASE_URL_DIRECT")
                    _CONNECTION_LOGGED = True
                
                return direct_url
            else:
                # Failed - lock to POOLER
                if verbose:
                    logger.info("⚠️  DIRECT connection unavailable (timeout or unreachable)")
                    logger.info("=" * 80)
                    logger.info("✅ Using POOLER (DIRECT unavailable - locked)")
                    logger.info("=" * 80)
        else:
            if verbose:
                logger.info("=" * 80)
                logger.info("⚠️  DATABASE_URL_DIRECT not configured")
                logger.info("✅ Using POOLER (DIRECT unavailable - locked)")
                logger.info("=" * 80)
        
        # Lock to POOLER
        pooler_url = _get_url_by_type("pooler", verbose=verbose)
        _CONNECTION_LOCKED = True
        _LOCKED_CONNECTION_TYPE = "pooler"
        _LOCKED_URL = pooler_url
        _CONNECTION_LOGGED = True  # Already logged above
        return pooler_url
    
    # Default path: get URL by type without DIRECT attempt
    url = _get_url_by_type(connection_type, verbose=verbose)
    return url


def _get_url_by_type(connection_type: str, verbose: bool = True) -> str:
    """
    Internal function to get URL by connection type.
    
    Args:
        connection_type: Either "pooler" or "direct"
        verbose: If True, logs which connection type and host is being used
        
    Returns:
        str: PostgreSQL database URL
        
    Raises:
        RuntimeError: If no database configuration is found
    """
    # Priority 1: Use DATABASE_URL_POOLER or DATABASE_URL_DIRECT
    if connection_type == "direct":
        url = os.getenv("DATABASE_URL_DIRECT")
        source = "DATABASE_URL_DIRECT"
        
        # Fall back to POOLER if DIRECT not configured
        if not url:
            if verbose:
                logger.debug("DATABASE_URL_DIRECT not set, using POOLER")
            url = os.getenv("DATABASE_URL_POOLER")
            source = "DATABASE_URL_POOLER (DIRECT not configured)"
            
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
            elif '.db.' in host.lower() or 'direct' in host.lower():
                connection_method = "DIRECT"
            else:
                connection_method = "UNKNOWN"
            
            logger.info(f"   Connection source: {source}")
            logger.info(f"   Host: {host}")
            logger.info(f"   Method: {connection_method}")
                
    except Exception as e:
        logger.debug(f"Could not parse connection info: {e}")
