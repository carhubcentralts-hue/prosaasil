#!/usr/bin/env python3
"""
🔥 EMERGENCY HOTFIX: Add lead_tabs_config column to business table
This script runs DIRECTLY on PostgreSQL without Flask/SQLAlchemy overhead
Use this when the normal migration system fails

Usage:
  export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
  python migration_add_lead_tabs_config.py
"""
import os
import sys
import psycopg2
from urllib.parse import urlparse

def parse_database_url(url):
    """Parse DATABASE_URL into connection parameters"""
    result = urlparse(url)
    return {
        'database': result.path[1:],
        'user': result.username,
        'password': result.password,
        'host': result.hostname,
        'port': result.port or 5432
    }

def main():
    print("=" * 80)
    print("🔥 EMERGENCY HOTFIX: Adding lead_tabs_config to business table")
    print("=" * 80)
    
    # Get database URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ ERROR: DATABASE_URL environment variable not set")
        print("Usage: export DATABASE_URL='postgresql://...' && python migration_add_lead_tabs_config.py")
        sys.exit(1)
    
    try:
        # Parse connection parameters
        conn_params = parse_database_url(database_url)
        print(f"📍 Connecting to: {conn_params['host']}:{conn_params['port']}/{conn_params['database']}")
        
        # Connect with extended timeout
        conn = psycopg2.connect(
            **conn_params,
            connect_timeout=30,
            options='-c statement_timeout=600000'  # 10 minutes
        )
        conn.autocommit = False
        cursor = conn.cursor()
        
        # Check if column exists
        print("\n🔍 Step 1/5: Checking if column exists...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'business' 
            AND column_name = 'lead_tabs_config'
        """)
        
        if cursor.fetchone():
            print("✅ Column 'lead_tabs_config' already exists!")
            print("=" * 80)
            print("ℹ️  Nothing to do - migration already complete")
            print("=" * 80)
            cursor.close()
            conn.close()
            sys.exit(0)
        
        print("❌ Column NOT found - proceeding with migration...")
        
        # Step 1: Add column as nullable (fast)
        print("\n🔧 Step 2/5: Adding column as nullable...")
        cursor.execute("""
            ALTER TABLE business 
            ADD COLUMN lead_tabs_config JSONB
        """)
        conn.commit()
        print("✅ Column added")
        
        # Step 2: Set default value
        print("\n🔧 Step 3/5: Setting default value...")
        cursor.execute("""
            ALTER TABLE business 
            ALTER COLUMN lead_tabs_config SET DEFAULT '{}'::jsonb
        """)
        conn.commit()
        print("✅ Default value set")
        
        # Step 3: Update existing NULL rows
        print("\n🔧 Step 4/5: Updating existing rows...")
        cursor.execute("""
            UPDATE business 
            SET lead_tabs_config = '{}'::jsonb 
            WHERE lead_tabs_config IS NULL
        """)
        rows_updated = cursor.rowcount
        conn.commit()
        print(f"✅ Updated {rows_updated} rows")
        
        # Step 4: Add NOT NULL constraint
        print("\n🔧 Step 5/5: Adding NOT NULL constraint...")
        cursor.execute("""
            ALTER TABLE business 
            ALTER COLUMN lead_tabs_config SET NOT NULL
        """)
        conn.commit()
        print("✅ NOT NULL constraint added")
        
        # Verify
        print("\n🔍 Verifying column...")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'business' 
            AND column_name = 'lead_tabs_config'
        """)
        col_info = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if col_info:
            print("\n" + "=" * 80)
            print("✅ SUCCESS - Migration completed successfully!")
            print("=" * 80)
            print(f"Column Details:")
            print(f"  • Name: {col_info[0]}")
            print(f"  • Type: {col_info[1]}")
            print(f"  • Nullable: {col_info[2]}")
            print(f"  • Default: {col_info[3]}")
            print("=" * 80)
            print("\n🎉 The business.lead_tabs_config column is now ready!")
            print("   The API can now start successfully.\n")
            sys.exit(0)
        else:
            print("\n❌ VERIFICATION FAILED - Column not found after migration")
            sys.exit(1)
            
    except psycopg2.OperationalError as e:
        print("\n" + "=" * 80)
        print(f"❌ DATABASE CONNECTION ERROR")
        print("=" * 80)
        print(f"Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Check DATABASE_URL is correct")
        print("  2. Verify database server is accessible")
        print("  3. Check firewall / security group settings")
        print("  4. Ensure credentials are valid")
        sys.exit(1)
        
    except psycopg2.errors.QueryCanceled as e:
        print("\n" + "=" * 80)
        print(f"❌ QUERY TIMEOUT")
        print("=" * 80)
        print(f"Error: {e}")
        print("\nThe ALTER TABLE command took too long (>10 minutes)")
        print("Possible causes:")
        print("  1. business table is very large (millions of rows)")
        print("  2. Table has locks from other transactions")
        print("  3. Database is under heavy load")
        print("\nSolutions:")
        print("  1. Run during low-traffic period")
        print("  2. Check for blocking queries: SELECT * FROM pg_locks WHERE NOT granted;")
        print("  3. Increase timeout in script (edit line 39)")
        sys.exit(1)
        
    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ UNEXPECTED ERROR")
        print("=" * 80)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()

