"""
Test for Migration 80 constraint_row UnboundLocalError fix

This test verifies that the constraint_row variable is properly initialized
before being used in Migration 80, preventing UnboundLocalError.
"""

import re


def test_constraint_row_initialization():
    """Test that constraint_row is properly initialized in Migration 80"""
    
    # Read the migration file
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Find Migration 80 section
    migration_80_pattern = r'# Migration 80:.*?except Exception as e:'
    match = re.search(migration_80_pattern, content, re.DOTALL)
    
    assert match, "Could not find Migration 80 section"
    migration_80_code = match.group(0)
    
    # Verify constraint_row is assigned before being used
    # Should have: constraint_row = result[0] if result else None
    constraint_row_assignment = re.search(r'constraint_row\s*=\s*result\[0\]\s+if\s+result\s+else\s+None', migration_80_code)
    assert constraint_row_assignment, "constraint_row should be assigned from result[0] if result else None"
    
    # Verify constraint_row is checked before use
    constraint_row_check = re.search(r'if\s+constraint_row:', migration_80_code)
    assert constraint_row_check, "constraint_row should be checked with 'if constraint_row:' before use"
    
    # Verify the assignment comes before the check
    assignment_pos = constraint_row_assignment.start()
    check_pos = constraint_row_check.start()
    assert assignment_pos < check_pos, "constraint_row assignment should come before the check"
    
    print("✅ Migration 80 constraint_row initialization is correct")
    print("✅ constraint_row is assigned before being used")
    print("✅ Proper guard check is in place")


def test_migration_80_idempotency():
    """Test that Migration 80 is idempotent (checks if file_downloaded already exists)"""
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Find Migration 80 section
    migration_80_pattern = r'# Migration 80:.*?except Exception as e:'
    match = re.search(migration_80_pattern, content, re.DOTALL)
    
    assert match, "Could not find Migration 80 section"
    migration_80_code = match.group(0)
    
    # Verify it checks if 'file_downloaded' already exists
    idempotent_check = re.search(r"if\s+'file_downloaded'\s+in\s+check_clause:", migration_80_code)
    assert idempotent_check, "Migration 80 should check if 'file_downloaded' is already in constraint"
    
    # Verify it skips if already exists
    skip_message = re.search(r"'file_downloaded' already in event_type constraint - skipping", migration_80_code)
    assert skip_message, "Migration 80 should skip if 'file_downloaded' already exists"
    
    print("✅ Migration 80 is idempotent")
    print("✅ Checks if 'file_downloaded' already exists")
    print("✅ Skips if already present")


def test_no_unboundlocalerror_pattern():
    """Test that there are no patterns that could cause UnboundLocalError"""
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Find Migration 80 section
    migration_80_pattern = r'# Migration 80:.*?except Exception as e:'
    match = re.search(migration_80_pattern, content, re.DOTALL)
    
    assert match, "Could not find Migration 80 section"
    migration_80_code = match.group(0)
    
    # Make sure we don't have "result = result[0]" followed by "if constraint_row:"
    # which would cause UnboundLocalError
    bad_pattern = re.search(r'result\s*=\s*result\[0\].*?if\s+constraint_row:', migration_80_code, re.DOTALL)
    assert not bad_pattern, "Found the bug pattern: result = result[0] followed by if constraint_row:"
    
    print("✅ No UnboundLocalError patterns found in Migration 80")


if __name__ == '__main__':
    test_constraint_row_initialization()
    test_migration_80_idempotency()
    test_no_unboundlocalerror_pattern()
    print("\n🎉 All tests passed!")
