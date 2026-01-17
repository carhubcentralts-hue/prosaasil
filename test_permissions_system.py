"""
Tests for page permissions system
הנחיית-על: בדיקות מערכת הרשאות דפים
"""
import pytest
import json
from server.security.page_registry import (
    PAGE_REGISTRY,
    get_all_page_keys,
    get_page_config,
    get_pages_by_category,
    get_all_categories,
    get_pages_for_role,
    validate_page_keys,
    DEFAULT_ENABLED_PAGES
)

def test_page_registry_not_empty():
    """Test that page registry has pages defined"""
    assert len(PAGE_REGISTRY) > 0, "Page registry should not be empty"
    assert len(PAGE_REGISTRY) >= 14, "Should have at least 14 pages"

def test_default_enabled_pages():
    """Test that default enabled pages excludes system_admin pages"""
    assert len(DEFAULT_ENABLED_PAGES) > 0
    
    # Check that no system_admin pages are in default
    for page_key in DEFAULT_ENABLED_PAGES:
        config = PAGE_REGISTRY.get(page_key)
        assert config is not None
        assert not config.is_system_admin_only, \
            f"System admin page {page_key} should not be in DEFAULT_ENABLED_PAGES"

def test_get_all_page_keys():
    """Test getting all page keys"""
    # Without system_admin pages
    non_admin_keys = get_all_page_keys(include_system_admin=False)
    assert len(non_admin_keys) > 0
    
    # With system_admin pages
    all_keys = get_all_page_keys(include_system_admin=True)
    assert len(all_keys) > len(non_admin_keys)
    
    # Check that admin pages are excluded from non-admin list
    admin_pages = set(all_keys) - set(non_admin_keys)
    for page_key in admin_pages:
        config = PAGE_REGISTRY.get(page_key)
        assert config.is_system_admin_only

def test_get_page_config():
    """Test getting individual page configuration"""
    # Test known page
    crm_leads = get_page_config("crm_leads")
    assert crm_leads is not None
    assert crm_leads.title_he == "לידים"
    assert crm_leads.min_role == "agent"
    
    # Test non-existent page
    invalid = get_page_config("invalid_page")
    assert invalid is None

def test_get_pages_by_category():
    """Test grouping pages by category"""
    crm_pages = get_pages_by_category("crm")
    assert len(crm_pages) > 0
    
    for page in crm_pages:
        assert page.category == "crm"

def test_get_all_categories():
    """Test getting all categories"""
    categories = get_all_categories()
    assert len(categories) > 0
    assert "crm" in categories
    assert "calls" in categories
    assert "dashboard" in categories

def test_get_pages_for_role():
    """Test getting pages accessible for each role"""
    # Agent should have least pages
    agent_pages = get_pages_for_role("agent", include_system_admin=False)
    assert len(agent_pages) > 0
    
    # Admin should have more than agent
    admin_pages = get_pages_for_role("admin", include_system_admin=False)
    assert len(admin_pages) >= len(agent_pages)
    
    # System admin with flag should have all pages
    system_admin_pages = get_pages_for_role("system_admin", include_system_admin=True)
    assert len(system_admin_pages) == len(PAGE_REGISTRY)

def test_validate_page_keys():
    """Test page key validation"""
    # Valid keys
    valid_keys = ["crm_leads", "dashboard", "calls_inbound"]
    is_valid, invalid = validate_page_keys(valid_keys)
    assert is_valid
    assert len(invalid) == 0
    
    # Invalid keys
    invalid_keys = ["crm_leads", "invalid_page", "another_invalid"]
    is_valid, invalid = validate_page_keys(invalid_keys)
    assert not is_valid
    assert len(invalid) == 2
    assert "invalid_page" in invalid
    assert "another_invalid" in invalid

def test_page_config_to_dict():
    """Test serialization of page config"""
    config = get_page_config("crm_leads")
    assert config is not None
    
    config_dict = config.to_dict()
    assert isinstance(config_dict, dict)
    assert config_dict["page_key"] == "crm_leads"
    assert config_dict["title_he"] == "לידים"
    assert config_dict["route"] == "/app/leads"
    assert config_dict["min_role"] == "agent"

def test_role_hierarchy():
    """Test that role hierarchy works correctly"""
    # Agent can access agent pages
    agent_pages = get_pages_for_role("agent")
    for page_key in agent_pages:
        config = PAGE_REGISTRY[page_key]
        assert config.min_role in ["agent"]
    
    # Admin can access admin and lower pages
    admin_pages = get_pages_for_role("admin")
    for page_key in admin_pages:
        config = PAGE_REGISTRY[page_key]
        assert config.min_role in ["agent", "manager", "admin"]

def test_critical_pages_exist():
    """Test that critical pages are registered"""
    critical_pages = [
        "dashboard",
        "crm_leads",
        "crm_customers",
        "calls_inbound",
        "calls_outbound",
        "whatsapp_inbox",
        "settings"
    ]
    
    for page_key in critical_pages:
        assert page_key in PAGE_REGISTRY, f"Critical page {page_key} missing from registry"
        config = PAGE_REGISTRY[page_key]
        assert config.title_he, f"Page {page_key} missing title"
        assert config.route, f"Page {page_key} missing route"

def test_admin_pages_marked_correctly():
    """Test that admin pages are marked as system_admin_only"""
    admin_pages = ["admin_dashboard", "admin_businesses", "admin_business_minutes"]
    
    for page_key in admin_pages:
        if page_key in PAGE_REGISTRY:
            config = PAGE_REGISTRY[page_key]
            assert config.is_system_admin_only, \
                f"Admin page {page_key} should be marked as system_admin_only"
            assert config.min_role == "system_admin", \
                f"Admin page {page_key} should require system_admin role"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
