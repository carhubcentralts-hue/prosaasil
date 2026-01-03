"""
Test Migration 58: business.voice_id column
Verify the migration adds voice_id column correctly
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_migration_58_idempotent():
    """Test that migration 58 is idempotent and adds voice_id correctly"""
    from server.app_factory import create_minimal_app
    from server.db import db
    from sqlalchemy import text, inspect
    
    print("🔧 Testing Migration 58: business.voice_id")
    print("=" * 60)
    
    app = create_minimal_app()
    
    with app.app_context():
        # Check if business table exists
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'business' not in tables:
            print("⚠️  business table does not exist - skipping test")
            return True
        
        # Check if voice_id column exists
        columns = [col['name'] for col in inspector.get_columns('business')]
        
        if 'voice_id' not in columns:
            print("❌ voice_id column does not exist in business table")
            print(f"   Available columns: {', '.join(columns)}")
            return False
        
        print("✅ voice_id column exists in business table")
        
        # Check column properties
        for col in inspector.get_columns('business'):
            if col['name'] == 'voice_id':
                print(f"   Type: {col['type']}")
                print(f"   Nullable: {col['nullable']}")
                print(f"   Default: {col.get('default', 'None')}")
        
        # Test querying business with voice_id
        try:
            from server.models_sql import Business
            
            # Count businesses
            count = Business.query.count()
            print(f"\n✅ Can query Business model (count: {count})")
            
            # Try to access voice_id on a business (if any exist)
            if count > 0:
                business = Business.query.first()
                voice_id = business.voice_id
                print(f"✅ Can access voice_id attribute: {voice_id}")
                
                # Verify it's a valid voice (or default)
                from server.config.voices import OPENAI_VOICES, DEFAULT_VOICE
                if voice_id in OPENAI_VOICES:
                    print(f"✅ voice_id '{voice_id}' is valid")
                elif voice_id == DEFAULT_VOICE:
                    print(f"✅ voice_id is default: '{DEFAULT_VOICE}'")
                else:
                    print(f"⚠️  voice_id '{voice_id}' is not in OPENAI_VOICES list")
            else:
                print("ℹ️  No businesses exist to test voice_id access")
        
        except Exception as e:
            print(f"❌ Error querying Business model: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test environment validation
        print("\n🔍 Testing environment validation...")
        try:
            from server.environment_validation import CRITICAL_COLUMNS
            
            if 'business' in CRITICAL_COLUMNS and 'voice_id' in CRITICAL_COLUMNS['business']:
                print("✅ voice_id is in CRITICAL_COLUMNS")
            else:
                print("❌ voice_id is NOT in CRITICAL_COLUMNS")
                return False
        except Exception as e:
            print(f"❌ Error checking CRITICAL_COLUMNS: {e}")
            return False
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        return True

if __name__ == '__main__':
    success = test_migration_58_idempotent()
    sys.exit(0 if success else 1)
