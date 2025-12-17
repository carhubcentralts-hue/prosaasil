#!/usr/bin/env python3
"""
Run migration for call duplicate fix
Adds parent_call_sid and twilio_direction fields to call_log table
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 80)
print("🔧 CALL LOG FIX MIGRATION")
print("=" * 80)
print("This migration adds:")
print("  1. parent_call_sid - track parent/child call relationships")
print("  2. twilio_direction - store original Twilio direction values")
print("=" * 80)

try:
    print("\n📦 Creating minimal app context...")
    from server.app_factory import create_minimal_app
    app = create_minimal_app()
    
    print("✅ App created successfully\n")
    
    with app.app_context():
        print("🔍 Checking database connection...")
        from server.db import db
        from sqlalchemy import text
        
        # Test connection
        result = db.session.execute(text("SELECT 1")).scalar()
        if result == 1:
            print("✅ Database connection OK\n")
        
        print("🚀 Running migrations...")
        from server.db_migrate import apply_migrations
        
        migrations = apply_migrations()
        
        print("\n" + "=" * 80)
        print(f"✅ SUCCESS - Applied {len(migrations)} migrations")
        if migrations:
            print("\nMigrations applied:")
            for m in migrations:
                print(f"  ✓ {m}")
        else:
            print("\nNo new migrations needed - database is up to date")
        print("=" * 80)
        
        # Verify new columns exist
        print("\n🔍 Verifying new columns...")
        from server.db_migrate import check_column_exists
        
        parent_exists = check_column_exists('call_log', 'parent_call_sid')
        twilio_dir_exists = check_column_exists('call_log', 'twilio_direction')
        
        if parent_exists and twilio_dir_exists:
            print("✅ Both new columns exist in database")
            
            # Count existing records
            call_count = db.session.execute(text("SELECT COUNT(*) FROM call_log")).scalar()
            print(f"📊 Total call logs in database: {call_count}")
            
            if call_count > 0:
                # Check how many have the new fields populated
                with_parent = db.session.execute(text(
                    "SELECT COUNT(*) FROM call_log WHERE parent_call_sid IS NOT NULL"
                )).scalar()
                with_twilio_dir = db.session.execute(text(
                    "SELECT COUNT(*) FROM call_log WHERE twilio_direction IS NOT NULL"
                )).scalar()
                
                print(f"📊 Calls with parent_call_sid: {with_parent}")
                print(f"📊 Calls with twilio_direction: {with_twilio_dir}")
                print("\n💡 Note: Existing calls won't have these fields.")
                print("   New calls from now on will capture this data.")
        else:
            print("⚠️ Warning: Columns not found!")
            if not parent_exists:
                print("  ❌ parent_call_sid column missing")
            if not twilio_dir_exists:
                print("  ❌ twilio_direction column missing")
        
        print("\n" + "=" * 80)
        print("✅ MIGRATION COMPLETE")
        print("=" * 80)
        print("\nNext steps:")
        print("1. Restart the server to use the new fields")
        print("2. Make test calls to verify direction tracking")
        print("3. Check that duplicate calls are filtered out")
        print("=" * 80)
        
except Exception as e:
    print("\n" + "=" * 80)
    print(f"❌ MIGRATION FAILED: {e}")
    print("=" * 80)
    import traceback
    traceback.print_exc()
    sys.exit(1)
