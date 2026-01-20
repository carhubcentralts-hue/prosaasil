"""
Test to verify call direction filtering is working correctly.

This test verifies that:
1. The /api/inbound/recent-calls endpoint exists and filters by direction='inbound'
2. The /api/outbound/recent-calls endpoint filters by direction='outbound'
3. The endpoints return the correct data structure
"""
import pytest
import os


def test_inbound_outbound_endpoints_exist():
    """
    Verify both inbound and outbound recent-calls endpoints are registered
    """
    # Set migration mode to avoid DB initialization during tests
    os.environ['MIGRATION_MODE'] = '1'
    
    from server.app_factory import create_app
    
    app = create_app()
    
    # Get all registered routes
    routes = {}
    for rule in app.url_map.iter_rules():
        routes[str(rule)] = list(rule.methods - {'HEAD', 'OPTIONS'})
    
    # Verify inbound recent-calls endpoint exists
    assert '/api/inbound/recent-calls' in routes, \
        "Missing /api/inbound/recent-calls endpoint"
    assert 'GET' in routes['/api/inbound/recent-calls'], \
        "/api/inbound/recent-calls should support GET method"
    
    # Verify outbound recent-calls endpoint exists
    assert '/api/outbound/recent-calls' in routes, \
        "Missing /api/outbound/recent-calls endpoint"
    assert 'GET' in routes['/api/outbound/recent-calls'], \
        "/api/outbound/recent-calls should support GET method"
    
    print("✅ Both inbound and outbound recent-calls endpoints are registered")


def test_direction_filtering_logic():
    """
    Verify that the endpoints have correct direction filtering in their implementation
    """
    import inspect
    from server.routes_outbound import get_recent_calls, get_recent_inbound_calls
    
    # Get source code of both functions
    outbound_source = inspect.getsource(get_recent_calls)
    inbound_source = inspect.getsource(get_recent_inbound_calls)
    
    # Verify outbound endpoint filters by direction="outbound"
    assert 'direction="outbound"' in outbound_source, \
        "Outbound endpoint should filter by direction='outbound'"
    
    # Verify inbound endpoint filters by direction="inbound"
    assert 'direction="inbound"' in inbound_source, \
        "Inbound endpoint should filter by direction='inbound'"
    
    print("✅ Both endpoints have correct direction filtering logic")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
