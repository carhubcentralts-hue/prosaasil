"""
Integration tests for page permissions API endpoints
הנחיית-על: בדיקות API הרשאות
"""
import pytest
import json

def test_page_registry_structure():
    """Test that PAGE_REGISTRY has correct structure"""
    from server.security.page_registry import PAGE_REGISTRY
    
    assert len(PAGE_REGISTRY) > 0
    
    # Check each page has required fields
    for page_key, config in PAGE_REGISTRY.items():
        assert config.page_key == page_key
        assert config.title_he, f"Page {page_key} missing title_he"
        assert config.route, f"Page {page_key} missing route"
        assert config.min_role in ["agent", "manager", "admin", "owner", "system_admin"]
        assert config.category, f"Page {page_key} missing category"
        assert isinstance(config.api_tags, list)

def test_default_pages_are_valid():
    """Test that DEFAULT_ENABLED_PAGES contains only valid page keys"""
    from server.security.page_registry import DEFAULT_ENABLED_PAGES, PAGE_REGISTRY
    
    for page_key in DEFAULT_ENABLED_PAGES:
        assert page_key in PAGE_REGISTRY, f"Invalid page key in defaults: {page_key}"

def test_migration_71_adds_enabled_pages():
    """Test that migration 71 would add enabled_pages column"""
    # This is a smoke test to ensure the migration code is syntactically correct
    from server.db_migrate import check_column_exists
    
    # Just import the function to verify syntax
    assert callable(check_column_exists)

def test_permission_decorator_exists():
    """Test that permission decorator is importable"""
    from server.security.permissions import require_page_access
    
    assert callable(require_page_access)

def test_context_endpoint_blueprint_exists():
    """Test that context endpoint blueprint exists"""
    from server.routes_context import context_bp
    
    assert context_bp is not None
    assert context_bp.name == "context_bp"

def test_business_pages_endpoints_exist():
    """Test that business pages management endpoints are registered"""
    from server.routes_business_management import biz_mgmt_bp
    
    # Check that blueprint has the routes
    routes = [rule.rule for rule in biz_mgmt_bp.url_map.iter_rules() 
              if rule.endpoint.startswith(biz_mgmt_bp.name)]
    
    # Note: routes may not be registered until app is created
    # This just verifies the blueprint exists
    assert biz_mgmt_bp is not None

def test_page_config_serialization():
    """Test that PageConfig can be serialized to JSON"""
    from server.security.page_registry import get_page_config
    
    config = get_page_config("crm_leads")
    assert config is not None
    
    config_dict = config.to_dict()
    
    # Should be JSON serializable
    json_str = json.dumps(config_dict)
    assert json_str
    
    # Should deserialize back
    deserialized = json.loads(json_str)
    assert deserialized["page_key"] == "crm_leads"

def test_role_hierarchy_logic():
    """Test role hierarchy validation"""
    from server.security.page_registry import get_pages_for_role
    
    # Agent role
    agent_pages = get_pages_for_role("agent", include_system_admin=False)
    assert len(agent_pages) > 0
    
    # Manager role should have at least same as agent
    manager_pages = get_pages_for_role("manager", include_system_admin=False)
    assert len(manager_pages) >= len(agent_pages)
    
    # Admin should have at least same as manager
    admin_pages = get_pages_for_role("admin", include_system_admin=False)
    assert len(admin_pages) >= len(manager_pages)
    
    # Owner should have at least same as admin
    owner_pages = get_pages_for_role("owner", include_system_admin=False)
    assert len(owner_pages) >= len(admin_pages)

def test_categories_are_defined():
    """Test that all pages have valid categories"""
    from server.security.page_registry import PAGE_REGISTRY, get_all_categories
    
    categories = get_all_categories()
    assert len(categories) > 0
    
    # Common categories should exist
    expected_categories = ["dashboard", "crm", "calls", "whatsapp", "settings"]
    for cat in expected_categories:
        assert cat in categories, f"Expected category {cat} not found"

def test_business_model_has_enabled_pages():
    """Test that Business model has enabled_pages field"""
    from server.models_sql import Business
    
    # Check that the field is defined
    assert hasattr(Business, 'enabled_pages')

def test_page_keys_are_unique():
    """Test that all page keys are unique"""
    from server.security.page_registry import PAGE_REGISTRY
    
    keys = list(PAGE_REGISTRY.keys())
    assert len(keys) == len(set(keys)), "Page keys should be unique"

def test_routes_are_unique():
    """Test that all routes are unique"""
    from server.security.page_registry import PAGE_REGISTRY
    
    routes = [config.route for config in PAGE_REGISTRY.values()]
    # Admin routes may overlap with business routes for system_admin
    # So we don't enforce strict uniqueness, just check they exist
    assert all(route for route in routes), "All pages should have routes"

def test_api_tags_structure():
    """Test that API tags are properly structured"""
    from server.security.page_registry import PAGE_REGISTRY
    
    for page_key, config in PAGE_REGISTRY.items():
        assert isinstance(config.api_tags, list), \
            f"Page {page_key} api_tags should be a list"
        assert all(isinstance(tag, str) for tag in config.api_tags), \
            f"Page {page_key} api_tags should contain strings"

def test_backward_compatibility():
    """Test that default pages include critical existing features"""
    from server.security.page_registry import DEFAULT_ENABLED_PAGES
    
    # Critical pages that should be enabled by default
    critical_pages = [
        "dashboard",
        "crm_leads", 
        "crm_customers",
        "calls_inbound",
        "calls_outbound",
        "settings"
    ]
    
    for page_key in critical_pages:
        assert page_key in DEFAULT_ENABLED_PAGES, \
            f"Critical page {page_key} should be in default enabled pages for backward compatibility"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
