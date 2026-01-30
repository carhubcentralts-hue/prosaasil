"""
Test the migration POOLER-only fix with execute_with_retry
"""
import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all required functions can be imported"""
    from server.db_migrate import (
        execute_with_retry,
        get_migrate_engine,
        check_table_exists,
        check_column_exists,
        check_index_exists,
        ensure_migration_tracking_table,
        is_migration_applied,
        mark_migration_applied
    )
    print("✅ All functions imported successfully")
    return True

def test_execute_with_retry_signature():
    """Test that execute_with_retry has the correct signature"""
    from server.db_migrate import execute_with_retry
    import inspect
    
    sig = inspect.signature(execute_with_retry)
    params = list(sig.parameters.keys())
    
    # Check required parameters
    assert 'engine' in params, "Missing 'engine' parameter"
    assert 'sql' in params, "Missing 'sql' parameter"
    assert 'params' in params, "Missing 'params' parameter"
    assert 'max_retries' in params, "Missing 'max_retries' parameter"
    assert 'fetch' in params, "Missing 'fetch' parameter"
    
    print("✅ execute_with_retry has correct signature")
    return True

def test_get_migrate_engine():
    """Test that get_migrate_engine creates a POOLER-only engine"""
    from server.db_migrate import get_migrate_engine
    import inspect
    
    # Read the source code
    source = inspect.getsource(get_migrate_engine)
    
    # Check that it mentions POOLER
    assert 'pooler' in source.lower(), "get_migrate_engine should use POOLER connection"
    assert 'USING POOLER (LOCKED)' in source, "Should log POOLER lock message"
    
    print("✅ get_migrate_engine configured for POOLER-only")
    return True

def test_no_db_session_usage():
    """Test that db.session is not used anywhere in the migration code"""
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Find all lines with db.session (excluding comments and documentation)
    lines = content.split('\n')
    problematic_lines = []
    
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip comments, docstrings, and documentation
        if stripped.startswith('#'):
            continue
        if 'BAD:' in line or 'NEVER use' in line or '❌' in line:
            continue
        if '"""' in line or "'''" in line:
            continue
            
        # Check for actual db.session usage
        if 'db.session.execute' in line or 'db.session.commit' in line or 'db.session.rollback' in line:
            problematic_lines.append((i, line))
    
    if problematic_lines:
        print("❌ Found db.session usage in the following lines:")
        for line_num, line in problematic_lines:
            print(f"  Line {line_num}: {line.strip()}")
        return False
    
    print("✅ No db.session usage found in migration code")
    return True

def test_execute_with_retry_has_dispose():
    """Test that execute_with_retry calls engine.dispose() on SSL errors"""
    from server.db_migrate import execute_with_retry
    import inspect
    
    source = inspect.getsource(execute_with_retry)
    
    assert 'engine.dispose()' in source, "execute_with_retry should call engine.dispose()"
    assert 'ssl' in source.lower(), "execute_with_retry should detect SSL errors"
    assert 'exponential' in source.lower(), "Should mention exponential backoff"
    
    print("✅ execute_with_retry has SSL error handling with engine.dispose()")
    return True

def test_retryable_errors():
    """Test that the correct SSL errors are detected as retryable"""
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    required_errors = [
        'ssl connection has been closed unexpectedly',
        'server closed the connection unexpectedly',
        'connection reset by peer',
        'could not receive data from server'
    ]
    
    content_lower = content.lower()
    for error in required_errors:
        if error not in content_lower:
            print(f"❌ Missing error pattern: {error}")
            return False
    
    print("✅ All required SSL error patterns are detected")
    return True

def main():
    """Run all tests"""
    print("=" * 80)
    print("Testing Migration POOLER-only Fix with execute_with_retry")
    print("=" * 80)
    print()
    
    tests = [
        ("Imports", test_imports),
        ("execute_with_retry signature", test_execute_with_retry_signature),
        ("get_migrate_engine POOLER-only", test_get_migrate_engine),
        ("No db.session usage", test_no_db_session_usage),
        ("execute_with_retry SSL handling", test_execute_with_retry_has_dispose),
        ("Retryable error patterns", test_retryable_errors),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            print(f"Testing: {test_name}...")
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test '{test_name}' failed with exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        print()
    
    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 80)
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
