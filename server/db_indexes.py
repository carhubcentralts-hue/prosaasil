"""
Database Indexes Registry - Single Source of Truth
===================================================

This file is the ONLY place where performance-only indexes should be defined.

DO NOT add CREATE INDEX statements to migration files.
All performance indexes must be added here and will be built separately
during deployment to avoid blocking migrations.

Index Structure:
    - name: Unique identifier for the index
    - sql: The CREATE INDEX statement (use CONCURRENTLY IF NOT EXISTS)
    - critical: Whether this index is critical for basic functionality
    - description: What the index is for (for documentation)

Guidelines:
    1. Always use "CREATE INDEX CONCURRENTLY IF NOT EXISTS"
    2. Set critical=True only for indexes required for basic app functionality
    3. Set critical=False for performance-only indexes
    4. Add clear descriptions for future maintainability
    5. Use partial indexes (WHERE clauses) when appropriate to reduce size
"""

# List of all performance indexes
# Each entry defines one index that will be built during deployment
INDEX_DEFS = [
    {
        "name": "idx_leads_last_call_direction",
        "sql": """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_leads_last_call_direction 
            ON leads(last_call_direction)
        """,
        "critical": False,
        "description": "Index for filtering leads by call direction (inbound/outbound). Added in Migration 36."
    },
    {
        "name": "idx_call_log_lead_created",
        "sql": """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_call_log_lead_created 
            ON call_log(lead_id, created_at) 
            WHERE lead_id IS NOT NULL
        """,
        "critical": False,
        "description": "Partial index for efficient call_log lookups by lead_id with temporal ordering. Filters out NULL lead_ids. Used for backfill and lead history queries."
    },
    {
        "name": "idx_leads_backfill_pending",
        "sql": """
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_leads_backfill_pending 
            ON leads(tenant_id, id) 
            WHERE last_call_direction IS NULL
        """,
        "critical": False,
        "description": "Partial index for faster batch selection during backfill operations. Only indexes leads that need backfill (last_call_direction IS NULL). Auto-shrinks as backfill completes."
    },
]

# Export for convenience
__all__ = ['INDEX_DEFS']
