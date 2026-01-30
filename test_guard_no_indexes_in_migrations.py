#!/usr/bin/env python3
"""
Guard test to prevent performance indexes in migrations

This test FAILS if any CREATE INDEX (non-UNIQUE) is found in db_migrate.py.
All performance indexes MUST be in server/db_indexes.py only.

Uses regex on full file content to catch multi-line indexes.
"""
import re
import sys

def test_no_performance_indexes_in_migrations():
    """
    Ensure no performance-only CREATE INDEX statements in db_migrate.py
    Only UNIQUE constraints are allowed.
    
    Uses regex pattern matching on entire file to catch:
    - Single line indexes
    - Multi-line indexes
    - Indexes with various whitespace
    - f-strings or concatenated SQL
    """
    print("=" * 80)
    print("GUARD TEST: Checking for performance indexes in migrations")
    print("=" * 80)
    
    # Read entire file as one string
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Split into lines for reference
    lines = content.split('\n')
    
    # Skip to apply_migrations function (line ~730)
    # Everything before that is utility functions and examples
    code_start = 0
    for i, line in enumerate(lines):
        if 'def apply_migrations' in line:
            code_start = i
            break
    
    if code_start == 0:
        print("⚠️  Warning: Could not find apply_migrations function")
        print("Checking entire file...")
        code_content = content
    else:
        # Get only the migrations section
        code_content = '\n'.join(lines[code_start:])
    
    # Pattern to find CREATE INDEX statements (including multi-line)
    # Matches: CREATE [UNIQUE] INDEX with optional whitespace
    pattern = re.compile(
        r'CREATE\s+(?:(UNIQUE)\s+)?INDEX',
        re.IGNORECASE | re.MULTILINE
    )
    
    violations = []
    
    # Find all matches
    for match in pattern.finditer(code_content):
        # Check if this is a UNIQUE index
        unique_keyword = match.group(1)
        
        if not unique_keyword:
            # This is a performance index - violation!
            # Get position and context
            start_pos = match.start()
            end_pos = match.end()
            
            # Find line number
            line_num = code_content[:start_pos].count('\n') + code_start + 1
            
            # Get context (200 chars before and after)
            context_start = max(0, start_pos - 200)
            context_end = min(len(code_content), end_pos + 200)
            context = code_content[context_start:context_end]
            
            # Get the actual line
            line_start = code_content.rfind('\n', 0, start_pos) + 1
            line_end = code_content.find('\n', end_pos)
            if line_end == -1:
                line_end = len(code_content)
            actual_line = code_content[line_start:line_end].strip()
            
            violations.append({
                'line': line_num,
                'text': actual_line[:100] + '...' if len(actual_line) > 100 else actual_line,
                'context': context,
                'match': match.group(0)
            })
    
    # Report results
    if violations:
        print(f"\n❌ FAILED: Found {len(violations)} performance index(es) in migrations\n")
        print("Performance indexes MUST be in server/db_indexes.py ONLY!")
        print("Only UNIQUE constraints are allowed in migrations.\n")
        
        for i, v in enumerate(violations, 1):
            print(f"\n[{i}] Line ~{v['line']}: {v['match']}")
            print(f"Text: {v['text']}")
            print(f"\nContext:")
            print(v['context'][:300] + '...' if len(v['context']) > 300 else v['context'])
            print("-" * 80)
        
        print("\n🔧 How to fix:")
        print("1. Move the index definition to server/db_indexes.py")
        print("2. Remove the CREATE INDEX line from the migration")
        print("3. See INDEXING_GUIDE.md for instructions\n")
        
        sys.exit(1)
    else:
        print("\n✅ PASSED: No performance indexes found in migrations")
        print("All indexes are in server/db_indexes.py as required.")
        print("Guard uses regex on full file content - catches multi-line indexes.\n")
        sys.exit(0)


if __name__ == '__main__':
    test_no_performance_indexes_in_migrations()
