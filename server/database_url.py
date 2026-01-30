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


def get_database_url(connection_type: str = "pooler") -> str:
    """
    Get database URL based on connection type.
    
    Args:
        connection_type: Either "pooler" (default) for API traffic or "direct" for DDL/migrations
    
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
    elif connection_type == "pooler":
        url = os.getenv("DATABASE_URL_POOLER")
    else:
        raise ValueError(f"Invalid connection_type: {connection_type}. Must be 'pooler' or 'direct'")
    
    if url:
        # Fix postgres:// → postgresql:// (Heroku compatibility)
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        return url

    # Priority 2: Fallback to legacy DATABASE_URL (for backwards compatibility)
    url = os.getenv("DATABASE_URL")
    if url:
        # Fix postgres:// → postgresql:// (Heroku compatibility)
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
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
        return f"postgresql://{user}:{password}@{host}:{port}/{db}{qs}"

    # Priority 4: Error if nothing is configured
    raise RuntimeError(
        "❌ CRITICAL: No database configuration found!\n"
        "   Either set DATABASE_URL_POOLER and DATABASE_URL_DIRECT (recommended),\n"
        "   or set DATABASE_URL (legacy),\n"
        "   or set all of: DB_POSTGRESDB_HOST, DB_POSTGRESDB_USER, DB_POSTGRESDB_PASSWORD"
    )
