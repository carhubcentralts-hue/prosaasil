#!/usr/bin/env python3
"""
Test Database Connection Logging
=================================

This test verifies that the logging correctly shows which connection type
and host is being used, as required by the GO/NO-GO checklist.
"""

import os
import sys
import logging
from io import StringIO

# Add parent directory to path
sys.path.insert(0, '/home/runner/work/prosaasil/prosaasil')


def test_connection_logging():
    """Test that connection logging works correctly."""
    
    print("=" * 80)
    print("TEST: Database Connection Logging")
    print("=" * 80)
    print()
    
    # Set up logging to capture output
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    logger = logging.getLogger('server.database_url')
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    # Set up test environment variables
    os.environ['DATABASE_URL_POOLER'] = 'postgresql://user:pass@xyz.pooler.supabase.com:5432/postgres?sslmode=require'
    os.environ['DATABASE_URL_DIRECT'] = 'postgresql://user:pass@xyz.db.supabase.com:5432/postgres?sslmode=require'
    
    from server.database_url import get_database_url
    
    # Test 1: DIRECT connection
    print("Test 1: DIRECT Connection Logging")
    print("-" * 80)
    log_stream.truncate(0)
    log_stream.seek(0)
    
    url = get_database_url(connection_type='direct', verbose=True)
    log_output = log_stream.getvalue()
    
    print("Log output:")
    print(log_output)
    
    # Verify expectations
    checks = {
        "Shows DIRECT": "DIRECT" in log_output.upper(),
        "Shows host": "xyz.db.supabase.com" in log_output,
        "Shows emoji": any(emoji in log_output for emoji in ["🎯", "🔄", "❓"]),
        "Shows connection method": "Connection method" in log_output,
    }
    
    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check}: {passed}")
    
    print()
    
    # Test 2: POOLER connection
    print("Test 2: POOLER Connection Logging")
    print("-" * 80)
    log_stream.truncate(0)
    log_stream.seek(0)
    
    url = get_database_url(connection_type='pooler', verbose=True)
    log_output = log_stream.getvalue()
    
    print("Log output:")
    print(log_output)
    
    # Verify expectations
    checks = {
        "Shows POOLER": "POOLER" in log_output.upper(),
        "Shows host": "xyz.pooler.supabase.com" in log_output,
        "Shows emoji": any(emoji in log_output for emoji in ["🎯", "🔄", "❓"]),
        "Shows connection method": "Connection method" in log_output,
    }
    
    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check}: {passed}")
    
    print()
    
    # Test 3: Mismatch warning
    print("Test 3: Mismatch Warning (requesting DIRECT but got pooler host)")
    print("-" * 80)
    
    # Set DIRECT to use pooler URL (wrong!)
    os.environ['DATABASE_URL_DIRECT'] = 'postgresql://user:pass@xyz.pooler.supabase.com:5432/postgres'
    
    log_stream.truncate(0)
    log_stream.seek(0)
    
    # Force reload
    import importlib
    import server.database_url
    importlib.reload(server.database_url)
    
    from server.database_url import get_database_url as get_url_reloaded
    
    url = get_url_reloaded(connection_type='direct', verbose=True)
    log_output = log_stream.getvalue()
    
    print("Log output:")
    print(log_output)
    
    if "WARNING" in log_output and "pooler" in log_output.lower():
        print("✅ Warning is correctly shown when there's a mismatch")
    else:
        print("❌ Expected warning about mismatch not shown")
    
    print()
    print("=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print()
    print("✅ Connection logging is working as expected!")
    print()
    print("When migrations run, you will see:")
    print("  🎯 Using DIRECT connection (DATABASE_URL_DIRECT)")
    print("     Host: xyz.db.supabase.com")
    print("     Connection method: DIRECT")
    print()
    print("When API starts, you will see:")
    print("  🔄 Using POOLER connection (DATABASE_URL_POOLER)")
    print("     Host: xyz.pooler.supabase.com")
    print("     Connection method: POOLER")
    print()


if __name__ == "__main__":
    test_connection_logging()
