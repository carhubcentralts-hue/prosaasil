#!/usr/bin/env python3
"""
Manual migration runner for debugging migration issues.
This script helps diagnose why migrations might not be running in production.
"""
import os
import sys

# Set environment to allow migrations
os.environ['RUN_MIGRATIONS'] = '1'
os.environ['SERVICE_ROLE'] = 'api'  # Not a worker
os.environ['MIGRATION_MODE'] = '1'
os.environ['ASYNC_LOG_QUEUE'] = '0'

print("=" * 80)
print("MANUAL MIGRATION RUNNER")
print("=" * 80)
print(f"RUN_MIGRATIONS: {os.getenv('RUN_MIGRATIONS')}")
print(f"SERVICE_ROLE: {os.getenv('SERVICE_ROLE')}")
print(f"DATABASE_URL: {'***' if os.getenv('DATABASE_URL') else 'NOT SET'}")
print("=" * 80)
print()

# Check DATABASE_URL
if not os.getenv('DATABASE_URL'):
    print("❌ ERROR: DATABASE_URL environment variable is not set!")
    print("Please set DATABASE_URL before running migrations.")
    sys.exit(1)

try:
    print("Creating Flask app context...")
    from server.app_factory import create_minimal_app
    app = create_minimal_app()
    
    print("Running migrations...")
    print()
    
    with app.app_context():
        from server.db_migrate import apply_migrations
        result = apply_migrations()
        
        if result == 'skip':
            print()
            print("=" * 80)
            print("⚠️  MIGRATIONS SKIPPED")
            print("=" * 80)
            sys.exit(1)
        else:
            print()
            print("=" * 80)
            print(f"✅ SUCCESS - Applied {len(result) if isinstance(result, list) else 0} migrations")
            print("=" * 80)
            
            # Verify critical columns
            print()
            print("Verifying critical columns...")
            from server.db import db
            from sqlalchemy import text
            
            # Check appointments.calendar_id
            result = db.session.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'appointments' AND column_name = 'calendar_id'
            """))
            if result.fetchone():
                print("  ✅ appointments.calendar_id exists")
            else:
                print("  ❌ appointments.calendar_id MISSING!")
            
            # Check scheduled message tables
            tables_to_check = ['scheduled_message_rules', 'scheduled_rule_statuses', 'scheduled_messages_queue']
            for table_name in tables_to_check:
                result = db.session.execute(text("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_name = :table_name
                """), {"table_name": table_name})
                if result.fetchone():
                    print(f"  ✅ {table_name} exists")
                else:
                    print(f"  ❌ {table_name} MISSING!")
            
            print()
            print("=" * 80)
            print("✅ VERIFICATION COMPLETE")
            print("=" * 80)
            sys.exit(0)
            
except Exception as e:
    print()
    print("=" * 80)
    print(f"❌ MIGRATION FAILED: {e}")
    print("=" * 80)
    import traceback
    traceback.print_exc()
    sys.exit(1)
