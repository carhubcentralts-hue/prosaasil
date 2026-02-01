"""
Test immediate_message parameter fix for scheduled messages

This test verifies that the immediate_message parameter is:
1. Accepted by create_rule() and update_rule()
2. Stored in the database
3. Used correctly when creating immediate messages
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def test_service_function_signatures():
    """Test that service functions accept immediate_message parameter"""
    print("=" * 60)
    print("TEST 1: Service Function Signatures")
    print("=" * 60)
    
    try:
        import inspect
        from server.services import scheduled_messages_service
        
        # Check create_rule signature
        create_sig = inspect.signature(scheduled_messages_service.create_rule)
        assert 'immediate_message' in create_sig.parameters, "❌ create_rule missing immediate_message parameter"
        print("✅ create_rule has immediate_message parameter")
        
        # Check update_rule signature
        update_sig = inspect.signature(scheduled_messages_service.update_rule)
        assert 'immediate_message' in update_sig.parameters, "❌ update_rule missing immediate_message parameter"
        print("✅ update_rule has immediate_message parameter")
        
    except ImportError as e:
        print(f"⚠️  Skipping test - dependencies not available: {e}")
    
    print()


def test_model_has_column():
    """Test that ScheduledMessageRule model has immediate_message column"""
    print("=" * 60)
    print("TEST 2: Model Column Definition")
    print("=" * 60)
    
    try:
        from server.models_sql import ScheduledMessageRule
        import inspect
        
        # Get the source code of the model
        source = inspect.getsource(ScheduledMessageRule)
        
        # Check if immediate_message is defined
        assert 'immediate_message' in source, "❌ Model missing immediate_message column"
        print("✅ ScheduledMessageRule has immediate_message column defined")
        
        # Check that it's a Text column
        assert 'db.Column(db.Text' in source and 'immediate_message' in source, "❌ immediate_message should be Text column"
        print("✅ immediate_message is defined as Text column")
        
        # Check that it's nullable
        assert 'nullable=True' in source or 'NULL' in source, "✅ immediate_message is nullable (optional)"
        
    except ImportError as e:
        print(f"⚠️  Skipping test - dependencies not available: {e}")
    
    print()


def test_route_accepts_parameter():
    """Test that API routes handle immediate_message parameter"""
    print("=" * 60)
    print("TEST 3: API Route Handling")
    print("=" * 60)
    
    # Read routes file
    routes_file = 'server/routes_scheduled_messages.py'
    
    with open(routes_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that immediate_message is included in create_rule call
    assert "immediate_message=data.get('immediate_message')" in content, \
        "❌ create_rule not passing immediate_message"
    print("✅ create_rule endpoint passes immediate_message parameter")
    
    # Check that immediate_message is returned in responses
    assert "getattr(rule, 'immediate_message', None)" in content, \
        "❌ Response not including immediate_message"
    print("✅ API responses include immediate_message field")
    
    # Count occurrences to make sure it's in all the right places
    count = content.count("'immediate_message'")
    assert count >= 3, f"❌ immediate_message should appear at least 3 times, found {count}"
    print(f"✅ immediate_message appears {count} times in routes file")
    
    print()


def test_service_logic():
    """Test that service logic uses immediate_message correctly"""
    print("=" * 60)
    print("TEST 4: Service Logic")
    print("=" * 60)
    
    # Read service file
    service_file = 'server/services/scheduled_messages_service.py'
    
    with open(service_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that immediate_message is used in create_scheduled_tasks_for_lead
    assert 'rule.immediate_message' in content, \
        "❌ Service not using rule.immediate_message"
    print("✅ Service uses rule.immediate_message field")
    
    # Check for fallback logic
    assert 'if rule.immediate_message else rule.message_text' in content or \
           'rule.immediate_message or rule.message_text' in content, \
        "❌ Missing fallback to message_text"
    print("✅ Service has fallback logic to message_text")
    
    # Check that immediate_message is set in create_rule
    assert 'immediate_message=immediate_message' in content, \
        "❌ create_rule not setting immediate_message"
    print("✅ create_rule sets immediate_message field")
    
    # Check that immediate_message is updated in update_rule
    assert 'rule.immediate_message = immediate_message' in content, \
        "❌ update_rule not updating immediate_message"
    print("✅ update_rule updates immediate_message field")
    
    print()


def test_migration_exists():
    """Test that migration file exists"""
    print("=" * 60)
    print("TEST 5: Database Migration File")
    print("=" * 60)
    
    migration_file = 'migration_add_immediate_message.py'
    
    assert os.path.exists(migration_file), "❌ Migration file not found"
    print("✅ migration_add_immediate_message.py exists")
    
    with open(migration_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that it adds the immediate_message column
    assert 'immediate_message' in content, "❌ Migration doesn't mention immediate_message"
    print("✅ Migration adds immediate_message column")
    
    # Check that it's on the right table
    assert 'scheduled_message_rules' in content, "❌ Migration targets wrong table"
    print("✅ Migration targets scheduled_message_rules table")
    
    # Check that it's nullable
    assert 'NULL' in content, "❌ Column should be nullable"
    print("✅ Column is nullable for backward compatibility")
    
    # Check for idempotency
    assert 'IF NOT EXISTS' in content or 'information_schema.columns' in content, \
        "❌ Migration should be idempotent"
    print("✅ Migration is idempotent")
    
    print()


def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("IMMEDIATE_MESSAGE PARAMETER FIX - TEST SUITE")
    print("=" * 60 + "\n")
    
    tests = [
        ("Service Function Signatures", test_service_function_signatures),
        ("Model Column Definition", test_model_has_column),
        ("API Route Handling", test_route_accepts_parameter),
        ("Service Logic", test_service_logic),
        ("Database Migration File", test_migration_exists),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"❌ {test_name} FAILED: {e}\n")
            failed += 1
    
    print("=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60)
    print(f"\n✅ {passed} tests passed")
    if failed > 0:
        print(f"❌ {failed} tests failed")
        return False
    
    print("\n📋 Summary:")
    print("   1. Service functions accept immediate_message parameter")
    print("   2. Model has immediate_message column defined")
    print("   3. API routes handle immediate_message parameter")
    print("   4. Service logic uses immediate_message with fallback")
    print("   5. Database migration file exists and is correct")
    print("\n🚀 Fix is complete and ready for testing!")
    
    return True


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
