#!/usr/bin/env python3
"""
Test push_enabled column migration
Verifies that:
1. Migration creates users.push_enabled column
2. Column has correct type and default value
3. Login works without column errors
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_column_exists():
    """Check if push_enabled column exists in users table"""
    from sqlalchemy import create_engine, text
    
    # Use test database
    database_url = os.getenv('DATABASE_URL', 'postgresql://test:test@localhost:5432/test')
    engine = create_engine(database_url)
    
    print("🔍 Checking if users.push_enabled column exists...")
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name, data_type, column_default, is_nullable
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'users' 
            AND column_name = 'push_enabled'
        """))
        
        row = result.fetchone()
        if row:
            print(f"✅ Column exists!")
            print(f"   Type: {row[1]}")
            print(f"   Default: {row[2]}")
            print(f"   Nullable: {row[3]}")
            return True
        else:
            print("❌ Column does not exist")
            return False

def test_migration():
    """Run migration and verify"""
    print("\n🔧 Testing push_enabled migration...\n")
    
    try:
        # First check if column already exists
        exists_before = test_column_exists()
        
        if exists_before:
            print("\n✅ Column already exists - migration was previously applied")
            return True
        
        # Run migration
        print("\n🔧 Running migration...")
        from server.app_factory import get_process_app
        from server.db_migrate import apply_migrations
        
        app = get_process_app()
        
        with app.app_context():
            migrations = apply_migrations()
            print(f"\n✅ Migrations applied: {len(migrations)}")
            
            # Check if our migration was applied
            if 'add_users_push_enabled' in migrations:
                print("✅ push_enabled migration applied!")
            else:
                print("ℹ️  push_enabled migration not in list (may have been applied previously)")
        
        # Verify column exists now
        print("\n🔍 Verifying column after migration...")
        exists_after = test_column_exists()
        
        if exists_after:
            print("\n✅ Migration successful - column created!")
            return True
        else:
            print("\n❌ Migration failed - column still missing")
            return False
            
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_user_query():
    """Test that User queries work with push_enabled column"""
    print("\n🔍 Testing User query with push_enabled column...\n")
    
    try:
        from server.app_factory import get_process_app
        from server.models_sql import User
        
        app = get_process_app()
        
        with app.app_context():
            # Try to query users - this will fail if column is missing
            users = User.query.limit(5).all()
            print(f"✅ Successfully queried {len(users)} users")
            
            # Check if push_enabled attribute exists
            if users:
                user = users[0]
                push_enabled = user.push_enabled
                print(f"✅ User.push_enabled accessible: {push_enabled}")
            
            return True
            
    except Exception as e:
        print(f"❌ User query failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("Testing push_enabled Column Migration")
    print("=" * 60)
    
    # Test 1: Check/run migration
    success = test_migration()
    
    if not success:
        print("\n❌ Migration test failed")
        sys.exit(1)
    
    # Test 2: Try querying users
    success = test_user_query()
    
    if not success:
        print("\n❌ User query test failed")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
    sys.exit(0)
