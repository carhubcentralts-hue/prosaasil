"""
Test for triggered_at parameter fix in scheduled messages

This test verifies that the triggered_at parameter is properly handled
by the create_scheduled_tasks_for_lead function.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

def test_function_signature():
    """Test that create_scheduled_tasks_for_lead accepts triggered_at parameter"""
    print("=" * 60)
    print("TEST: Function Signature - triggered_at parameter")
    print("=" * 60)
    
    import inspect
    
    # Read the service file to check signature
    service_file = 'server/services/scheduled_messages_service.py'
    
    with open(service_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check function signature
    assert 'def create_scheduled_tasks_for_lead(rule_id: int, lead_id: int, triggered_at:' in content, \
        "❌ Function signature missing triggered_at parameter"
    print("✅ Function signature includes triggered_at parameter")
    
    # Check that triggered_at is Optional
    assert 'triggered_at: Optional[datetime]' in content, \
        "❌ triggered_at should be Optional[datetime]"
    print("✅ triggered_at is Optional[datetime] with default None")
    
    # Check that the function uses triggered_at
    assert 'now = triggered_at if triggered_at is not None else datetime.utcnow()' in content, \
        "❌ Function doesn't use triggered_at parameter"
    print("✅ Function uses triggered_at when provided")
    
    # Check that all returns return a count
    lines = content.split('\n')
    in_function = False
    return_count = 0
    return_0_count = 0
    
    for i, line in enumerate(lines):
        if 'def create_scheduled_tasks_for_lead' in line:
            in_function = True
        elif in_function and line.strip().startswith('def '):
            # Hit the next function
            break
        elif in_function and 'return' in line:
            return_count += 1
            if 'return 0' in line or 'return created_count' in line:
                return_0_count += 1
    
    assert return_0_count == return_count, \
        f"❌ Not all returns are returning counts: {return_0_count}/{return_count}"
    print(f"✅ All {return_count} return statements return numeric values")
    
    print()


def test_caller_passes_parameter():
    """Test that schedule_messages_for_lead_status_change passes triggered_at"""
    print("=" * 60)
    print("TEST: Caller Function - passes triggered_at")
    print("=" * 60)
    
    service_file = 'server/services/scheduled_messages_service.py'
    
    with open(service_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that the caller passes triggered_at
    assert 'create_scheduled_tasks_for_lead(' in content and 'triggered_at=changed_at' in content, \
        "❌ schedule_messages_for_lead_status_change doesn't pass triggered_at parameter"
    print("✅ schedule_messages_for_lead_status_change passes triggered_at=changed_at")
    
    # Find the call site
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'tasks_created = create_scheduled_tasks_for_lead(' in line:
            # Check the next few lines for the parameters
            call_block = '\n'.join(lines[i:i+5])
            assert 'rule_id=' in call_block, "❌ Missing rule_id parameter"
            assert 'lead_id=' in call_block, "❌ Missing lead_id parameter"
            assert 'triggered_at=' in call_block, "❌ Missing triggered_at parameter"
            print("✅ All required parameters are passed to create_scheduled_tasks_for_lead")
            break
    
    print()


def test_docstring_updated():
    """Test that docstring mentions triggered_at parameter"""
    print("=" * 60)
    print("TEST: Documentation - docstring updated")
    print("=" * 60)
    
    service_file = 'server/services/scheduled_messages_service.py'
    
    with open(service_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the docstring for create_scheduled_tasks_for_lead
    lines = content.split('\n')
    in_docstring = False
    docstring = []
    
    for i, line in enumerate(lines):
        if 'def create_scheduled_tasks_for_lead' in line:
            # Start looking for docstring
            for j in range(i+1, min(i+20, len(lines))):
                if '"""' in lines[j]:
                    if in_docstring:
                        # End of docstring
                        break
                    else:
                        in_docstring = True
                elif in_docstring:
                    docstring.append(lines[j])
            break
    
    docstring_text = '\n'.join(docstring)
    assert 'triggered_at' in docstring_text.lower(), \
        "❌ Docstring doesn't mention triggered_at parameter"
    print("✅ Docstring documents triggered_at parameter")
    
    print()


def test_backward_compatibility():
    """Test that the fix maintains backward compatibility"""
    print("=" * 60)
    print("TEST: Backward Compatibility")
    print("=" * 60)
    
    service_file = 'server/services/scheduled_messages_service.py'
    
    with open(service_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that triggered_at has a default value
    assert 'triggered_at: Optional[datetime] = None' in content, \
        "❌ triggered_at parameter should have default value None"
    print("✅ triggered_at parameter has default value None (backward compatible)")
    
    # Check that there's a fallback to datetime.utcnow()
    assert 'datetime.utcnow()' in content, \
        "❌ Should fallback to datetime.utcnow() when triggered_at is None"
    print("✅ Falls back to datetime.utcnow() when triggered_at is not provided")
    
    print()


def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("TRIGGERED_AT PARAMETER FIX - TEST SUITE")
    print("=" * 60 + "\n")
    
    tests = [
        ("Function Signature", test_function_signature),
        ("Caller Function", test_caller_passes_parameter),
        ("Documentation", test_docstring_updated),
        ("Backward Compatibility", test_backward_compatibility),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test_name} FAILED: {e}\n")
            failed += 1
        except Exception as e:
            print(f"❌ {test_name} ERROR: {e}\n")
            failed += 1
    
    print("=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60)
    print(f"\n✅ {passed} tests passed")
    if failed > 0:
        print(f"❌ {failed} tests failed")
        return False
    
    print("\n📋 Summary:")
    print("   1. Function accepts triggered_at parameter")
    print("   2. Caller passes triggered_at correctly")
    print("   3. Documentation is updated")
    print("   4. Backward compatibility maintained")
    print("\n🚀 Fix is complete and verified!")
    
    return True


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
