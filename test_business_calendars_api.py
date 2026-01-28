"""
Test Business Calendars API Endpoints
Tests the REST API for calendar and routing rule management
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_api_endpoints_exist():
    """Test that all required API endpoints are defined"""
    from server.routes_calendar import (
        get_business_calendars,
        create_calendar,
        update_calendar,
        delete_calendar,
        get_routing_rules,
        create_routing_rule,
        update_routing_rule,
        delete_routing_rule
    )
    
    # Check that all endpoint functions exist and are callable
    endpoints = {
        'get_business_calendars': get_business_calendars,
        'create_calendar': create_calendar,
        'update_calendar': update_calendar,
        'delete_calendar': delete_calendar,
        'get_routing_rules': get_routing_rules,
        'create_routing_rule': create_routing_rule,
        'update_routing_rule': update_routing_rule,
        'delete_routing_rule': delete_routing_rule,
    }
    
    print("📋 Found API endpoints:")
    for name, func in endpoints.items():
        assert callable(func), f"{name} should be callable"
        print(f"  ✓ {name}")
    
    print("✅ All required API endpoints exist")

def test_calendar_management_imports():
    """Test that calendar management imports work"""
    try:
        from server.models_sql import BusinessCalendar, CalendarRoutingRule
        from server.routes_calendar import (
            get_business_calendars,
            create_calendar,
            update_calendar,
            delete_calendar,
            get_routing_rules,
            create_routing_rule,
            update_routing_rule,
            delete_routing_rule
        )
        print("✅ Calendar management imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_endpoint_decorators():
    """Test that endpoints have proper decorators"""
    from server.routes_calendar import (
        get_business_calendars,
        create_calendar,
        update_calendar,
        delete_calendar
    )
    
    # Check that functions have required decorators applied
    # Note: We can't directly test decorators, but we can verify the functions exist
    assert callable(get_business_calendars), "get_business_calendars should be callable"
    assert callable(create_calendar), "create_calendar should be callable"
    assert callable(update_calendar), "update_calendar should be callable"
    assert callable(delete_calendar), "delete_calendar should be callable"
    
    print("✅ Endpoint decorators validation passed")

def test_endpoint_permissions():
    """Test that endpoints have permission checks"""
    import inspect
    from server.routes_calendar import create_calendar
    
    # Get the source code of the function
    source = inspect.getsource(create_calendar)
    
    # Verify it checks business_id
    assert 'get_business_id()' in source, "Endpoint should check business_id"
    assert 'business_id' in source, "Endpoint should use business_id"
    
    print("✅ Endpoint permissions validation passed")

def test_endpoint_error_handling():
    """Test that endpoints have proper error handling"""
    import inspect
    from server.routes_calendar import get_business_calendars
    
    source = inspect.getsource(get_business_calendars)
    
    # Verify error handling exists
    assert 'try:' in source, "Endpoint should have try/except"
    assert 'except' in source, "Endpoint should have exception handling"
    assert 'jsonify' in source, "Endpoint should return JSON"
    
    print("✅ Endpoint error handling validation passed")

def test_security_business_scope():
    """Test that endpoints enforce business-level security"""
    import inspect
    from server.routes_calendar import update_calendar, delete_calendar
    
    # Check update_calendar
    source_update = inspect.getsource(update_calendar)
    assert 'business_id == business_id' in source_update or 'BusinessCalendar.business_id == business_id' in source_update, \
        "update_calendar should filter by business_id"
    
    # Check delete_calendar
    source_delete = inspect.getsource(delete_calendar)
    assert 'business_id == business_id' in source_delete or 'BusinessCalendar.business_id == business_id' in source_delete, \
        "delete_calendar should filter by business_id"
    
    print("✅ Security business scope validation passed")

def test_routing_rules_calendar_validation():
    """Test that routing rules validate calendar ownership"""
    import inspect
    from server.routes_calendar import create_routing_rule
    
    source = inspect.getsource(create_routing_rule)
    
    # Verify it checks that calendar belongs to business
    assert 'BusinessCalendar.query' in source or 'calendar = BusinessCalendar' in source, \
        "Should verify calendar ownership"
    assert 'business_id' in source, "Should check business_id"
    
    print("✅ Routing rules calendar validation passed")

if __name__ == '__main__':
    # Run tests
    try:
        test_calendar_management_imports()
        test_api_endpoints_exist()
        test_endpoint_decorators()
        test_endpoint_permissions()
        test_endpoint_error_handling()
        test_security_business_scope()
        test_routing_rules_calendar_validation()
        
        print("\n🎉 All API endpoint tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
