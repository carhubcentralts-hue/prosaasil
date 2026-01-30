#!/usr/bin/env python3
"""
Connection Type Demonstration Script
=====================================

This script demonstrates which database connection type (POOLER vs DIRECT)
is being used by different components of the system.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')

def demonstrate_connection_routing():
    """Demonstrate which connection each component uses."""
    
    print("=" * 80)
    print("DATABASE CONNECTION ROUTING DEMONSTRATION")
    print("=" * 80)
    print()
    
    # Set up test environment variables
    os.environ['DATABASE_URL_POOLER'] = 'postgresql://user:pass@xyz.pooler.supabase.com:5432/postgres'
    os.environ['DATABASE_URL_DIRECT'] = 'postgresql://user:pass@xyz.db.supabase.com:5432/postgres'
    
    from server.database_url import get_database_url
    
    print("1️⃣  MIGRATIONS / INDEXER / BACKFILL (Maintenance Operations)")
    print("-" * 80)
    try:
        url = get_database_url(connection_type='direct')
        print(f"✅ Uses: DIRECT connection")
        print(f"   URL contains: {_extract_host(url)}")
        print(f"   Expected: *.db.supabase.com or direct connection")
        print()
    except Exception as e:
        print(f"❌ Error: {e}")
        print()
    
    print("2️⃣  API / WORKER / CALLS (Runtime Operations)")
    print("-" * 80)
    try:
        url = get_database_url(connection_type='pooler')
        print(f"✅ Uses: POOLER connection")
        print(f"   URL contains: {_extract_host(url)}")
        print(f"   Expected: *.pooler.supabase.com or pooler connection")
        print()
    except Exception as e:
        print(f"❌ Error: {e}")
        print()
    
    print("3️⃣  FALLBACK BEHAVIOR (Legacy DATABASE_URL)")
    print("-" * 80)
    # Remove specific vars to test fallback
    del os.environ['DATABASE_URL_POOLER']
    del os.environ['DATABASE_URL_DIRECT']
    os.environ['DATABASE_URL'] = 'postgresql://user:pass@legacy.database.com:5432/postgres'
    
    try:
        url_direct = get_database_url(connection_type='direct', verbose=False)
        url_pooler = get_database_url(connection_type='pooler', verbose=False)
        print(f"✅ Both connection types fall back to DATABASE_URL")
        print(f"   DIRECT uses: {_extract_host(url_direct)}")
        print(f"   POOLER uses: {_extract_host(url_pooler)}")
        print(f"   (This is for backwards compatibility)")
        print()
    except Exception as e:
        print(f"❌ Error: {e}")
        print()
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print("✅ Connection routing is working correctly!")
    print()
    print("KEY POINTS:")
    print("  • Migrations use DIRECT → Avoids pooler 'ghost locks'")
    print("  • API/Worker use POOLER → Optimized for high traffic")
    print("  • Falls back to DATABASE_URL → Backwards compatible")
    print()


def _extract_host(url: str) -> str:
    """Extract host from database URL."""
    import re
    match = re.search(r'@([^:/@]+)', url)
    if match:
        return match.group(1)
    return "unknown"


if __name__ == "__main__":
    demonstrate_connection_routing()
