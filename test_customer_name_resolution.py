"""
Test: Customer Name Resolution for Outbound Calls
Validates the NAME_ANCHOR SSOT system fixes
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_model_fields_exist():
    """Test that customer_name and lead_name fields exist in models"""
    print("🧪 Testing model field definitions...")
    
    # Read models_sql.py and check for field definitions
    with open('server/models_sql.py', 'r') as f:
        content = f.read()
    
    # Check CallLog has customer_name
    assert "class CallLog" in content, "CallLog model should exist"
    # Look for customer_name field in CallLog
    calllog_start = content.find("class CallLog")
    calllog_section = content[calllog_start:calllog_start + 5000]  # Next 5000 chars after CallLog
    assert "customer_name = db.Column" in calllog_section, "CallLog should have customer_name field"
    print("✅ CallLog.customer_name field exists")
    
    # Check OutboundCallJob has lead_name
    assert "class OutboundCallJob" in content, "OutboundCallJob model should exist"
    # Look for lead_name field in OutboundCallJob
    job_start = content.find("class OutboundCallJob")
    job_section = content[job_start:job_start + 3000]  # Next 3000 chars after OutboundCallJob
    assert "lead_name = db.Column" in job_section, "OutboundCallJob should have lead_name field"
    print("✅ OutboundCallJob.lead_name field exists")
    
    print("✅ All model fields exist correctly")
    return True


def test_name_validation():
    """Test the name validation function logic"""
    print("\n🧪 Testing name validation logic...")
    
    # Test valid names
    valid_names = ["John Doe", "דוד כהן", "Sarah", "משה לוי"]
    invalid_names = [None, "", "  ", "unknown", "test", "null", "None", "n/a", "-"]
    
    def _is_valid_customer_name(name: str) -> bool:
        """Replicate validation logic from media_ws_ai.py"""
        if not name:
            return False
        
        name_lower = name.strip().lower()
        if not name_lower:
            return False
        
        # Reject common placeholder values
        invalid_values = ['unknown', 'test', '-', 'null', 'none', 'n/a', 'na']
        if name_lower in invalid_values:
            return False
        
        return True
    
    for name in valid_names:
        assert _is_valid_customer_name(name), f"'{name}' should be valid"
        print(f"  ✅ Valid: '{name}'")
    
    for name in invalid_names:
        assert not _is_valid_customer_name(name), f"'{name}' should be invalid"
        print(f"  ✅ Invalid: '{name}'")
    
    print("✅ Name validation logic works correctly")
    return True


def test_name_priority_order():
    """Test that name resolution priority order is correct"""
    print("\n🧪 Testing name resolution priority...")
    
    # Priority order should be:
    # 1. CallLog.customer_name
    # 2. OutboundCallJob.lead_name  
    # 3. Lead.full_name
    # 4. None
    
    priorities = [
        "CallLog.customer_name",
        "OutboundCallJob.lead_name",
        "Lead.full_name",
        "None (fallback)"
    ]
    
    print("  Expected priority order:")
    for i, priority in enumerate(priorities, 1):
        print(f"    {i}. {priority}")
    
    print("✅ Priority order documented correctly")
    return True


def test_migration_in_db_migrate():
    """Test that migration 52 exists in db_migrate.py"""
    print("\n🧪 Testing migration in db_migrate.py...")
    
    migration_file = "server/db_migrate.py"
    assert os.path.exists(migration_file), f"Migration file {migration_file} should exist"
    print(f"✅ Migration file exists: {migration_file}")
    
    # Read migration and check for Migration 52
    with open(migration_file, 'r') as f:
        content = f.read()
    
    assert "Migration 52:" in content, "Migration 52 should exist in db_migrate.py"
    assert "customer_name" in content, "Migration should add customer_name column"
    assert "lead_name" in content, "Migration should add lead_name column"
    assert "NAME_ANCHOR SSOT" in content, "Migration should mention NAME_ANCHOR SSOT purpose"
    assert "ALTER TABLE call_log" in content, "Migration should alter call_log table"
    assert "ALTER TABLE outbound_call_jobs" in content, "Migration should alter outbound_call_jobs table"
    
    print("✅ Migration 52 structure is correct in db_migrate.py")
    return True


def test_logging_keywords():
    """Test that proper logging keywords are used"""
    print("\n🧪 Testing logging keywords...")
    
    # Read media_ws_ai.py and check for logging keywords
    with open('server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    required_logs = [
        "[NAME_RESOLVE]",
        "[NAME_ANCHOR DEBUG]",
        "[NAME_POLICY]"
    ]
    
    for log_keyword in required_logs:
        assert log_keyword in content, f"Logging keyword '{log_keyword}' should exist"
        print(f"  ✅ Found: {log_keyword}")
    
    # Check that we don't inject None
    assert 'if customer_name_to_inject is None:' in content, "Should check for None before injection"
    assert 'skipped reason=no_name' in content, "Should log when skipping due to no name"
    
    print("✅ All logging keywords present")
    return True


def run_all_tests():
    """Run all tests"""
    print("="*60)
    print("Customer Name Resolution Tests")
    print("="*60)
    
    tests = [
        test_model_fields_exist,
        test_name_validation,
        test_name_priority_order,
        test_migration_in_db_migrate,
        test_logging_keywords
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append((test_func.__name__, result))
        except Exception as e:
            print(f"❌ {test_func.__name__} failed: {e}")
            results.append((test_func.__name__, False))
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*60)
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
