"""
Test that Migration 112 fix addresses the timeout and incorrect success marking issues.
"""
import re

def test_migration_112_success_inside_try_block():
    """Verify that success checkpoint is inside the try block and NOT after except"""
    with open('server/db_migrate.py', 'r') as f:
        lines = f.readlines()
    
    # Find Migration 112 section
    migration_start_line = None
    for i, line in enumerate(lines):
        if '# Migration 112:' in line:
            migration_start_line = i
            break
    
    assert migration_start_line is not None, "Migration 112 not found"
    
    # Find the try, except, and checkpoint lines
    try_line = None
    except_line = None
    rollback_line = None
    success_checkpoint_lines = []
    else_line = None
    
    for i in range(migration_start_line, min(len(lines), migration_start_line + 100)):
        if 'try:' in lines[i] and try_line is None:
            try_line = i
        if 'except Exception as e:' in lines[i]:
            except_line = i
        if 'db.session.rollback()' in lines[i] and except_line and i > except_line:
            rollback_line = i
        if '✅ Migration 112 complete:' in lines[i]:
            success_checkpoint_lines.append(i)
        if 'else:' in lines[i] and 'business table does not exist' in lines[i+1] if i+1 < len(lines) else False:
            else_line = i
    
    assert try_line is not None, f"try block not found (searched from line {migration_start_line})"
    assert except_line is not None, "except block not found"
    assert rollback_line is not None, "rollback not found"
    assert len(success_checkpoint_lines) > 0, "Success checkpoint not found"
    
    # The key check: Verify NO success checkpoint exists AFTER rollback but BEFORE else clause
    # (this would mean it's after the except block but not in else clause)
    for checkpoint_line in success_checkpoint_lines:
        if rollback_line < checkpoint_line < (else_line if else_line else float('inf')):
            # This checkpoint is after rollback - is it in the else clause?
            if else_line is None or checkpoint_line < else_line:
                raise AssertionError(
                    f"Success checkpoint at line {checkpoint_line+1} is AFTER except block (rollback at {rollback_line+1}) "
                    f"but BEFORE/WITHOUT else clause. This means migration always marks as complete even on failure!"
                )
    
    # Verify there ARE success checkpoints inside the try block (between try and except)
    checkpoints_in_try = [line for line in success_checkpoint_lines if try_line < line < except_line]
    assert len(checkpoints_in_try) > 0, "No success checkpoints found inside try block"
    
    # Verify there's a comment about not marking as complete on failure
    found_comment = False
    for i in range(except_line, min(len(lines), except_line + 10)):
        if 'Do NOT mark as complete' in lines[i]:
            found_comment = True
            break
    assert found_comment, "Comment about not marking as complete on failure not found"
    
    print("✅ Success checkpoint is correctly placed inside try block, NOT after except")
    print(f"   - Try block at line {try_line+1}")
    print(f"   - Except block at line {except_line+1}")
    print(f"   - Success checkpoints inside try: lines {[l+1 for l in checkpoints_in_try]}")

def test_migration_112_uses_three_step_approach():
    """Verify that Migration 112 uses the optimized 3-step approach"""
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Find Migration 112 section
    migration_112_start = content.find('# Migration 112:')
    migration_section = content[migration_112_start:migration_112_start + 5000]  # Increased size
    
    # Check for the 3-step approach markers
    assert 'Step 1/3' in migration_section, "Step 1/3 marker not found"
    assert 'Step 2/3' in migration_section, "Step 2/3 marker not found"
    assert 'Step 3/3' in migration_section, "Step 3/3 marker not found"
    
    # Verify Step 1: Add column as nullable (no NOT NULL in first ALTER)
    step1_pattern = r'Step 1.*?ADD COLUMN.*?lead_tabs_config JSONB\s*\n'
    match = re.search(step1_pattern, migration_section, re.DOTALL)
    assert match, "Step 1 should add column as nullable"
    # Make sure this ADD COLUMN doesn't have NOT NULL
    add_column_stmt = match.group(0)
    assert 'NOT NULL' not in add_column_stmt, "Step 1 ADD COLUMN should not have NOT NULL"
    
    # Verify Step 2: Set default
    assert 'SET DEFAULT' in migration_section, "Step 2 should set default"
    assert "'{}'::jsonb" in migration_section, "Default should be empty JSON object"
    
    # Verify Step 3: Update + NOT NULL
    assert 'UPDATE business' in migration_section, "Step 3 should update existing rows"
    assert 'SET NOT NULL' in migration_section, "Step 3 should add NOT NULL constraint"
    
    print("✅ Migration 112 uses optimized 3-step approach")

def test_migration_112_no_combined_not_null_default():
    """Verify that the problematic combined NOT NULL DEFAULT is removed"""
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Find Migration 112 section
    migration_112_start = content.find('# Migration 112:')
    migration_section = content[migration_112_start:migration_112_start + 5000]  # Increased size
    
    # Check that we don't have the problematic pattern anymore
    problematic_pattern = r'ADD COLUMN.*?NOT NULL DEFAULT.*?jsonb'
    assert not re.search(problematic_pattern, migration_section, re.IGNORECASE), \
        "Migration 112 should not use combined NOT NULL DEFAULT in ADD COLUMN"
    
    print("✅ Problematic combined NOT NULL DEFAULT pattern is removed")

def test_migration_112_comment_on_failure():
    """Verify that there's a comment indicating no completion on failure"""
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Find Migration 112 section
    migration_112_start = content.find('# Migration 112:')
    migration_section = content[migration_112_start:migration_112_start + 5000]  # Increased size
    
    # Check for explicit comment about not marking complete on failure
    # The comment should be in the except block
    assert 'Do NOT mark as complete on failure' in migration_section or \
           'do not mark as complete on failure' in migration_section, \
        "Should have comment about not marking as complete on failure"
    
    print("✅ Comment about not marking complete on failure is present")

def test_migration_112_optimized_message():
    """Verify that migration mentions optimization for large tables"""
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Find Migration 112 section
    migration_112_start = content.find('# Migration 112:')
    migration_section = content[migration_112_start:migration_112_start + 5000]  # Increased size
    
    # Check for optimization message
    assert 'optimized for large tables' in migration_section.lower(), \
        "Migration should mention optimization for large tables"
    
    print("✅ Migration mentions optimization for large tables")

if __name__ == '__main__':
    print("Testing Migration 112 fix...")
    print()
    
    try:
        test_migration_112_success_inside_try_block()
        test_migration_112_uses_three_step_approach()
        test_migration_112_no_combined_not_null_default()
        test_migration_112_comment_on_failure()
        test_migration_112_optimized_message()
        print()
        print("✅ All Migration 112 fix tests passed!")
        print()
        print("Summary of fixes:")
        print("1. Success checkpoint moved inside try block")
        print("2. Optimized 3-step approach to avoid table rewrite")
        print("3. Removed problematic combined NOT NULL DEFAULT")
        print("4. Added explicit comment about not marking as complete on failure")
        print("5. Added user-visible optimization message")
    except AssertionError as e:
        print(f"❌ Test failed: {e}")
        import sys
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        import sys
        sys.exit(1)
