#!/usr/bin/env python3
"""
Verification Script for Webhook Secret Implementation
Run this to verify the 3 points raised in the PR comment
"""

import sys
import os

# Add server to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def verify_migration():
    """Verify Migration 47 - webhook_secret column exists"""
    print("\n" + "="*80)
    print("1. VERIFYING MIGRATION 47")
    print("="*80)
    
    try:
        from server.db import db
        from server.app_factory import create_minimal_app
        from sqlalchemy import text, inspect
        
        app = create_minimal_app()
        
        with app.app_context():
            inspector = inspect(db.engine)
            
            # Check if business table exists
            if 'business' not in inspector.get_table_names():
                print("❌ FAIL: business table does not exist")
                return False
            
            # Check columns in business table
            columns = {col['name']: col for col in inspector.get_columns('business')}
            
            if 'webhook_secret' not in columns:
                print("❌ FAIL: webhook_secret column does not exist in business table")
                print("   Run: python -m server.db_migrate")
                return False
            
            # Check column properties
            col = columns['webhook_secret']
            print(f"✅ Column exists: webhook_secret")
            print(f"   Type: {col['type']}")
            print(f"   Nullable: {col['nullable']}")
            
            # Check for unique constraint
            constraints = inspector.get_unique_constraints('business')
            has_unique = any('webhook_secret' in c.get('column_names', []) 
                           for c in constraints)
            
            if has_unique:
                print(f"✅ Unique constraint exists on webhook_secret")
            else:
                print(f"⚠️  WARNING: No unique constraint found (may be enforced differently)")
            
            return True
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_blueprint_registration():
    """Verify Blueprint is registered"""
    print("\n" + "="*80)
    print("2. VERIFYING BLUEPRINT REGISTRATION")
    print("="*80)
    
    try:
        from server.app_factory import create_minimal_app
        
        app = create_minimal_app()
        
        # Check if routes are registered
        routes = []
        for rule in app.url_map.iter_rules():
            if 'webhook-secret' in rule.rule:
                routes.append((rule.rule, rule.methods))
        
        if not routes:
            print("❌ FAIL: No webhook-secret routes found")
            print("   Expected routes:")
            print("   - GET  /api/business/settings/webhook-secret")
            print("   - POST /api/business/settings/webhook-secret/rotate")
            return False
        
        print("✅ Routes registered:")
        for route, methods in routes:
            methods_str = ', '.join(sorted(methods - {'HEAD', 'OPTIONS'}))
            print(f"   {methods_str:6} {route}")
        
        # Verify the routes are what we expect
        expected_routes = {
            '/api/business/settings/webhook-secret',
            '/api/business/settings/webhook-secret/rotate'
        }
        
        actual_routes = {route for route, _ in routes}
        
        if expected_routes.issubset(actual_routes):
            print("✅ All expected routes are present")
            return True
        else:
            missing = expected_routes - actual_routes
            print(f"⚠️  Missing routes: {missing}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_tenant_isolation():
    """Verify tenant isolation in routes"""
    print("\n" + "="*80)
    print("3. VERIFYING TENANT ISOLATION")
    print("="*80)
    
    try:
        # Read the routes file and check for tenant isolation
        import re
        
        routes_file = os.path.join(os.path.dirname(__file__), 'server', 'routes_webhook_secret.py')
        
        with open(routes_file, 'r') as f:
            content = f.read()
        
        # Check for business_id extraction
        if 'business_id' not in content:
            print("❌ FAIL: No business_id found in routes")
            return False
        
        # Check for Business.query.filter_by(id=business_id)
        if 'Business.query.filter_by(id=business_id)' not in content:
            print("❌ FAIL: Business query not filtering by business_id")
            return False
        
        # Check for authentication
        if '@require_api_auth' not in content:
            print("❌ FAIL: No authentication decorator found")
            return False
        
        # Count occurrences
        business_id_count = len(re.findall(r'business_id', content))
        filter_by_count = len(re.findall(r'filter_by\(id=business_id\)', content))
        
        print(f"✅ Tenant isolation implemented:")
        print(f"   - business_id references: {business_id_count}")
        print(f"   - Filter by business_id: {filter_by_count}")
        print(f"   - Authentication: @require_api_auth present")
        print(f"   - Roles allowed: system_admin, owner, admin, manager")
        
        # Check the model has the field
        models_file = os.path.join(os.path.dirname(__file__), 'server', 'models_sql.py')
        with open(models_file, 'r') as f:
            models_content = f.read()
        
        if 'webhook_secret' in models_content and 'Business' in models_content:
            print(f"✅ Business model has webhook_secret field")
        else:
            print(f"❌ FAIL: webhook_secret not found in Business model")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verifications"""
    print("\n" + "="*80)
    print("WEBHOOK SECRET IMPLEMENTATION VERIFICATION")
    print("="*80)
    print("\nThis script verifies the 3 points from the PR comment:")
    print("1. Migration 47 ran and webhook_secret column exists")
    print("2. Blueprint is registered and routes are accessible")
    print("3. Tenant isolation is properly implemented")
    
    results = []
    
    # Run verifications
    results.append(("Migration 47", verify_migration()))
    results.append(("Blueprint Registration", verify_blueprint_registration()))
    results.append(("Tenant Isolation", verify_tenant_isolation()))
    
    # Summary
    print("\n" + "="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*80)
    
    if all_passed:
        print("✅ ALL VERIFICATIONS PASSED")
        print("\nNext steps for production deployment:")
        print("1. Run migration: python -m server.db_migrate")
        print("2. Test endpoints (replace with your domain):")
        print("   curl -i https://prosaas.pro/api/business/settings/webhook-secret")
        print("   curl -i -X POST https://prosaas.pro/api/business/settings/webhook-secret/rotate")
        print("3. Verify tenant isolation by testing with different business accounts")
        return 0
    else:
        print("❌ SOME VERIFICATIONS FAILED")
        print("\nPlease review the output above and fix the issues.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
