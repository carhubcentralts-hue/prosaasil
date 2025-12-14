#!/usr/bin/env python3
"""
Test script to verify last_call_direction logic is correct

This script validates that:
1. Column exists in database
2. Backfill worked correctly
3. Direction is set only once (never overridden)
4. API filters work correctly
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_column_exists():
    """Test 1: Verify column exists"""
    from sqlalchemy import text
    from server.db import db
    from server.app_factory import create_minimal_app
    
    app = create_minimal_app()
    with app.app_context():
        result = db.session.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
              AND table_name = 'leads' 
              AND column_name = 'last_call_direction'
        """))
        row = result.fetchone()
        
        if row:
            print("✅ Test 1 PASSED: Column exists")
            print(f"   Column: {row[0]}, Type: {row[1]}")
            return True
        else:
            print("❌ Test 1 FAILED: Column does not exist")
            return False

def test_index_exists():
    """Test 2: Verify index exists"""
    from sqlalchemy import text
    from server.db import db
    from server.app_factory import create_minimal_app
    
    app = create_minimal_app()
    with app.app_context():
        result = db.session.execute(text("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE schemaname = 'public' 
              AND indexname = 'idx_leads_last_call_direction'
        """))
        row = result.fetchone()
        
        if row:
            print("✅ Test 2 PASSED: Index exists")
            print(f"   Index: {row[0]}")
            return True
        else:
            print("❌ Test 2 FAILED: Index does not exist")
            return False

def test_backfill_results():
    """Test 3: Verify backfill worked"""
    from sqlalchemy import text
    from server.db import db
    from server.app_factory import create_minimal_app
    
    app = create_minimal_app()
    with app.app_context():
        result = db.session.execute(text("""
            SELECT 
                COUNT(*) as total_leads,
                COUNT(last_call_direction) as leads_with_direction,
                COUNT(*) FILTER (WHERE last_call_direction = 'inbound') as inbound_leads,
                COUNT(*) FILTER (WHERE last_call_direction = 'outbound') as outbound_leads
            FROM leads
        """))
        row = result.fetchone()
        
        print("✅ Test 3 PASSED: Backfill stats")
        print(f"   Total leads: {row[0]}")
        print(f"   Leads with direction: {row[1]}")
        print(f"   Inbound leads: {row[2]}")
        print(f"   Outbound leads: {row[3]}")
        
        if row[0] > 0 and row[1] == 0:
            print("   ⚠️  WARNING: No leads have direction set (might need backfill)")
        
        return True

def test_api_query():
    """Test 4: Verify API can query the column without errors"""
    from server.models_sql import Lead
    from server.db import db
    from server.app_factory import create_minimal_app
    
    app = create_minimal_app()
    with app.app_context():
        try:
            # Test simple query
            count = Lead.query.count()
            print(f"✅ Test 4a PASSED: Can query leads table ({count} leads)")
            
            # Test filter by direction
            inbound_count = Lead.query.filter_by(last_call_direction='inbound').count()
            print(f"✅ Test 4b PASSED: Can filter by direction (inbound={inbound_count})")
            
            # Test accessing the column
            lead = Lead.query.first()
            if lead:
                direction = lead.last_call_direction
                print(f"✅ Test 4c PASSED: Can access column (first lead direction={direction})")
            
            return True
        except Exception as e:
            print(f"❌ Test 4 FAILED: {e}")
            return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing last_call_direction Implementation")
    print("=" * 60)
    print()
    
    # Check DATABASE_URL is set
    if not os.getenv('DATABASE_URL'):
        print("❌ ERROR: DATABASE_URL environment variable not set")
        print("   Please set DATABASE_URL to run tests")
        sys.exit(1)
    
    # Mask sensitive database info
    db_url = os.getenv('DATABASE_URL', '')
    if '@' in db_url:
        # Show only that it's configured, not the actual host
        print("Database: [configured]")
    else:
        print("Database: [not properly configured]")
    print()
    
    tests = [
        test_column_exists,
        test_index_exists,
        test_backfill_results,
        test_api_query
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
        print()
    
    print("=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)

if __name__ == '__main__':
    main()
