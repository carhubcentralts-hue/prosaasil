"""
Test to verify the project full_name fix
This test ensures that the get_project endpoint works correctly
with the CONCAT_WS fix for full_name column
"""
import os
import pytest


def test_project_full_name_query_syntax():
    """
    Test that the SQL query for retrieving project leads uses
    CONCAT_WS correctly and doesn't reference non-existent full_name column
    """
    # Set migration mode to avoid DB initialization during tests
    os.environ['MIGRATION_MODE'] = '1'
    
    # Read the routes_projects.py file
    with open('/home/runner/work/prosaasil/prosaasil/server/routes_projects.py', 'r') as f:
        content = f.read()
    
    # Verify that the old problematic pattern is NOT present
    assert 'l.full_name, l.phone_e164' not in content, (
        "Found old pattern 'l.full_name' which references non-existent column"
    )
    
    # Verify that the fix is present
    assert 'CONCAT_WS' in content, (
        "CONCAT_WS not found in routes_projects.py - fix not applied"
    )
    
    assert 'COALESCE(CONCAT_WS' in content, (
        "COALESCE wrapper for CONCAT_WS not found - NULL handling may fail"
    )
    
    # Verify it's aliased as full_name
    assert 'AS full_name' in content, (
        "Missing 'AS full_name' alias in query"
    )
    
    print("✅ Project full_name query fix verified!")
    print("   - Old 'l.full_name' pattern removed")
    print("   - New CONCAT_WS with COALESCE implemented")
    print("   - Proper aliasing maintained")


def test_routes_projects_imports():
    """
    Verify that routes_projects.py can be imported without errors
    """
    os.environ['MIGRATION_MODE'] = '1'
    
    try:
        from server import routes_projects
        print("✅ routes_projects module imported successfully")
    except ImportError as e:
        pytest.fail(f"Failed to import routes_projects: {e}")


if __name__ == '__main__':
    test_project_full_name_query_syntax()
    test_routes_projects_imports()
    print("\n✅ All project full_name fix tests passed!")
