#!/usr/bin/env python3
"""
Test script to validate index separation implementation
"""
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_index_registry():
    """Test that index registry is properly configured."""
    print("Testing index registry...")
    
    from server.db_indexes import INDEX_DEFS
    
    # Check that we have indexes
    assert len(INDEX_DEFS) > 0, "INDEX_DEFS should not be empty"
    print(f"  ✅ Found {len(INDEX_DEFS)} indexes")
    
    # Verify each index has required fields
    required_fields = ['name', 'sql', 'critical', 'description']
    for idx in INDEX_DEFS:
        for field in required_fields:
            assert field in idx, f"Index missing required field: {field}"
        
        # Check that SQL contains CONCURRENTLY
        assert 'CONCURRENTLY' in idx['sql'].upper(), \
            f"Index {idx['name']} should use CONCURRENTLY"
        
        # Check that SQL contains IF NOT EXISTS
        assert 'IF NOT EXISTS' in idx['sql'].upper(), \
            f"Index {idx['name']} should use IF NOT EXISTS"
        
        print(f"  ✅ {idx['name']}: {idx['description'][:60]}...")
    
    print("  ✅ All indexes properly configured\n")


def test_migration_36_no_indexes():
    """Test that Migration 36 doesn't create indexes."""
    print("Testing Migration 36 for index removal...")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Find Migration 36 section
    migration_36_start = content.find('# Migration 36:')
    assert migration_36_start > 0, "Could not find Migration 36"
    
    # Find next migration (Migration 37 or end of file)
    migration_37_start = content.find('# Migration 37:', migration_36_start)
    if migration_37_start == -1:
        # Look for next migration or function end
        migration_end = content.find('def ', migration_36_start + 100)
        if migration_end == -1:
            migration_end = len(content)
    else:
        migration_end = migration_37_start
    
    migration_36_content = content[migration_36_start:migration_end]
    
    # Check that Migration 36 doesn't call exec_index
    assert 'exec_index' not in migration_36_content, \
        "Migration 36 should not call exec_index"
    
    # Check that it mentions the index registry
    assert 'db_indexes.py' in migration_36_content, \
        "Migration 36 should reference db_indexes.py"
    
    # Check that it mentions the specific indexes that were moved
    assert 'idx_leads_last_call_direction' in migration_36_content, \
        "Migration 36 should mention moved indexes"
    assert 'idx_call_log_lead_created' in migration_36_content, \
        "Migration 36 should mention moved indexes"
    assert 'idx_leads_backfill_pending' in migration_36_content, \
        "Migration 36 should mention moved indexes"
    
    print("  ✅ Migration 36 correctly updated (no index creation)")
    print("  ✅ Migration 36 references db_indexes.py")
    print("  ✅ Migration 36 documents moved indexes\n")


def test_migration_rules_updated():
    """Test that migration rules mention index separation."""
    print("Testing migration rules documentation...")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Check header has been updated
    header = content[:2000]  # First 2000 chars should contain the rules
    
    assert 'db_indexes.py' in header, \
        "Migration header should mention db_indexes.py"
    assert 'Performance indexes' in header or 'performance indexes' in header, \
        "Migration header should mention performance indexes"
    
    print("  ✅ Migration rules updated to mention index separation\n")


def test_indexer_service_exists():
    """Test that indexer service is defined in docker-compose.prod.yml."""
    print("Testing Docker Compose configuration...")
    
    with open('docker-compose.prod.yml', 'r') as f:
        content = f.read()
    
    # Check indexer service exists
    assert 'indexer:' in content, "indexer service should be defined"
    
    # Check it uses the correct image
    assert 'Dockerfile.backend.light' in content, \
        "indexer should use backend.light image"
    
    # Check it runs the correct command
    indexer_start = content.find('indexer:')
    indexer_end = content.find('\n  # =', indexer_start + 1)
    if indexer_end == -1:
        indexer_end = content.find('\n  db:', indexer_start + 1)
    if indexer_end == -1:
        indexer_end = len(content)
    
    indexer_section = content[indexer_start:indexer_end]
    
    assert 'db_build_indexes.py' in indexer_section, \
        "indexer should run db_build_indexes.py"
    assert 'migrate:' in indexer_section, \
        "indexer should depend on migrate"
    
    print("  ✅ Indexer service properly configured")
    print("  ✅ Depends on migrate service")
    print("  ✅ Runs db_build_indexes.py\n")


def test_deployment_script_updated():
    """Test that deployment script includes index building."""
    print("Testing deployment script...")
    
    with open('scripts/deploy_production.sh', 'r') as f:
        content = f.read()
    
    # Check that index building step exists
    assert 'Building Performance Indexes' in content or 'Building Indexes' in content, \
        "Deployment script should have index building step"
    assert 'run --rm indexer' in content, \
        "Deployment script should run indexer"
    
    # Check that more services are stopped
    assert 'prosaas-calls' in content, "Should stop prosaas-calls"
    assert 'baileys' in content, "Should stop baileys"
    
    print("  ✅ Deployment script includes index building step")
    print("  ✅ Stops all database-connected services\n")


def test_documentation_exists():
    """Test that INDEXING_GUIDE.md exists and is complete."""
    print("Testing documentation...")
    
    assert os.path.exists('INDEXING_GUIDE.md'), \
        "INDEXING_GUIDE.md should exist"
    
    with open('INDEXING_GUIDE.md', 'r') as f:
        content = f.read()
    
    # Check for key sections
    required_sections = [
        'How to Add a New Index',
        'db_indexes.py',
        'db_build_indexes.py',
        'CONCURRENTLY',
        'IF NOT EXISTS',
    ]
    
    for section in required_sections:
        assert section in content, \
            f"INDEXING_GUIDE.md should contain section: {section}"
    
    print("  ✅ INDEXING_GUIDE.md exists")
    print("  ✅ Contains all required sections\n")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Index Separation Implementation Tests")
    print("=" * 60)
    print()
    
    try:
        test_index_registry()
        test_migration_36_no_indexes()
        test_migration_rules_updated()
        test_indexer_service_exists()
        test_deployment_script_updated()
        test_documentation_exists()
        
        print("=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print()
        print("=" * 60)
        print(f"❌ Test failed: {e}")
        print("=" * 60)
        return 1
    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ Unexpected error: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
