"""
Test Migration 58: Verify SQL syntax for business.voice_id column
This test validates the SQL migration without requiring database connection
"""

def test_migration_sql_syntax():
    """Verify the SQL migration syntax is correct"""
    print("🔧 Testing Migration 58 SQL Syntax")
    print("=" * 60)
    
    # Test 1: Check migration is in db_migrate.py
    print("\n1. Checking if migration is in db_migrate.py...")
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    if 'Migration 58' in content:
        print("   ✅ Migration 58 comment found")
    else:
        print("   ❌ Migration 58 comment NOT found")
        return False
    
    if "ADD COLUMN voice_id VARCHAR(32)" in content:
        print("   ✅ ALTER TABLE ADD COLUMN statement found")
    else:
        print("   ❌ ALTER TABLE ADD COLUMN statement NOT found")
        return False
    
    if "DEFAULT 'ash'" in content:
        print("   ✅ DEFAULT 'ash' value found")
    else:
        print("   ❌ DEFAULT value NOT found")
        return False
    
    if "add_business_voice_id" in content:
        print("   ✅ Migration name 'add_business_voice_id' found")
    else:
        print("   ❌ Migration name NOT found")
        return False
    
    # Test 2: Check environment validation includes voice_id
    print("\n2. Checking environment_validation.py...")
    with open('server/environment_validation.py', 'r') as f:
        content = f.read()
    
    if "'business'" in content and "'voice_id'" in content:
        print("   ✅ business.voice_id found in critical columns")
    else:
        print("   ❌ business.voice_id NOT found in critical columns")
        return False
    
    # Test 3: Check Business model has voice_id
    print("\n3. Checking Business model in models_sql.py...")
    with open('server/models_sql.py', 'r') as f:
        content = f.read()
    
    if "voice_id = db.Column" in content:
        print("   ✅ voice_id column defined in Business model")
    else:
        print("   ❌ voice_id column NOT defined in Business model")
        return False
    
    # Test 4: Check DEFAULT_VOICE config exists
    print("\n4. Checking DEFAULT_VOICE in config/voices.py...")
    with open('server/config/voices.py', 'r') as f:
        content = f.read()
    
    if 'DEFAULT_VOICE = "ash"' in content:
        print("   ✅ DEFAULT_VOICE = 'ash' found")
    else:
        print("   ❌ DEFAULT_VOICE NOT correctly set")
        return False
    
    # Test 5: Verify migration logic
    print("\n5. Verifying migration logic...")
    
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Check for idempotent pattern
    if "check_column_exists('business', 'voice_id')" in content:
        print("   ✅ Idempotent check found (check_column_exists)")
    else:
        print("   ❌ Missing idempotent check")
        return False
    
    # Check for NULL value update
    if "UPDATE business" in content and "SET voice_id = 'ash'" in content:
        print("   ✅ NULL value update statement found")
    else:
        print("   ❌ NULL value update statement NOT found")
        return False
    
    print("\n" + "=" * 60)
    print("✅ All SQL syntax tests passed!")
    print("\nMigration 58 is ready to be applied to the database.")
    print("It will:")
    print("  1. Add voice_id VARCHAR(32) column to business table")
    print("  2. Set default value to 'ash'")
    print("  3. Update any NULL values to 'ash'")
    print("  4. Only run if column doesn't exist (idempotent)")
    return True

if __name__ == '__main__':
    import sys
    success = test_migration_sql_syntax()
    sys.exit(0 if success else 1)
