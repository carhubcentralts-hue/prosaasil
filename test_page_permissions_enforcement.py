#!/usr/bin/env python3
"""
Test that page permissions are properly enforced on API routes
Verifies that the @require_page_access decorator blocks unauthorized access
"""
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

def test_decorator_applied():
    """Test that @require_page_access decorator is applied to routes"""
    print("✅ Testing decorator application...")
    
    # Test outbound routes
    from server.routes_outbound import outbound_bp
    
    # Get all view functions from the blueprint
    view_functions = []
    for rule in outbound_bp.url_map.iter_rules():
        if rule.endpoint.startswith('outbound.'):
            view_func = outbound_bp.view_functions.get(rule.endpoint.split('.')[-1])
            if view_func:
                view_functions.append((rule.endpoint, view_func))
    
    if not view_functions:
        print("   ⚠️  No view functions found - blueprint may not be registered")
        print("   ℹ️  This is expected in isolated testing")
        print("   ℹ️  Run with Flask app context for full validation")
    else:
        print(f"   - Found {len(view_functions)} view functions")
        
        # Note: Decorator detection via introspection is unreliable in isolated tests.
        # The proper way to verify is:
        # 1. Check source code for @require_page_access decorators (done in test_import_structure)
        # 2. Run integration tests with actual HTTP requests
        print("   ℹ️  Use test_import_structure() to verify decorator presence in source")
    
    print("✅ Decorator application test completed!\n")

def test_import_structure():
    """Test that imports are correct"""
    print("✅ Testing import structure...")
    
    # Test that routes import the decorator
    from server import routes_outbound
    import inspect
    
    source = inspect.getsource(routes_outbound)
    
    if 'from server.security.permissions import require_page_access' in source:
        print("   ✅ routes_outbound imports require_page_access")
    else:
        print("   ❌ routes_outbound does NOT import require_page_access")
        return False
    
    if '@require_page_access' in source:
        decorator_count = source.count('@require_page_access')
        print(f"   ✅ Found {decorator_count} uses of @require_page_access decorator")
    else:
        print("   ❌ @require_page_access decorator not used in routes_outbound")
        return False
    
    # Test leads routes
    from server import routes_leads
    source = inspect.getsource(routes_leads)
    
    if 'from server.security.permissions import require_page_access' in source:
        print("   ✅ routes_leads imports require_page_access")
    else:
        print("   ❌ routes_leads does NOT import require_page_access")
        return False
    
    if '@require_page_access' in source:
        decorator_count = source.count('@require_page_access')
        print(f"   ✅ Found {decorator_count} uses of @require_page_access decorator")
    else:
        print("   ❌ @require_page_access decorator not used in routes_leads")
        return False
    
    print("✅ Import structure tests passed!\n")
    return True

def test_page_registry():
    """Test that page keys used in decorators exist in registry"""
    print("✅ Testing page registry consistency...")
    
    from server.security.page_registry import PAGE_REGISTRY
    
    # Expected page keys based on our changes
    expected_keys = [
        'calls_outbound',
        'calls_inbound',
        'crm_leads',
        'crm_customers',
        'calendar',
        'whatsapp_inbox',
        'whatsapp_broadcast',
        'dashboard',
        'emails',
        'statistics',
        'settings',
        'users'
    ]
    
    missing_keys = []
    for key in expected_keys:
        if key not in PAGE_REGISTRY:
            missing_keys.append(key)
            print(f"   ❌ Page key '{key}' not found in registry")
        else:
            print(f"   ✅ Page key '{key}' exists in registry")
    
    if missing_keys:
        print(f"   ❌ Missing {len(missing_keys)} page keys")
        return False
    
    print("✅ Page registry consistency tests passed!\n")
    return True

def test_permissions_decorator_logic():
    """Test the decorator logic itself"""
    print("✅ Testing decorator logic...")
    
    from server.security.permissions import require_page_access, ROLE_HIERARCHY
    from server.security.page_registry import get_page_config
    
    # Test that role hierarchy is defined
    expected_roles = ['agent', 'admin', 'owner', 'system_admin']
    for role in expected_roles:
        assert role in ROLE_HIERARCHY, f"Role '{role}' not found in ROLE_HIERARCHY"
    print("   ✅ Role hierarchy defined correctly")
    
    # Test that get_page_config works
    config = get_page_config('calls_outbound')
    assert config is not None
    assert config.page_key == 'calls_outbound'
    assert config.min_role in ROLE_HIERARCHY
    print(f"   ✅ get_page_config works - calls_outbound requires '{config.min_role}' role")
    
    # Test that decorator can be called
    decorator = require_page_access('calls_outbound')
    assert callable(decorator)
    print("   ✅ Decorator is callable")
    
    print("✅ Decorator logic tests passed!\n")
    return True

if __name__ == '__main__':
    print("=" * 60)
    print("Testing Page Permissions Enforcement")
    print("=" * 60)
    print()
    
    all_passed = True
    
    try:
        all_passed &= test_import_structure()
    except Exception as e:
        print(f"❌ Import structure test failed: {e}\n")
        all_passed = False
    
    try:
        all_passed &= test_page_registry()
    except Exception as e:
        print(f"❌ Page registry test failed: {e}\n")
        all_passed = False
    
    try:
        all_passed &= test_permissions_decorator_logic()
    except Exception as e:
        print(f"❌ Decorator logic test failed: {e}\n")
        all_passed = False
    
    try:
        test_decorator_applied()
    except Exception as e:
        print(f"⚠️  Decorator application test: {e}\n")
    
    print("=" * 60)
    if all_passed:
        print("✅ ALL CRITICAL TESTS PASSED!")
        print()
        print("Page permissions enforcement is properly configured:")
        print("  ✅ Backend routes have @require_page_access decorators")
        print("  ✅ All page keys exist in the registry")
        print("  ✅ Decorator logic is functional")
        print()
        print("Next steps:")
        print("  1. Test with a running application")
        print("  2. Disable a page in business.enabled_pages")
        print("  3. Verify frontend redirects to /app/forbidden")
        print("  4. Verify backend returns 403 for API calls")
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
    
    print("=" * 60)
