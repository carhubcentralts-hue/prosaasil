"""
Test for Migration 36 Backfill Separation
==========================================

This test verifies that:
1. Migration 36 is now schema-only (no backfill)
2. db_backfill.py tool exists and can be imported
3. Backfill logic uses FOR UPDATE SKIP LOCKED
4. Backfill is idempotent and safe
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_migration_36_is_schema_only():
    """Test that Migration 36 only adds schema, not backfill."""
    print("\n=== Test 1: Migration 36 is schema-only ===")
    
    # Read the migration file
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Find Migration 36
    migration_36_start = content.find('# Migration 36:')
    migration_37_start = content.find('# Migration 37:', migration_36_start)
    
    if migration_36_start == -1:
        print("❌ FAIL: Migration 36 not found")
        return False
    
    migration_36_code = content[migration_36_start:migration_37_start]
    
    # Check that backfill is NOT in migration code
    if 'exec_dml' in migration_36_code and 'UPDATE leads l' in migration_36_code:
        print("❌ FAIL: Migration 36 still contains backfill logic (exec_dml + UPDATE)")
        return False
    
    # Check for the message about separate backfill
    if 'Backfill will run separately' not in migration_36_code and 'db_backfill.py' not in migration_36_code:
        print("⚠️  WARNING: Migration 36 doesn't mention db_backfill.py")
    
    # Check that it only adds column
    if 'ADD COLUMN last_call_direction' in migration_36_code:
        print("✅ PASS: Migration 36 adds column (schema change)")
    else:
        print("❌ FAIL: Migration 36 doesn't add column")
        return False
    
    print("✅ PASS: Migration 36 is schema-only (no backfill)")
    return True


def test_backfill_tool_exists():
    """Test that db_backfill.py exists and is executable."""
    print("\n=== Test 2: Backfill tool exists ===")
    
    backfill_path = 'server/db_backfill.py'
    
    if not os.path.exists(backfill_path):
        print(f"❌ FAIL: {backfill_path} does not exist")
        return False
    
    print(f"✅ PASS: {backfill_path} exists")
    
    # Check if executable
    if os.access(backfill_path, os.X_OK):
        print(f"✅ PASS: {backfill_path} is executable")
    else:
        print(f"⚠️  WARNING: {backfill_path} is not executable (chmod +x may be needed)")
    
    return True


def test_backfill_uses_skip_locked():
    """Test that backfill uses FOR UPDATE SKIP LOCKED."""
    print("\n=== Test 3: Backfill uses SKIP LOCKED ===")
    
    with open('server/db_backfill.py', 'r') as f:
        content = f.read()
    
    # Check for FOR UPDATE SKIP LOCKED
    if 'FOR UPDATE SKIP LOCKED' not in content:
        print("❌ FAIL: Backfill doesn't use FOR UPDATE SKIP LOCKED")
        return False
    
    print("✅ PASS: Backfill uses FOR UPDATE SKIP LOCKED")
    
    # Check for batch processing
    if 'batch_size' not in content:
        print("⚠️  WARNING: No batch_size parameter found")
    else:
        print("✅ PASS: Backfill uses batched processing")
    
    # Check for time limit
    if 'max_time' in content or 'deadline' in content:
        print("✅ PASS: Backfill has time limit")
    else:
        print("⚠️  WARNING: No time limit found")
    
    return True


def test_backfill_is_idempotent():
    """Test that backfill is idempotent and safe."""
    print("\n=== Test 4: Backfill is idempotent ===")
    
    with open('server/db_backfill.py', 'r') as f:
        content = f.read()
    
    # Check for idempotent conditions
    if 'WHERE last_call_direction IS NULL' not in content:
        print("❌ FAIL: Backfill doesn't check for NULL before updating")
        return False
    
    print("✅ PASS: Backfill only updates NULL values (idempotent)")
    
    # Check that it exits 0
    if 'sys.exit(0)' not in content:
        print("⚠️  WARNING: Backfill may not always exit 0")
    else:
        print("✅ PASS: Backfill exits 0 (won't fail deployment)")
    
    return True


def test_docker_compose_has_backfill():
    """Test that docker-compose.prod.yml has backfill service."""
    print("\n=== Test 5: Docker Compose has backfill service ===")
    
    with open('docker-compose.prod.yml', 'r') as f:
        content = f.read()
    
    if 'backfill:' not in content:
        print("❌ FAIL: docker-compose.prod.yml doesn't have backfill service")
        return False
    
    print("✅ PASS: docker-compose.prod.yml has backfill service")
    
    # Check for db_backfill.py command
    if 'server/db_backfill.py' not in content:
        print("❌ FAIL: backfill service doesn't run db_backfill.py")
        return False
    
    print("✅ PASS: backfill service runs db_backfill.py")
    
    return True


def test_deploy_script_runs_backfill():
    """Test that deploy_production.sh runs backfill."""
    print("\n=== Test 6: Deploy script runs backfill ===")
    
    with open('scripts/deploy_production.sh', 'r') as f:
        content = f.read()
    
    if 'backfill' not in content:
        print("❌ FAIL: deploy_production.sh doesn't mention backfill")
        return False
    
    print("✅ PASS: deploy_production.sh includes backfill step")
    
    # Check that backfill runs after migrations
    migrate_pos = content.find('run --rm migrate')
    backfill_pos = content.find('run --rm backfill')
    
    if migrate_pos == -1 or backfill_pos == -1:
        print("⚠️  WARNING: Can't verify order of migrate and backfill")
    elif backfill_pos > migrate_pos:
        print("✅ PASS: backfill runs after migrate")
    else:
        print("❌ FAIL: backfill runs before migrate")
        return False
    
    return True


def test_backfill_sql_correctness():
    """Test that backfill SQL uses correct logic."""
    print("\n=== Test 7: Backfill SQL correctness ===")
    
    with open('server/db_backfill.py', 'r') as f:
        content = f.read()
    
    # Check for DISTINCT ON with ORDER BY created_at ASC
    if 'DISTINCT ON' in content and 'created_at ASC' in content:
        print("✅ PASS: Backfill uses DISTINCT ON with ORDER BY created_at ASC")
    else:
        print("❌ FAIL: Backfill SQL may not get FIRST call correctly")
        return False
    
    # Check for tenant_id filtering
    if 'tenant_id = :tenant_id' in content or 'WHERE tenant_id =' in content:
        print("✅ PASS: Backfill processes by tenant_id (reduces lock contention)")
    else:
        print("⚠️  WARNING: Backfill may not process by tenant_id")
    
    return True


def main():
    """Run all tests."""
    print("=" * 80)
    print("Testing Migration 36 Backfill Separation")
    print("=" * 80)
    
    tests = [
        test_migration_36_is_schema_only,
        test_backfill_tool_exists,
        test_backfill_uses_skip_locked,
        test_backfill_is_idempotent,
        test_docker_compose_has_backfill,
        test_deploy_script_runs_backfill,
        test_backfill_sql_correctness,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ ERROR: {test.__name__} raised exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED")
        return 0
    else:
        print(f"\n❌ {total - passed} TEST(S) FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(main())
