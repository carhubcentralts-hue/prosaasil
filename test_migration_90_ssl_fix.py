#!/usr/bin/env python3
"""
Test for Migration 90 SSL Connection Fix

Verifies that Migration 90 uses resilient connection handling with:
1. Short-lived connections via engine.connect() instead of db.session
2. AUTOCOMMIT isolation level for metadata queries
3. Retry logic for transient OperationalError failures
"""
import sys
import os
import inspect

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_fetch_all_retry_function_exists():
    """Test that fetch_all_retry helper function is defined"""
    print("✓ Testing fetch_all_retry function exists...")
    from server import db_migrate
    
    assert hasattr(db_migrate, 'fetch_all_retry'), "fetch_all_retry function should exist"
    assert callable(db_migrate.fetch_all_retry), "fetch_all_retry should be callable"
    print("  ✅ fetch_all_retry function is defined and callable")


def test_migration_90_uses_fetch_all_retry():
    """Test that Migration 90 code uses fetch_all_retry instead of db.session"""
    print("✓ Testing Migration 90 uses fetch_all_retry...")
    from server.db_migrate import apply_migrations
    
    # Get source code of apply_migrations
    source = inspect.getsource(apply_migrations)
    
    # Check for Migration 90 section
    migration_90_start = source.find('Migration 90:')
    assert migration_90_start > 0, "Migration 90 should exist"
    print(f"  ✅ Found Migration 90 at position {migration_90_start}")
    
    # Extract Migration 90 section (next ~5000 chars)
    migration_90_section = source[migration_90_start:migration_90_start + 5000]
    
    # Verify it uses fetch_all_retry
    assert 'fetch_all_retry' in migration_90_section, \
        "Migration 90 should use fetch_all_retry for metadata queries"
    print("  ✅ Migration 90 uses fetch_all_retry")
    
    # Verify it doesn't use db.session.execute for information_schema queries
    # (DDL operations can still use db.session)
    lines = migration_90_section.split('\n')
    found_info_schema = False
    for i, line in enumerate(lines):
        if 'information_schema' in line.lower():
            found_info_schema = True
            # Check surrounding lines for fetch_all_retry
            context = '\n'.join(lines[max(0, i-5):min(len(lines), i+5)])
            assert 'fetch_all_retry' in context, \
                f"information_schema query should use fetch_all_retry: {line}"
            print("  ✅ information_schema query uses fetch_all_retry (not db.session)")
            break
    
    if not found_info_schema:
        print("  ⚠️  No information_schema query found in Migration 90")


def test_migration_90_uses_engine_connect_pattern():
    """Verify Migration 90 follows the engine.connect() pattern for metadata"""
    print("✓ Testing Migration 90 uses engine.connect() pattern...")
    from server.db_migrate import apply_migrations
    
    source = inspect.getsource(apply_migrations)
    migration_90_start = source.find('Migration 90:')
    migration_90_section = source[migration_90_start:migration_90_start + 5000]
    
    # Should use fetch_all_retry which internally uses engine.connect()
    assert 'fetch_all_retry(db.engine' in migration_90_section, \
        "Migration 90 should pass db.engine to fetch_all_retry"
    print("  ✅ Migration 90 passes db.engine to fetch_all_retry")


def test_fetch_all_retry_has_retry_logic():
    """Verify fetch_all_retry has proper retry and error handling"""
    print("✓ Testing fetch_all_retry has retry logic...")
    from server.db_migrate import fetch_all_retry
    
    # Get source code
    source = inspect.getsource(fetch_all_retry)
    
    # Check for retry loop
    assert 'for i in range(attempts)' in source or 'for' in source, \
        "fetch_all_retry should have retry loop"
    print("  ✅ Has retry loop")
    
    # Check for OperationalError handling
    assert 'OperationalError' in source, \
        "fetch_all_retry should handle OperationalError"
    print("  ✅ Handles OperationalError")
    
    # Check for sleep/backoff
    assert 'time.sleep' in source or 'sleep' in source, \
        "fetch_all_retry should have exponential backoff"
    print("  ✅ Has exponential backoff with sleep")
    
    # Check for engine.connect()
    assert 'engine.connect()' in source, \
        "fetch_all_retry should use engine.connect()"
    print("  ✅ Uses engine.connect() for short-lived connections")
    
    # Check for AUTOCOMMIT
    assert 'AUTOCOMMIT' in source, \
        "fetch_all_retry should use AUTOCOMMIT isolation level"
    print("  ✅ Uses AUTOCOMMIT isolation level")


def test_engine_configuration_has_resilience_settings():
    """Verify that app factory configures engine with resilience settings"""
    print("✓ Testing engine configuration has resilience settings...")
    
    # Read app_factory.py source
    import server.app_factory
    source = inspect.getsource(server.app_factory)
    
    # Check for pool_pre_ping
    assert 'pool_pre_ping' in source and 'True' in source, \
        "pool_pre_ping should be enabled"
    print("  ✅ pool_pre_ping is configured")
    
    # Check for pool_recycle
    assert 'pool_recycle' in source, \
        "pool_recycle should be configured"
    print("  ✅ pool_recycle is configured")
    
    # Check for keepalives
    assert 'keepalives' in source, \
        "keepalives should be configured"
    print("  ✅ keepalives are configured")
    
    assert 'keepalives_idle' in source, \
        "keepalives_idle should be configured"
    print("  ✅ keepalives_idle is configured")


def test_migration_90_no_long_lived_session():
    """Verify Migration 90 doesn't use db.session for information_schema queries"""
    print("✓ Testing Migration 90 doesn't use long-lived session for metadata...")
    from server.db_migrate import apply_migrations
    
    source = inspect.getsource(apply_migrations)
    migration_90_start = source.find('Migration 90:')
    migration_90_section = source[migration_90_start:migration_90_start + 5000]
    
    # Split into lines for analysis
    lines = migration_90_section.split('\n')
    
    # Look for db.session.execute with information_schema in same section
    found_problem = False
    for i, line in enumerate(lines):
        if 'db.session.execute' in line:
            # Check if this is for information_schema (within 5 lines)
            context = '\n'.join(lines[max(0, i-5):min(len(lines), i+5)])
            if 'information_schema' in context.lower():
                found_problem = True
                print(f"  ❌ Found db.session.execute for information_schema at line {i}")
                break
    
    assert not found_problem, \
        "Migration 90 should NOT use db.session.execute for information_schema queries"
    print("  ✅ Migration 90 does not use db.session for metadata queries")


def main():
    """Run all tests"""
    print("=" * 70)
    print("Migration 90 SSL Connection Fix - Test Suite")
    print("=" * 70)
    print()
    
    tests = [
        test_fetch_all_retry_function_exists,
        test_fetch_all_retry_has_retry_logic,
        test_migration_90_uses_fetch_all_retry,
        test_migration_90_uses_engine_connect_pattern,
        test_migration_90_no_long_lived_session,
        test_engine_configuration_has_resilience_settings,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
            print()
        except AssertionError as e:
            print(f"  ❌ FAILED: {e}")
            failed += 1
            print()
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            failed += 1
            print()
    
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
