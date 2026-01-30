#!/usr/bin/env python3
"""
Guard test to prevent performance indexes in migrations

This test FAILS if any CREATE INDEX (non-UNIQUE) is found in db_migrate.py.
All performance indexes MUST be in server/db_indexes.py only.
"""
import re
import sys

def test_no_performance_indexes_in_migrations():
    """
    Ensure no performance-only CREATE INDEX statements in db_migrate.py
    Only UNIQUE constraints are allowed.
    """
    print("=" * 80)
    print("GUARD TEST: Checking for performance indexes in migrations")
    print("=" * 80)
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
        lines = content.split('\n')
    
    violations = []
    in_docstring = False
    in_function_def = False
    
    for i, line in enumerate(lines, 1):
        # Track docstrings
        if '"""' in line:
            in_docstring = not in_docstring
            continue
        
        if in_docstring:
            continue
        
        # Skip comments
        stripped = line.strip()
        if stripped.startswith('#'):
            continue
        
        # Track function definitions (skip examples in docstrings)
        if 'def exec_index' in line:
            in_function_def = True
            continue
        
        # Exit function def after the docstring closes
        if in_function_def and not in_docstring and line.strip() and not line.strip().startswith('"""'):
            if 'def ' in line:
                in_function_def = False
        
        # Skip if in function definition area
        if in_function_def:
            continue
        
        # Look for CREATE INDEX that is NOT UNIQUE
        if 'CREATE INDEX' in line.upper():
            # Check if this is a UNIQUE index
            if 'UNIQUE' not in line.upper():
                # Get some context
                context_start = max(0, i - 3)
                context_end = min(len(lines), i + 2)
                context = '\n'.join(lines[context_start:context_end])
                
                violations.append({
                    'line': i,
                    'text': line.strip(),
                    'context': context
                })
    
    # Report results
    if violations:
        print(f"\n❌ FAILED: Found {len(violations)} performance index(es) in migrations\n")
        print("Performance indexes MUST be in server/db_indexes.py ONLY!")
        print("Only UNIQUE constraints are allowed in migrations.\n")
        
        for v in violations:
            print(f"Line {v['line']}: {v['text']}")
            print(f"Context:")
            print(v['context'])
            print("-" * 80)
        
        print("\n🔧 How to fix:")
        print("1. Move the index definition to server/db_indexes.py")
        print("2. Remove the CREATE INDEX line from the migration")
        print("3. See INDEXING_GUIDE.md for instructions\n")
        
        sys.exit(1)
    else:
        print("\n✅ PASSED: No performance indexes found in migrations")
        print("All indexes are in server/db_indexes.py as required.\n")
        sys.exit(0)


if __name__ == '__main__':
    test_no_performance_indexes_in_migrations()
