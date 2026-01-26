"""
Test lead_tabs_config migration and schema validation
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_migration_112_uses_jsonb():
    """Verify Migration 112 uses JSONB type with proper default"""
    from server.app_factory import get_process_app
    
    app = get_process_app()
    with app.app_context():
        from server.db import db
        from sqlalchemy import text
        
        # Check if column exists
        result = db.session.execute(text("""
            SELECT column_name, data_type, column_default, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'business' AND column_name = 'lead_tabs_config'
        """))
        
        column_info = result.fetchone()
        
        if column_info:
            column_name, data_type, column_default, is_nullable = column_info
            print(f"✅ Column exists: {column_name}")
            print(f"   Type: {data_type}")
            print(f"   Default: {column_default}")
            print(f"   Nullable: {is_nullable}")
            
            # Verify it's JSONB (not JSON)
            assert data_type == 'jsonb', f"Expected JSONB type, got {data_type}"
            
            # Verify it has a default
            assert column_default is not None, "Expected default value"
            
            # Verify it's NOT NULL
            assert is_nullable == 'NO', "Expected NOT NULL constraint"
        else:
            print("⚠️  Column does not exist yet - migration needs to run")

def test_critical_columns_includes_lead_tabs_config():
    """Verify lead_tabs_config is in CRITICAL_COLUMNS"""
    from server.environment_validation import CRITICAL_COLUMNS
    
    assert 'business' in CRITICAL_COLUMNS, "business table should be in CRITICAL_COLUMNS"
    assert 'lead_tabs_config' in CRITICAL_COLUMNS['business'], \
        "lead_tabs_config should be in business CRITICAL_COLUMNS"
    
    print("✅ lead_tabs_config is in CRITICAL_COLUMNS")

def test_twilio_route_has_db_protection():
    """Verify incoming_call route has DB error protection"""
    import inspect
    from server.routes_twilio import incoming_call
    
    # Get the source code of the function
    source = inspect.getsource(incoming_call)
    
    # Verify it imports sqlalchemy.exc
    assert 'sqlalchemy.exc' in source, \
        "incoming_call should import sqlalchemy.exc"
    
    # Verify it has try/except for Business query
    assert 'try:' in source and 'except' in source, \
        "incoming_call should have try/except protection"
    
    # Verify it catches ProgrammingError
    assert 'ProgrammingError' in source, \
        "incoming_call should catch ProgrammingError"
    
    # Verify it returns TwiML on error
    assert 'VoiceResponse' in source and 'return str(vr)' in source, \
        "incoming_call should return TwiML on error"
    
    print("✅ incoming_call has DB error protection with TwiML fallback")

def test_ensure_db_ready_checks_lead_tabs_config():
    """Verify ensure_db_ready checks for lead_tabs_config column"""
    import inspect
    from server.app_factory import ensure_db_ready
    
    # Get the source code
    source = inspect.getsource(ensure_db_ready)
    
    # Verify it checks for lead_tabs_config
    assert 'lead_tabs_config' in source, \
        "ensure_db_ready should check for lead_tabs_config column"
    
    print("✅ ensure_db_ready checks for lead_tabs_config column")

def test_migrations_enabled_by_default():
    """Verify migrations are enabled by default (RUN_MIGRATIONS defaults to '1')"""
    import inspect
    from server.db_migrate import apply_migrations
    
    # Get the source code
    source = inspect.getsource(apply_migrations)
    
    # Verify RUN_MIGRATIONS defaults to '1' (enabled)
    # This ensures migrations run automatically unless explicitly disabled
    assert "RUN_MIGRATIONS', '1')" in source or "RUN_MIGRATIONS\", '1')" in source, \
        "RUN_MIGRATIONS should default to '1' (enabled)"
    
    # Verify worker check comes before RUN_MIGRATIONS check
    worker_check_pos = source.find("service_role")
    run_migrations_check_pos = source.find("RUN_MIGRATIONS")
    
    assert worker_check_pos < run_migrations_check_pos, \
        "Worker check should come before RUN_MIGRATIONS check"
    
    print("✅ Migrations enabled by default, worker check is first")

if __name__ == '__main__':
    print("Testing lead_tabs_config migration and protections...")
    print()
    
    try:
        test_critical_columns_includes_lead_tabs_config()
        test_twilio_route_has_db_protection()
        test_ensure_db_ready_checks_lead_tabs_config()
        test_migrations_enabled_by_default()
        print()
        print("Testing actual migration (requires DB connection)...")
        test_migration_112_uses_jsonb()
        print()
        print("✅ All tests passed!")
    except AssertionError as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
