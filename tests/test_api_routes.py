"""
Test to verify all critical API routes are registered in Flask app
This test addresses the 404 errors by ensuring routes exist before deployment
"""
import pytest
import os


def test_critical_routes_exist():
    """
    Verify all critical API endpoints mentioned in the issue are registered
    
    This test ensures:
    1. Dashboard endpoints exist
    2. Business endpoints exist
    3. Admin endpoints exist
    4. WhatsApp endpoints exist
    5. CRM endpoints exist
    6. Notification endpoints exist
    7. Search endpoints exist
    8. Leads endpoints exist
    """
    # Set migration mode to avoid DB initialization during tests
    os.environ['MIGRATION_MODE'] = '1'
    
    from server.app_factory import create_app
    
    app = create_app()
    
    # Get all registered routes
    routes = {}
    for rule in app.url_map.iter_rules():
        # Store route path -> methods mapping
        routes[str(rule)] = list(rule.methods - {'HEAD', 'OPTIONS'})
    
    # Critical endpoints that MUST exist (from user's console errors)
    critical_endpoints = [
        # Dashboard endpoints
        '/api/dashboard/stats',
        '/api/dashboard/activity',
        
        # Business endpoints
        '/api/business/current',
        '/api/business/current/prompt',
        
        # Admin endpoints
        '/api/admin/businesses',
        
        # Notifications
        '/api/notifications',
        
        # Search
        '/api/search',
        
        # WhatsApp endpoints
        '/api/whatsapp/status',
        '/api/whatsapp/templates',
        '/api/whatsapp/broadcasts',
        '/api/whatsapp/summaries',
        '/api/whatsapp/active-chats',
        
        # CRM endpoints
        '/api/crm/threads',
        
        # Leads endpoints
        '/api/leads',
        
        # Statuses
        '/api/statuses',
        
        # Outbound endpoints
        '/api/outbound/import-lists',
        
        # Health endpoints
        '/api/health',
    ]
    
    missing_routes = []
    
    for endpoint in critical_endpoints:
        # Check if exact route exists OR if parameterized version exists
        found = False
        
        # Check exact match first
        if endpoint in routes:
            found = True
        else:
            # Check for parameterized routes (e.g., /api/leads/<int:lead_id>)
            # by checking if any registered route starts with the base path
            for route in routes.keys():
                # Remove trailing slash for comparison
                route_clean = route.rstrip('/')
                endpoint_clean = endpoint.rstrip('/')
                
                if route_clean == endpoint_clean:
                    found = True
                    break
                
                # For routes like /api/whatsapp/summaries, check if base exists
                if endpoint_clean in route_clean or route_clean.startswith(endpoint_clean):
                    found = True
                    break
        
        if not found:
            missing_routes.append(endpoint)
    
    # Print all API routes for debugging
    api_routes = [r for r in routes.keys() if '/api/' in r]
    print(f"\n=== Registered API Routes ({len(api_routes)}) ===")
    for route in sorted(api_routes)[:50]:  # Print first 50 for debugging
        print(f"  {route} -> {routes[route]}")
    
    # Assert all critical routes exist
    assert len(missing_routes) == 0, (
        f"Missing {len(missing_routes)} critical routes:\n" + 
        "\n".join(f"  - {r}" for r in missing_routes) +
        f"\n\nTotal API routes registered: {len(api_routes)}"
    )
    
    print(f"\n✅ All {len(critical_endpoints)} critical routes are registered!")


def test_route_prefix_consistency():
    """
    Verify that blueprints have consistent prefix usage
    
    This prevents the common bug where routes are defined as /api/... 
    but blueprint also has url_prefix='/api', resulting in /api/api/...
    """
    os.environ['MIGRATION_MODE'] = '1'
    
    from server.app_factory import create_app
    
    app = create_app()
    
    # Get all routes
    routes = [str(rule) for rule in app.url_map.iter_rules()]
    
    # Check for double /api/ prefix (common bug)
    double_api_routes = [r for r in routes if '/api/api/' in r]
    
    assert len(double_api_routes) == 0, (
        f"Found {len(double_api_routes)} routes with double /api/ prefix:\n" +
        "\n".join(f"  - {r}" for r in double_api_routes)
    )
    
    print("✅ No routes with double /api/ prefix found!")


def test_frontend_backend_endpoint_mapping():
    """
    Document the mapping between frontend calls and backend routes
    """
    os.environ['MIGRATION_MODE'] = '1'
    
    from server.app_factory import create_app
    
    app = create_app()
    
    # Get all API routes
    routes = {}
    for rule in app.url_map.iter_rules():
        if '/api/' in str(rule):
            routes[str(rule)] = {
                'methods': list(rule.methods - {'HEAD', 'OPTIONS'}),
                'endpoint': rule.endpoint
            }
    
    # Print mapping table
    print("\n=== Frontend → Backend Endpoint Mapping ===")
    print(f"{'Frontend Path':<50} {'Backend Endpoint':<40} {'Methods'}")
    print("-" * 100)
    
    for path in sorted(routes.keys())[:30]:
        endpoint = routes[path]['endpoint']
        methods = ', '.join(routes[path]['methods'])
        print(f"{path:<50} {endpoint:<40} {methods}")
    
    print(f"\nTotal API routes: {len(routes)}")


if __name__ == '__main__':
    # Run tests
    test_critical_routes_exist()
    test_route_prefix_consistency()
    test_frontend_backend_endpoint_mapping()
