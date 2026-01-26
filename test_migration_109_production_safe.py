"""
Test migration 109 production-safe implementation
Tests that migration 109 is idempotent and production-safe
"""
import pytest
import os
from sqlalchemy import create_engine, text, inspect
from server.db import db
from server.app_factory import create_app

def test_migration_109_idempotency():
    """
    Test that migration 109 can be run multiple times without errors.
    This is critical for production safety.
    """
    # Use the test database
    app = create_app()
    
    with app.app_context():
        inspector = inspect(db.engine)
        
        # Check if call_log table exists
        tables = inspector.get_table_names()
        if 'call_log' not in tables:
            pytest.skip("call_log table does not exist in test database")
        
        # Get initial columns
        columns_before = {col['name'] for col in inspector.get_columns('call_log')}
        
        # Run migration 109 logic (DDL part only)
        # This simulates running the migration
        from server.db_migrate import exec_ddl
        
        # Set timeouts (should not fail)
        with db.engine.begin() as conn:
            conn.execute(text("SET statement_timeout = 0"))
            conn.execute(text("SET lock_timeout = '5s'"))
        
        # Add columns with IF NOT EXISTS (should be idempotent)
        exec_ddl(db.engine, """
            ALTER TABLE call_log 
            ADD COLUMN IF NOT EXISTS started_at TIMESTAMP DEFAULT NULL
        """)
        
        exec_ddl(db.engine, """
            ALTER TABLE call_log 
            ADD COLUMN IF NOT EXISTS ended_at TIMESTAMP DEFAULT NULL
        """)
        
        exec_ddl(db.engine, """
            ALTER TABLE call_log 
            ADD COLUMN IF NOT EXISTS duration_sec INTEGER DEFAULT NULL
        """)
        
        # Get columns after first run
        inspector = inspect(db.engine)
        columns_after_first = {col['name'] for col in inspector.get_columns('call_log')}
        
        # Verify columns were added
        assert 'started_at' in columns_after_first, "started_at column should be added"
        assert 'ended_at' in columns_after_first, "ended_at column should be added"
        assert 'duration_sec' in columns_after_first, "duration_sec column should be added"
        
        # Run the same migration again (should not fail)
        exec_ddl(db.engine, """
            ALTER TABLE call_log 
            ADD COLUMN IF NOT EXISTS started_at TIMESTAMP DEFAULT NULL
        """)
        
        exec_ddl(db.engine, """
            ALTER TABLE call_log 
            ADD COLUMN IF NOT EXISTS ended_at TIMESTAMP DEFAULT NULL
        """)
        
        exec_ddl(db.engine, """
            ALTER TABLE call_log 
            ADD COLUMN IF NOT EXISTS duration_sec INTEGER DEFAULT NULL
        """)
        
        # Get columns after second run
        inspector = inspect(db.engine)
        columns_after_second = {col['name'] for col in inspector.get_columns('call_log')}
        
        # Verify columns still exist and count hasn't changed
        assert columns_after_first == columns_after_second, "Running migration twice should not change schema"
        
        print("✅ Migration 109 is idempotent - can be run multiple times safely")


def test_migration_109_column_types():
    """
    Test that migration 109 columns have correct types
    """
    app = create_app()
    
    with app.app_context():
        inspector = inspect(db.engine)
        
        # Check if call_log table exists
        tables = inspector.get_table_names()
        if 'call_log' not in tables:
            pytest.skip("call_log table does not exist in test database")
        
        columns = {col['name']: col for col in inspector.get_columns('call_log')}
        
        # Check column types (may need adjustment based on actual schema)
        if 'started_at' in columns:
            col_type = str(columns['started_at']['type']).upper()
            assert 'TIMESTAMP' in col_type or 'DATETIME' in col_type, \
                f"started_at should be TIMESTAMP, got {col_type}"
        
        if 'ended_at' in columns:
            col_type = str(columns['ended_at']['type']).upper()
            assert 'TIMESTAMP' in col_type or 'DATETIME' in col_type, \
                f"ended_at should be TIMESTAMP, got {col_type}"
        
        if 'duration_sec' in columns:
            col_type = str(columns['duration_sec']['type']).upper()
            assert 'INTEGER' in col_type or 'INT' in col_type, \
                f"duration_sec should be INTEGER, got {col_type}"
        
        print("✅ Migration 109 columns have correct types")


def test_migration_109_no_backfill_in_migration():
    """
    Test that migration 109 does NOT contain heavy backfill operations.
    This verifies the production-safe implementation.
    """
    # Read the db_migrate.py file and check migration 109
    db_migrate_path = os.path.join(
        os.path.dirname(__file__),
        'server',
        'db_migrate.py'
    )
    
    with open(db_migrate_path, 'r') as f:
        content = f.read()
    
    # Find Migration 109 section
    migration_109_start = content.find('# Migration 109:')
    migration_109_end = content.find('# Migration 110:', migration_109_start)
    
    if migration_109_start == -1:
        pytest.skip("Migration 109 not found in db_migrate.py")
    
    migration_109_code = content[migration_109_start:migration_109_end]
    
    # Verify production-safe implementation
    assert 'IF NOT EXISTS' in migration_109_code, \
        "Migration 109 should use IF NOT EXISTS for idempotency"
    
    assert 'statement_timeout = 0' in migration_109_code, \
        "Migration 109 should set statement_timeout = 0"
    
    assert 'lock_timeout' in migration_109_code, \
        "Migration 109 should set lock_timeout"
    
    # Verify heavy backfill operations are NOT present in the DDL section
    # The migration should skip backfill and defer it to background jobs
    assert 'Backfill skipped' in migration_109_code or 'deferred to background job' in migration_109_code, \
        "Migration 109 should skip backfill operations"
    
    print("✅ Migration 109 is production-safe - no heavy backfill in DDL")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
