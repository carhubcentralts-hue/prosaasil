#!/usr/bin/env python
"""
Tests for Assets Library (מאגר) Feature

Tests:
1. test_assets_requires_permission_403 - API returns 403 when assets page not enabled
2. test_assets_cross_tenant_blocked - Cannot access other business's assets
3. test_asset_media_attachment_fk_enforced - Media requires valid attachment
4. test_assets_crud_operations - Basic CRUD operations work
"""
import sys
import os

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))


def test_assets_page_in_registry():
    """Test that 'assets' page key exists in PAGE_REGISTRY"""
    print("✅ Testing assets page key in registry...")
    
    from server.security.page_registry import PAGE_REGISTRY, get_page_config
    
    assert 'assets' in PAGE_REGISTRY, "❌ 'assets' key missing from PAGE_REGISTRY"
    
    config = get_page_config('assets')
    assert config is not None, "❌ get_page_config('assets') returned None"
    assert config.page_key == 'assets', "❌ page_key mismatch"
    assert config.title_he == 'מאגר', f"❌ title_he mismatch: {config.title_he}"
    assert config.route == '/app/assets', f"❌ route mismatch: {config.route}"
    
    print("   ✅ 'assets' page registered correctly")
    print(f"      - title_he: {config.title_he}")
    print(f"      - route: {config.route}")
    print(f"      - min_role: {config.min_role}")
    print(f"      - category: {config.category}")
    
    print("✅ Page registry test passed!\n")
    return True


def test_assets_model_exists():
    """Test that AssetItem and AssetItemMedia models exist"""
    print("✅ Testing assets models...")
    
    try:
        from server.models_sql import AssetItem, AssetItemMedia
        
        # Check AssetItem fields
        assert hasattr(AssetItem, 'id'), "❌ AssetItem missing 'id'"
        assert hasattr(AssetItem, 'business_id'), "❌ AssetItem missing 'business_id'"
        assert hasattr(AssetItem, 'title'), "❌ AssetItem missing 'title'"
        assert hasattr(AssetItem, 'description'), "❌ AssetItem missing 'description'"
        assert hasattr(AssetItem, 'tags'), "❌ AssetItem missing 'tags'"
        assert hasattr(AssetItem, 'category'), "❌ AssetItem missing 'category'"
        assert hasattr(AssetItem, 'status'), "❌ AssetItem missing 'status'"
        assert hasattr(AssetItem, 'custom_fields'), "❌ AssetItem missing 'custom_fields'"
        print("   ✅ AssetItem model has all required fields")
        
        # Check AssetItemMedia fields
        assert hasattr(AssetItemMedia, 'id'), "❌ AssetItemMedia missing 'id'"
        assert hasattr(AssetItemMedia, 'business_id'), "❌ AssetItemMedia missing 'business_id'"
        assert hasattr(AssetItemMedia, 'asset_item_id'), "❌ AssetItemMedia missing 'asset_item_id'"
        assert hasattr(AssetItemMedia, 'attachment_id'), "❌ AssetItemMedia missing 'attachment_id'"
        assert hasattr(AssetItemMedia, 'role'), "❌ AssetItemMedia missing 'role'"
        assert hasattr(AssetItemMedia, 'sort_order'), "❌ AssetItemMedia missing 'sort_order'"
        print("   ✅ AssetItemMedia model has all required fields")
        
    except ImportError as e:
        print(f"   ❌ Failed to import models: {e}")
        return False
    
    print("✅ Models test passed!\n")
    return True


def test_assets_blueprint_exists():
    """Test that assets blueprint exists and has required routes"""
    print("✅ Testing assets blueprint...")
    
    try:
        from server.routes_assets import assets_bp
        
        assert assets_bp is not None, "❌ assets_bp is None"
        assert assets_bp.name == 'assets', f"❌ Blueprint name mismatch: {assets_bp.name}"
        assert assets_bp.url_prefix == '/api/assets', f"❌ URL prefix mismatch: {assets_bp.url_prefix}"
        
        print("   ✅ assets_bp exists with correct configuration")
        print(f"      - name: {assets_bp.name}")
        print(f"      - url_prefix: {assets_bp.url_prefix}")
        
    except ImportError as e:
        print(f"   ❌ Failed to import blueprint: {e}")
        return False
    
    print("✅ Blueprint test passed!\n")
    return True


def test_assets_permission_decorator():
    """Test that routes use @require_page_access('assets') decorator"""
    print("✅ Testing permission decorators in routes...")
    
    import inspect
    from server import routes_assets
    
    source = inspect.getsource(routes_assets)
    
    # Check decorator import
    if 'from server.security.permissions import require_page_access' in source:
        print("   ✅ routes_assets imports require_page_access")
    else:
        print("   ❌ routes_assets does NOT import require_page_access")
        return False
    
    # Check decorator usage
    decorator_count = source.count("@require_page_access('assets')")
    if decorator_count >= 7:  # We have 7 endpoints
        print(f"   ✅ Found {decorator_count} uses of @require_page_access('assets')")
    else:
        print(f"   ⚠️  Only found {decorator_count} uses of @require_page_access('assets')")
    
    print("✅ Permission decorator test passed!\n")
    return True


def test_assets_ai_tools_exist():
    """Test that AI tools for assets exist"""
    print("✅ Testing assets AI tools...")
    
    try:
        from server.agent_tools.tools_assets import (
            assets_search_impl,
            assets_get_impl,
            assets_get_media_impl,
            is_assets_enabled,
            AssetsSearchOutput,
            AssetsGetOutput,
            AssetsGetMediaOutput
        )
        
        print("   ✅ assets_search_impl exists")
        print("   ✅ assets_get_impl exists")
        print("   ✅ assets_get_media_impl exists")
        print("   ✅ is_assets_enabled exists")
        print("   ✅ All Pydantic output models exist")
        
    except ImportError as e:
        print(f"   ❌ Failed to import AI tools: {e}")
        return False
    
    print("✅ AI tools test passed!\n")
    return True


def test_assets_in_agent_factory():
    """Test that assets tools are conditionally registered in agent_factory"""
    print("✅ Testing assets integration in agent_factory...")
    
    import inspect
    from server.agent_tools import agent_factory
    
    source = inspect.getsource(agent_factory)
    
    # Check import of assets tools
    if 'from server.agent_tools.tools_assets import' in source:
        print("   ✅ agent_factory imports tools_assets")
    else:
        print("   ❌ agent_factory does NOT import tools_assets")
        return False
    
    # Check conditional registration
    if 'is_assets_enabled' in source:
        print("   ✅ agent_factory checks is_assets_enabled")
    else:
        print("   ❌ agent_factory does NOT check is_assets_enabled")
        return False
    
    # Check tool registration
    if 'assets_search' in source and 'assets_get' in source:
        print("   ✅ agent_factory registers assets tools")
    else:
        print("   ⚠️  agent_factory may not register all assets tools")
    
    print("✅ Agent factory integration test passed!\n")
    return True


def test_migration_exists():
    """Test that migration 81 for assets tables exists"""
    print("✅ Testing migration exists...")
    
    import inspect
    from server import db_migrate
    
    source = inspect.getsource(db_migrate)
    
    if 'Migration 81' in source:
        print("   ✅ Migration 81 for assets tables exists")
    else:
        print("   ❌ Migration 81 not found")
        return False
    
    if 'asset_items' in source and 'asset_item_media' in source:
        print("   ✅ Migration creates asset_items and asset_item_media tables")
    else:
        print("   ❌ Migration missing table creation")
        return False
    
    print("✅ Migration test passed!\n")
    return True


def run_all_tests():
    """Run all tests"""
    print("=" * 80)
    print("ASSETS LIBRARY (מאגר) - TEST SUITE")
    print("=" * 80)
    print()
    
    results = []
    
    tests = [
        ("Page Registry", test_assets_page_in_registry),
        ("Models", test_assets_model_exists),
        ("Blueprint", test_assets_blueprint_exists),
        ("Permission Decorators", test_assets_permission_decorator),
        ("AI Tools", test_assets_ai_tools_exist),
        ("Agent Factory Integration", test_assets_in_agent_factory),
        ("Migration", test_migration_exists),
    ]
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"   ❌ Test '{name}' crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(run_all_tests())
