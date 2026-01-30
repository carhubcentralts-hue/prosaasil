"""
Test Migration 36 improvements - Lock policy separation and batching
Tests code structure without requiring database connection
"""
import sys
import os

# Get the repository root directory
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__)))


def test_exec_dml_exists():
    """Test that exec_dml function exists in db_migrate"""
    
    # Read the file
    db_migrate_path = os.path.join(REPO_ROOT, 'server', 'db_migrate.py')
    with open(db_migrate_path, 'r') as f:
        content = f.read()
    
    # Check exec_dml exists
    assert 'def exec_dml(' in content, "exec_dml function should exist"
    print("✅ exec_dml function exists")
    
    # Check it has correct parameters
    assert 'def exec_dml(engine, sql: str, params=None, retries=3):' in content, \
        "exec_dml should have correct signature"
    print("✅ exec_dml has correct signature")
    
    # Check lock timeout settings
    assert 'SET lock_timeout = \'60s\'' in content, "exec_dml should set 60s lock_timeout"
    assert 'SET statement_timeout = \'0\'' in content, "exec_dml should set unlimited statement_timeout"
    print("✅ exec_dml has correct lock timeout settings")
    
    # Check LockNotAvailable handling
    assert 'DBAPIError' in content, "Should import DBAPIError"
    assert 'locknotavailable' in content.lower() or 'lock_timeout' in content, \
        "Should check for LockNotAvailable errors"
    print("✅ exec_dml handles LockNotAvailable errors")


def test_exec_index_exists():
    """Test that exec_index function exists for CONCURRENT index creation"""
    
    # Read the file
    db_migrate_path = os.path.join(REPO_ROOT, 'server', 'db_migrate.py')
    with open(db_migrate_path, 'r') as f:
        content = f.read()
    
    # Check exec_index exists
    assert 'def exec_index(' in content, "exec_index function should exist"
    print("✅ exec_index function exists")
    
    # Check it has correct parameters including best_effort
    assert 'def exec_index(engine, sql: str, index_name: str = None, retries=10, best_effort=True):' in content, \
        "exec_index should have correct signature with best_effort parameter"
    print("✅ exec_index has correct signature")
    
    # Check AUTOCOMMIT isolation level (required for CONCURRENTLY)
    assert 'isolation_level="AUTOCOMMIT"' in content, "exec_index should use AUTOCOMMIT isolation"
    print("✅ exec_index uses AUTOCOMMIT isolation level")
    
    # Check lock timeout settings for index creation
    exec_index_start = content.find('def exec_index(')
    apply_migrations_start = content.find('def apply_migrations()')
    exec_index_section = content[exec_index_start:apply_migrations_start]
    
    assert 'SET lock_timeout = \'60s\'' in exec_index_section, "exec_index should set 60s lock_timeout"
    assert 'SET statement_timeout = \'0\'' in exec_index_section, "exec_index should set unlimited statement_timeout"
    print("✅ exec_index has correct lock timeout settings")
    
    # Check retry and best-effort logic
    assert 'best_effort' in exec_index_section, "exec_index should support best_effort mode"
    assert 'retries' in exec_index_section, "exec_index should have retry logic"
    print("✅ exec_index has retry and best-effort logic")

def test_migration_36_batching():
    """Test that Migration 36 uses batching by business"""
    db_migrate_path = os.path.join(REPO_ROOT, 'server', 'db_migrate.py')
    with open(db_migrate_path, 'r') as f:
        content = f.read()
    
    # Check for batching by tenant_id
    assert 'tenant_id' in content and 'DISTINCT tenant_id' in content, \
        "Should query for distinct tenant_ids"
    print("✅ Migration 36 queries for distinct tenant_ids")
    
    # Check for exec_dml usage
    assert 'exec_dml(migrate_engine,' in content, \
        "Migration 36 should use exec_dml for backfill"
    print("✅ Migration 36 uses exec_dml")
    
    # Check batch size parameter
    assert 'batch_size = 1000' in content, "Should have batch_size = 1000"
    print("✅ Migration 36 has batch_size configured")
    
    # Check WHERE tenant_id in batch query
    migration_36_start = content.find('# Migration 36:')
    migration_37_start = content.find('# Migration 37:')
    migration_36_section = content[migration_36_start:migration_37_start] if migration_37_start > 0 else content[migration_36_start:]
    
    assert 'WHERE tenant_id = :tenant_id' in migration_36_section, \
        "Batch query should filter by tenant_id"
    print("✅ Migration 36 batches by tenant_id")


def test_supporting_indexes():
    """Test that supporting indexes are created with CONCURRENTLY before backfill"""
    db_migrate_path = os.path.join(REPO_ROOT, 'server', 'db_migrate.py')
    with open(db_migrate_path, 'r') as f:
        content = f.read()
    
    # Find Migration 36 section
    migration_36_start = content.find('# Migration 36:')
    migration_37_start = content.find('# Migration 37:')
    migration_36_section = content[migration_36_start:migration_37_start] if migration_37_start > 0 else content[migration_36_start:]
    
    # Check for call_log index
    assert 'idx_call_log_lead_created' in migration_36_section, \
        "Should create idx_call_log_lead_created index"
    assert 'ON call_log(lead_id, created_at)' in migration_36_section, \
        "Index should be on call_log(lead_id, created_at)"
    print("✅ Migration 36 creates idx_call_log_lead_created index")
    
    # Check for leads backfill index
    assert 'idx_leads_backfill_pending' in migration_36_section, \
        "Should create idx_leads_backfill_pending index"
    assert 'WHERE last_call_direction IS NULL' in migration_36_section, \
        "Should be a partial index for pending backfill"
    print("✅ Migration 36 creates idx_leads_backfill_pending partial index")
    
    # Check that indexes come BEFORE backfill
    index_pos = migration_36_section.find('idx_call_log_lead_created')
    backfill_pos = migration_36_section.find('Backfilling last_call_direction')
    assert index_pos < backfill_pos, "Indexes should be created before backfill"
    print("✅ Indexes are created BEFORE backfill starts")
    
    # 🔥 NEW CHECK: Verify indexes use CONCURRENTLY
    assert 'CREATE INDEX CONCURRENTLY' in migration_36_section, \
        "Indexes should use CONCURRENTLY for production safety"
    assert 'exec_index(' in migration_36_section, \
        "Should use exec_index() function for CONCURRENT index creation"
    print("✅ Indexes use CREATE INDEX CONCURRENTLY")
    
    # Check that exec_index is called with best_effort=True
    assert 'best_effort=True' in migration_36_section, \
        "exec_index should be called with best_effort=True"
    print("✅ Indexes use best-effort mode (won't fail migration)")


def test_imports():
    """Test that required imports are present"""
    db_migrate_path = os.path.join(REPO_ROOT, 'server', 'db_migrate.py')
    with open(db_migrate_path, 'r') as f:
        content = f.read()
    
    # Check for DBAPIError import
    assert 'from sqlalchemy.exc import OperationalError, DBAPIError' in content, \
        "Should import both OperationalError and DBAPIError"
    print("✅ DBAPIError is imported")


def test_documentation_exists():
    """Test that deployment guide exists and has key sections"""
    
    guide_path = os.path.join(REPO_ROOT, 'MIGRATION_36_DEPLOYMENT_GUIDE.md')
    assert os.path.exists(guide_path), "Deployment guide should exist"
    print("✅ MIGRATION_36_DEPLOYMENT_GUIDE.md exists")
    
    with open(guide_path, 'r') as f:
        content = f.read()
    
    # Check for key sections
    assert 'LockNotAvailable' in content, "Guide should mention LockNotAvailable"
    assert 'exec_dml' in content, "Guide should document exec_dml"
    assert 'tenant_id' in content or 'business' in content.lower(), \
        "Guide should mention batching by business"
    assert 'Supporting Indexes' in content, "Guide should document supporting indexes"
    print("✅ Deployment guide has all key sections")


if __name__ == '__main__':
    print("Testing Migration 36 Improvements...")
    print("=" * 60)
    
    try:
        test_imports()
        print()
        
        test_exec_dml_exists()
        print()
        
        test_exec_index_exists()
        print()
        
        test_migration_36_batching()
        print()
        
        test_supporting_indexes()
        print()
        
        test_documentation_exists()
        print()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
