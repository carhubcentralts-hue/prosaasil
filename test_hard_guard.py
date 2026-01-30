#!/usr/bin/env python3
"""
Test Hard Guard - Prevent Migrations on POOLER
================================================

This test verifies that the hard guard prevents migrations from running
on a pooler connection, which would cause "ghost locks" and timeouts.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')


def test_hard_guard_prevents_pooler_for_migrations():
    """Test that hard guard fails if migrations try to use pooler."""
    
    print("=" * 80)
    print("TEST: Hard Guard - Prevent Migrations on POOLER")
    print("=" * 80)
    print()
    
    # Set up WRONG environment - migrations using pooler (this should FAIL)
    os.environ['DATABASE_URL_DIRECT'] = 'postgresql://user:pass@xyz.pooler.supabase.com:5432/postgres'
    os.environ['SERVICE_ROLE'] = 'migrate'
    
    # Force reload of module
    import importlib
    if 'server.database_url' in sys.modules:
        del sys.modules['server.database_url']
    
    from server.database_url import get_database_url
    
    print("Test 1: Migrations with POOLER host (should FAIL)")
    print("-" * 80)
    print(f"DATABASE_URL_DIRECT: ...@xyz.pooler.supabase.com")
    print(f"SERVICE_ROLE: migrate")
    print()
    
    try:
        url = get_database_url(connection_type='direct', verbose=True)
        print("❌ FAIL: Should have raised RuntimeError but didn't!")
        print(f"   Got URL: {url}")
        return False
    except RuntimeError as e:
        if 'FATAL' in str(e) and 'POOLER' in str(e):
            print("✅ PASS: Hard guard correctly prevented pooler usage")
            print(f"   Error message: {str(e)[:100]}...")
        else:
            print(f"❌ FAIL: Wrong error: {e}")
            return False
    print()
    
    # Test 2: API with pooler host (should SUCCEED)
    print("Test 2: API with POOLER host (should SUCCEED)")
    print("-" * 80)
    
    os.environ['SERVICE_ROLE'] = 'api'
    os.environ['DATABASE_URL_POOLER'] = 'postgresql://user:pass@xyz.pooler.supabase.com:5432/postgres'
    
    # Force reload
    if 'server.database_url' in sys.modules:
        del sys.modules['server.database_url']
    
    from server.database_url import get_database_url as get_url2
    
    try:
        url = get_url2(connection_type='pooler', verbose=False)
        print("✅ PASS: API correctly uses pooler connection")
        print(f"   Host: xyz.pooler.supabase.com")
    except Exception as e:
        print(f"❌ FAIL: API should be able to use pooler: {e}")
        return False
    print()
    
    # Test 3: Migrations with correct DIRECT host (should SUCCEED)
    print("Test 3: Migrations with DIRECT host (should SUCCEED)")
    print("-" * 80)
    
    os.environ['SERVICE_ROLE'] = 'migrate'
    os.environ['DATABASE_URL_DIRECT'] = 'postgresql://user:pass@xyz.db.supabase.com:5432/postgres'
    
    # Force reload
    if 'server.database_url' in sys.modules:
        del sys.modules['server.database_url']
    
    from server.database_url import get_database_url as get_url3
    
    try:
        url = get_url3(connection_type='direct', verbose=False)
        print("✅ PASS: Migrations correctly use direct connection")
        print(f"   Host: xyz.db.supabase.com")
    except Exception as e:
        print(f"❌ FAIL: Migrations should work with direct: {e}")
        return False
    print()
    
    print("=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print()
    print("✅ Hard guard is working correctly!")
    print()
    print("Summary:")
    print("  • Migrations CANNOT use pooler → FATAL error")
    print("  • API CAN use pooler → Works fine")
    print("  • Migrations CAN use direct → Works fine")
    print()
    print("This prevents the exact issue that caused your lock timeouts!")
    print()
    
    return True


if __name__ == "__main__":
    success = test_hard_guard_prevents_pooler_for_migrations()
    sys.exit(0 if success else 1)
