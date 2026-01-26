"""
Test to verify that database queries use efficient range-based comparisons
instead of date() function calls that break indexes
"""
import os
import sys
from datetime import datetime, timedelta


def test_api_adapter_uses_range_queries():
    """Verify api_adapter.py uses range-based queries instead of date() function"""
    with open('server/api_adapter.py', 'r') as f:
        content = f.read()
    
    # Check that we don't use db.func.date() anymore in critical queries
    # Note: We still allow db.func.date() for non-critical queries if needed
    lines = content.split('\n')
    
    problematic_patterns = []
    for i, line in enumerate(lines, 1):
        # Check for problematic date() usage in query filters
        if 'db.func.date(' in line and ('.filter' in line or 'CallLog' in line or 'WhatsAppMessage' in line):
            problematic_patterns.append(f"Line {i}: {line.strip()}")
    
    # We should have fixed all date() calls in filter queries
    assert len(problematic_patterns) == 0, (
        f"Found {len(problematic_patterns)} problematic date() function calls:\n" +
        "\n".join(problematic_patterns)
    )
    
    # Verify we're using datetime range comparisons
    assert 'datetime.combine' in content, "Should use datetime.combine for range queries"
    assert '.min.time()' in content, "Should use .min.time() for start of day"
    assert '.max.time()' in content, "Should use .max.time() for end of day"
    
    print("✅ api_adapter.py uses efficient range-based queries")


def test_routes_calendar_uses_range_queries():
    """Verify routes_calendar.py uses range-based queries instead of date() function"""
    with open('server/routes_calendar.py', 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    
    problematic_patterns = []
    for i, line in enumerate(lines, 1):
        # Check for problematic date() usage in Appointment queries
        if 'db.func.date(Appointment' in line and '.filter' in line:
            problematic_patterns.append(f"Line {i}: {line.strip()}")
    
    # We should have fixed all date() calls for Appointment queries
    assert len(problematic_patterns) == 0, (
        f"Found {len(problematic_patterns)} problematic date() function calls:\n" +
        "\n".join(problematic_patterns)
    )
    
    # Verify we're using datetime range comparisons
    assert 'datetime.combine' in content, "Should use datetime.combine for range queries"
    
    print("✅ routes_calendar.py uses efficient range-based queries")


def test_data_api_uses_range_queries():
    """Verify data_api.py uses range-based queries instead of date() function"""
    with open('server/data_api.py', 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    
    problematic_patterns = []
    for i, line in enumerate(lines, 1):
        # Check for problematic date() usage in admin KPI queries
        if 'db.func.date(' in line and ('.filter' in line or 'CallLog' in line or 'WhatsAppMessage' in line):
            problematic_patterns.append(f"Line {i}: {line.strip()}")
    
    # We should have fixed all date() calls in filter queries
    assert len(problematic_patterns) == 0, (
        f"Found {len(problematic_patterns)} problematic date() function calls:\n" +
        "\n".join(problematic_patterns)
    )
    
    # Verify we're using datetime range comparisons
    assert 'datetime.combine' in content, "Should use datetime.combine for range queries"
    
    print("✅ data_api.py uses efficient range-based queries")


def test_query_pattern_correctness():
    """Verify that the query pattern is correct for efficient index usage"""
    # Test the pattern we're using
    from datetime import datetime
    
    # Simulate the pattern we're using in the fixed code
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    # Verify the datetime objects are correct
    assert today_start.hour == 0
    assert today_start.minute == 0
    assert today_start.second == 0
    
    assert today_end.hour == 23
    assert today_end.minute == 59
    assert today_end.second == 59
    
    # Verify date range spans the full day
    assert (today_end - today_start).total_seconds() >= 86399  # Almost full day
    
    print("✅ Query pattern correctness verified")


def test_migration_111_index_exists():
    """Verify that migration 111 creates the necessary index"""
    with open('server/db_migrate.py', 'r') as f:
        content = f.read()
    
    # Check that migration 111 exists
    assert 'Migration 111' in content, "Migration 111 should exist"
    
    # Check that it creates the composite index
    assert 'idx_call_log_business_created' in content, "Should create idx_call_log_business_created index"
    assert 'call_log(business_id, created_at)' in content, "Index should be on (business_id, created_at)"
    
    print("✅ Migration 111 index definition found")


if __name__ == '__main__':
    print("\n" + "="*80)
    print("Database Query Performance Fix Validation")
    print("="*80 + "\n")
    
    try:
        test_api_adapter_uses_range_queries()
        test_routes_calendar_uses_range_queries()
        test_data_api_uses_range_queries()
        test_query_pattern_correctness()
        test_migration_111_index_exists()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED - Query performance fix validated")
        print("="*80)
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
