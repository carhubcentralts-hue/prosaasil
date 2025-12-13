#!/usr/bin/env python3
"""
Test script to verify db_migrate.py transaction fixes.

This test verifies:
1. check_table_exists uses db.engine.connect() (independent connection)
2. check_column_exists uses db.engine.connect() (independent connection)
3. check_index_exists uses db.engine.connect() (independent connection)
4. Exception handlers properly call db.session.rollback()
5. Table existence checks are done before COUNT queries
"""
import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_independent_connections():
    """Verify that check_* functions use db.engine.connect() instead of db.session"""
    print("\n=== Checking Independent Connections ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        all_ok = True
        
        # Extract check_table_exists function
        table_exists_match = re.search(
            r'def check_table_exists\(.*?\):.*?(?=\ndef |\Z)', 
            content, 
            re.DOTALL
        )
        
        if table_exists_match:
            func_content = table_exists_match.group(0)
            if 'db.engine.connect()' in func_content:
                print(f"  ✅ check_table_exists uses db.engine.connect()")
            elif 'db.session.execute' in func_content:
                print(f"  ❌ check_table_exists still uses db.session.execute")
                all_ok = False
            else:
                print(f"  ⚠️  check_table_exists - unclear connection method")
                all_ok = False
        else:
            print(f"  ❌ check_table_exists function not found")
            all_ok = False
        
        # Extract check_column_exists function
        column_exists_match = re.search(
            r'def check_column_exists\(.*?\):.*?(?=\ndef |\Z)', 
            content, 
            re.DOTALL
        )
        
        if column_exists_match:
            func_content = column_exists_match.group(0)
            if 'db.engine.connect()' in func_content:
                print(f"  ✅ check_column_exists uses db.engine.connect()")
            elif 'db.session.execute' in func_content:
                print(f"  ❌ check_column_exists still uses db.session.execute")
                all_ok = False
            else:
                print(f"  ⚠️  check_column_exists - unclear connection method")
                all_ok = False
        else:
            print(f"  ❌ check_column_exists function not found")
            all_ok = False
        
        # Extract check_index_exists function
        index_exists_match = re.search(
            r'def check_index_exists\(.*?\):.*?(?=\ndef |\Z)', 
            content, 
            re.DOTALL
        )
        
        if index_exists_match:
            func_content = index_exists_match.group(0)
            if 'db.engine.connect()' in func_content:
                print(f"  ✅ check_index_exists uses db.engine.connect()")
            elif 'db.session.execute' in func_content:
                print(f"  ❌ check_index_exists still uses db.session.execute")
                all_ok = False
            else:
                print(f"  ⚠️  check_index_exists - unclear connection method")
                all_ok = False
        else:
            print(f"  ❌ check_index_exists function not found")
            all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def check_rollback_calls():
    """Verify that exception handlers in apply_migrations have db.session.rollback() calls"""
    print("\n=== Checking Rollback Calls ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Find all except Exception blocks and check for rollback
        except_blocks = re.findall(
            r'except Exception.*?(?=\n(?:    \w|def |if __name__))', 
            content, 
            re.DOTALL
        )
        
        rollback_count = 0
        no_rollback_count = 0
        skipped_count = 0
        
        for block in except_blocks:
            # Skip check_* functions - they use independent connections and don't need rollback
            if any(x in block for x in ['Error checking if column', 'Error checking if table', 'Error checking if index', 'Failed to create tables']):
                skipped_count += 1
                continue
            
            if 'db.session.rollback()' in block:
                rollback_count += 1
            elif 'Data protection violation' in block and 'raise' in block:
                # This is OK - it re-raises the exception
                rollback_count += 1
            else:
                no_rollback_count += 1
                # Print first 100 chars for debugging
                snippet = block.replace('\n', ' ')[:100]
                print(f"  ⚠️  Exception block without rollback: {snippet}...")
        
        print(f"  ✅ Found {rollback_count} exception handlers with proper rollback")
        print(f"  ℹ️  Skipped {skipped_count} check_* functions (use independent connections)")
        if no_rollback_count > 0:
            print(f"  ❌ Found {no_rollback_count} exception handlers without rollback")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def check_table_exists_before_count():
    """Verify that COUNT queries are preceded by check_table_exists calls"""
    print("\n=== Checking Table Existence Checks Before COUNT ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Find all COUNT queries in the file
        count_queries = re.finditer(
            r'SELECT COUNT\(\*\) FROM (\w+)',
            content,
            re.IGNORECASE
        )
        
        all_ok = True
        count_found = 0
        
        for match in count_queries:
            count_found += 1
            table_name = match.group(1)
            
            # Get context around this COUNT query (500 chars before)
            start_pos = max(0, match.start() - 500)
            context = content[start_pos:match.start()]
            
            # Check if there's a check_table_exists call for this table in the context
            if f"check_table_exists('{table_name}')" in context or \
               f'check_table_exists("{table_name}")' in context:
                print(f"  ✅ COUNT on '{table_name}' is protected by check_table_exists")
            else:
                print(f"  ❌ COUNT on '{table_name}' is NOT protected by check_table_exists")
                all_ok = False
        
        if count_found == 0:
            print(f"  ⚠️  No COUNT queries found")
            all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def check_no_nested_rollback_try():
    """Verify that rollback calls are not wrapped in try-except anymore"""
    print("\n=== Checking Direct Rollback Calls (No Nested Try) ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Look for the old pattern: try: db.session.rollback() except: pass
        old_pattern_count = len(re.findall(
            r'try:\s*db\.session\.rollback\(\)\s*except',
            content
        ))
        
        if old_pattern_count > 0:
            print(f"  ❌ Found {old_pattern_count} instances of nested try-except for rollback")
            return False
        else:
            print(f"  ✅ No nested try-except blocks wrapping rollback calls")
            return True
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def check_table_schema_filter():
    """Verify that check_table_exists includes table_schema = 'public' filter"""
    print("\n=== Checking Table Schema Filter ===")
    
    filepath = 'server/db_migrate.py'
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Extract check_table_exists function
        table_exists_match = re.search(
            r'def check_table_exists\(.*?\):.*?(?=\ndef |\Z)', 
            content, 
            re.DOTALL
        )
        
        if table_exists_match:
            func_content = table_exists_match.group(0)
            if "table_schema = 'public'" in func_content or \
               'table_schema = "public"' in func_content or \
               "table_schema='public'" in func_content:
                print(f"  ✅ check_table_exists includes table_schema = 'public' filter")
                return True
            else:
                print(f"  ⚠️  check_table_exists does not filter by table_schema='public'")
                print(f"      This is not critical but recommended for PostgreSQL")
                return True  # Not a failure, just a warning
        else:
            print(f"  ❌ check_table_exists function not found")
            return False
        
    except Exception as e:
        print(f"  ❌ Error checking {filepath}: {e}")
        return False


def main():
    """Run all verification checks"""
    print("=" * 60)
    print("DB MIGRATION TRANSACTION FIX VERIFICATION")
    print("=" * 60)
    
    results = {
        'Independent Connections': check_independent_connections(),
        'Rollback Calls': check_rollback_calls(),
        'Table Existence Before COUNT': check_table_exists_before_count(),
        'No Nested Rollback Try': check_no_nested_rollback_try(),
        'Table Schema Filter': check_table_schema_filter(),
    }
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for check_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {check_name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✅ ALL CHECKS PASSED - Transaction fixes look good!")
        print("\nKey improvements:")
        print("1. ✅ check_* functions use independent connections (db.engine.connect())")
        print("2. ✅ All exception handlers call db.session.rollback()")
        print("3. ✅ COUNT queries are protected by table existence checks")
        print("4. ✅ No nested try-except wrapping rollback calls")
        print("\nThis prevents InFailedSqlTransaction errors!")
        return 0
    else:
        print("\n❌ SOME CHECKS FAILED - Review the issues above")
        return 1


if __name__ == '__main__':
    sys.exit(main())
