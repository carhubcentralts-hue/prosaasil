"""
Database URL Configuration - Single Source of Truth
====================================================
This module provides a unified way to get the database URL.
It prioritizes DATABASE_URL, with fallback to DB_POSTGRESDB_* variables.

This ensures all parts of the application (migrations, health checks, API) 
use the same database connection.
"""
import os


def get_database_url() -> str:
    """
    Get database URL with single source of truth.
    
    Priority:
    1. DATABASE_URL environment variable (preferred)
    2. Construct from DB_POSTGRESDB_* variables (fallback)
    3. Raise error if neither is available
    
    Returns:
        str: PostgreSQL database URL
        
    Raises:
        RuntimeError: If no DATABASE_URL and no DB_POSTGRESDB_* vars are set
    """
    # Priority 1: Use DATABASE_URL if available
    url = os.getenv("DATABASE_URL")
    if url:
        # Fix postgres:// → postgresql:// (Heroku compatibility)
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        return url

    # Priority 2: Fallback to DB_POSTGRESDB_* variables
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

    # Priority 3: Error if nothing is configured
    raise RuntimeError(
        "❌ CRITICAL: No database configuration found!\n"
        "   Either set DATABASE_URL or all of: DB_POSTGRESDB_HOST, "
        "DB_POSTGRESDB_USER, DB_POSTGRESDB_PASSWORD"
    )
