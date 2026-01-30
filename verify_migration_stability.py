"""
Verification of 3 Critical Points for Migration Stability

This script verifies:
1. execute_with_retry() opens NEW connection on each retry attempt
2. No external engine.begin() wrapping execute_with_retry calls
3. No DML/backfills in migrations (DDL only)
"""

import re
import sys


def check_execute_with_retry_creates_new_connections():
    """
    Verify that execute_with_retry opens a NEW connection on each attempt.
    
    ✅ CORRECT pattern:
        for attempt in range(max_retries):
            with engine.begin() as conn:  # NEW connection each iteration
                ...
            except:
                engine.dispose()  # Ensures next iteration gets NEW connection
                
    ❌ WRONG pattern:
        conn = engine.connect()  # Reusing same connection
        for attempt in range(max_retries):
            conn.execute(...)
    """
    print("=" * 80)
    print("1. Checking execute_with_retry() creates NEW connections on each retry")
    print("=" * 80)
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Find the execute_with_retry function
    match = re.search(
        r'def execute_with_retry\([^)]+\):.*?(?=\ndef |\nclass |\Z)',
        content,
        re.DOTALL
    )
    
    if not match:
        print("❌ FAIL: execute_with_retry function not found")
        return False
    
    func_body = match.group(0)
    
    checks = {
        "Has for loop with attempts": r'for attempt in range\(max_retries\)',
        "Opens connection inside loop": r'with engine\.begin\(\) as conn:',
        "Calls engine.dispose() on error": r'engine\.dispose\(\)',
        "Has continue after dispose": r'continue',
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if re.search(pattern, func_body):
            print(f"✅ {check_name}")
        else:
            print(f"❌ {check_name}")
            all_passed = False
    
    # Verify connection is NOT created outside the loop
    if re.search(r'conn\s*=\s*engine\.(connect|begin)\(\).*?for attempt', func_body, re.DOTALL):
        print("❌ FAIL: Connection created outside retry loop (reusing conn)")
        all_passed = False
    else:
        print("✅ Connection NOT created outside loop (good)")
    
    print()
    return all_passed


def check_no_external_engine_begin():
    """
    Verify no external engine.begin() that wraps execute_with_retry calls.
    
    ❌ WRONG pattern:
        with engine.begin() as conn:
            execute_with_retry(engine, "...")  # Nested transactions confusion
    """
    print("=" * 80)
    print("2. Checking for external engine.begin() wrapping execute_with_retry")
    print("=" * 80)
    
    with open('server/db_migrate.py', 'r') as f:
        lines = f.readlines()
    
    issues = []
    in_with_block = False
    with_indent = 0
    with_line_num = 0
    
    for i, line in enumerate(lines, 1):
        # Check for 'with engine.begin()' or 'with engine.connect()'
        if re.match(r'\s*with\s+.*engine\.(begin|connect)\s*\(\)', line):
            in_with_block = True
            with_indent = len(line) - len(line.lstrip())
            with_line_num = i
            continue
        
        # If we're in a with block, check for execute_with_retry
        if in_with_block:
            current_indent = len(line) - len(line.lstrip())
            
            # If we've dedented, we're out of the with block
            if line.strip() and current_indent <= with_indent:
                in_with_block = False
                continue
            
            # Check if this line calls execute_with_retry
            if 'execute_with_retry' in line and not line.strip().startswith('#'):
                issues.append({
                    'line': i,
                    'with_line': with_line_num,
                    'code': line.strip()
                })
    
    if issues:
        print(f"⚠️  Found {len(issues)} potential issue(s):")
        for issue in issues:
            print(f"   Line {issue['line']} (with block started at {issue['with_line']})")
            print(f"   {issue['code']}")
        print()
        print("These should be reviewed - execute_with_retry should manage its own connections")
        return False
    else:
        print("✅ No external engine.begin() wrapping execute_with_retry calls")
        print()
        return True


def check_dml_in_migrations():
    """
    Verify migrations contain only DDL (no DML/backfills).
    
    ✅ ALLOWED in migrations:
        - CREATE TABLE
        - ALTER TABLE ADD COLUMN
        - CREATE INDEX (should be in db_indexes.py, but technically DDL)
        - Small INSERT/UPDATE for setup (e.g., schema_migrations tracking)
        
    ❌ NOT ALLOWED in migrations:
        - UPDATE on large tables
        - DELETE for data cleanup
        - INSERT for data migration
        - Loops over data
        - Backfill operations
    """
    print("=" * 80)
    print("3. Checking for DML/backfills in migrations (should be DDL only)")
    print("=" * 80)
    
    with open('server/db_migrate.py', 'r') as f:
        lines = f.readlines()
    
    # Find DML statements but exclude safe ones
    dml_patterns = [
        (r'UPDATE\s+\w+\s+SET', 'UPDATE'),
        (r'DELETE\s+FROM\s+\w+', 'DELETE'),
        (r'INSERT\s+INTO\s+(?!schema_migrations|alembic_version)', 'INSERT'),
    ]
    
    issues = []
    for i, line in enumerate(lines, 1):
        # Skip comments
        if line.strip().startswith('#'):
            continue
        
        for pattern, dml_type in dml_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                # Get some context
                context_start = max(0, i - 3)
                context_end = min(len(lines), i + 2)
                context = ''.join(lines[context_start:context_end])
                
                issues.append({
                    'line': i,
                    'type': dml_type,
                    'code': line.strip(),
                    'context': context
                })
    
    if issues:
        print(f"⚠️  Found {len(issues)} DML operation(s) in migrations:")
        print()
        
        for issue in issues:
            print(f"Line {issue['line']}: {issue['type']}")
            print(f"  {issue['code'][:80]}")
        
        print()
        print("These operations should be:")
        print("  1. Moved to db_backfills.py if they're data migrations")
        print("  2. Documented as safe if they're small one-time setup")
        print("  3. Removed if they're unnecessary")
        print()
        return False
    else:
        print("✅ No problematic DML operations found in migrations")
        print()
        return True


def main():
    print("\n")
    print("🔍 MIGRATION STABILITY VERIFICATION")
    print("=" * 80)
    print()
    
    results = [
        ("New connections on each retry", check_execute_with_retry_creates_new_connections()),
        ("No external engine.begin()", check_no_external_engine_begin()),
        ("DDL only (no DML/backfills)", check_dml_in_migrations()),
    ]
    
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "⚠️  NEEDS REVIEW"
        print(f"{status}: {test_name}")
    
    print()
    
    if all(passed for _, passed in results):
        print("🎉 All checks passed! Migrations are properly configured.")
        return 0
    else:
        print("⚠️  Some issues need review. See details above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
