"""
Test that migration functions work correctly with the new implementation
"""
import sys
import os

# Mock modules that aren't available
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_execute_with_retry_logic():
    """Test the execute_with_retry logic without actual database"""
    print("Testing execute_with_retry logic...")
    
    # Read the function source
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Extract the execute_with_retry function
    start = content.find('def execute_with_retry(')
    end = content.find('\ndef ', start + 1)
    func_code = content[start:end]
    
    checks = [
        ('Has max_retries parameter with default 10', 'max_retries=10' in func_code),
        ('Has fetch parameter', 'fetch=' in func_code),
        ('Calls engine.begin()', 'engine.begin()' in func_code),
        ('Calls engine.dispose() on error', 'engine.dispose()' in func_code),
        ('Uses exponential backoff', '2 ** attempt' in func_code),
        ('Caps sleep at 8 seconds', 'min(2 ** attempt, 8)' in func_code or 'min(..., 8)' in func_code),
        ('Auto-detects SELECT queries', 'SELECT' in func_code and 'startswith' in func_code),
        ('Returns fetchall() for queries', 'fetchall()' in func_code),
    ]
    
    print("\nFunction checks:")
    for check_name, result in checks:
        status = "✅" if result else "❌"
        print(f"  {status} {check_name}")
    
    all_passed = all(result for _, result in checks)
    return all_passed

def test_get_migrate_engine_logic():
    """Test the get_migrate_engine configuration"""
    print("\nTesting get_migrate_engine configuration...")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Extract the get_migrate_engine function
    start = content.find('def get_migrate_engine(')
    end = content.find('\ndef ', start + 1)
    func_code = content[start:end]
    
    checks = [
        ('Uses pooler connection type', 'connection_type="pooler"' in func_code),
        ('Has pool_pre_ping enabled', 'pool_pre_ping=True' in func_code),
        ('Has pool_recycle set', 'pool_recycle=' in func_code),
        ('Logs POOLER locked message', 'USING POOLER (LOCKED)' in func_code),
        ('Uses checkpoint for logging', 'checkpoint(' in func_code),
        ('No DIRECT connection attempt', 'direct' not in func_code.lower() or 'NO DIRECT' in func_code),
    ]
    
    print("\nConfiguration checks:")
    for check_name, result in checks:
        status = "✅" if result else "❌"
        print(f"  {status} {check_name}")
    
    all_passed = all(result for _, result in checks)
    return all_passed

def test_metadata_functions():
    """Test that metadata check functions use execute_with_retry"""
    print("\nTesting metadata check functions...")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    functions_to_check = [
        'check_column_exists',
        'check_table_exists', 
        'check_index_exists',
        'check_constraint_exists',
        'ensure_migration_tracking_table',
        'is_migration_applied',
        'mark_migration_applied',
    ]
    
    checks = []
    for func_name in functions_to_check:
        # Find the function
        start = content.find(f'def {func_name}(')
        if start == -1:
            checks.append((f'{func_name} exists', False))
            continue
        
        end = content.find('\ndef ', start + 1)
        func_code = content[start:end]
        
        # Check if it uses execute_with_retry
        uses_execute_with_retry = 'execute_with_retry(' in func_code
        checks.append((f'{func_name} uses execute_with_retry', uses_execute_with_retry))
    
    print("\nMetadata function checks:")
    for check_name, result in checks:
        status = "✅" if result else "❌"
        print(f"  {status} {check_name}")
    
    all_passed = all(result for _, result in checks)
    return all_passed

def test_ssl_error_patterns():
    """Test that all required SSL error patterns are defined"""
    print("\nTesting SSL error pattern coverage...")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    required_patterns = [
        'SSL connection has been closed unexpectedly',
        'server closed the connection unexpectedly',
        'connection reset by peer',
        'could not receive data from server',
        'connection not open',
        'connection already closed',
        'network is unreachable',
        'could not connect to server',
    ]
    
    checks = []
    for pattern in required_patterns:
        found = pattern in content
        checks.append((f'Pattern: "{pattern[:40]}..."', found))
    
    print("\nError pattern checks:")
    for check_name, result in checks:
        status = "✅" if result else "❌"
        print(f"  {status} {check_name}")
    
    all_passed = all(result for _, result in checks)
    return all_passed

def main():
    print("=" * 80)
    print("Migration Execution Test - Implementation Verification")
    print("=" * 80)
    print()
    
    tests = [
        ("execute_with_retry logic", test_execute_with_retry_logic),
        ("get_migrate_engine configuration", test_get_migrate_engine_logic),
        ("Metadata functions", test_metadata_functions),
        ("SSL error patterns", test_ssl_error_patterns),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
        print()
    
    print("=" * 80)
    print("Test Summary")
    print("=" * 80)
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    print(f"\nTotal: {passed_count}/{len(results)} tests passed")
    print("=" * 80)
    
    return all(passed for _, passed in results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
