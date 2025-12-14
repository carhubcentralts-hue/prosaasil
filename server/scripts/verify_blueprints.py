#!/usr/bin/env python3
"""
Blueprint Registration Verification Script
Verifies all required blueprints are registered in app_factory.py
"""

import re
from pathlib import Path

# Define required endpoints based on the problem statement
REQUIRED_ENDPOINTS = {
    '/api/dashboard/stats': 'api_adapter_bp',
    '/api/dashboard/activity': 'api_adapter_bp',
    '/api/leads': 'leads_bp',
    '/api/crm/threads': 'crm_bp',
    '/api/whatsapp/status': 'whatsapp_bp',
    '/api/whatsapp/templates': 'whatsapp_bp',
    '/api/whatsapp/broadcasts': 'whatsapp_bp',
    '/api/notifications': 'leads_bp',
    '/api/admin/businesses': 'admin_bp',
    '/api/outbound/import-lists': 'outbound_bp',
    '/api/outbound_calls/counts': 'outbound_bp',
    '/api/statuses': 'status_management_bp',
}

def extract_registered_blueprints(app_factory_path):
    """Extract all registered blueprints from app_factory.py"""
    with open(app_factory_path, 'r') as f:
        content = f.read()
    
    # Find all app.register_blueprint calls
    pattern = r'app\.register_blueprint\(([^,)]+)'
    matches = re.findall(pattern, content)
    
    return [bp.strip() for bp in matches]

def extract_blueprint_imports(app_factory_path):
    """Extract all blueprint imports from app_factory.py"""
    with open(app_factory_path, 'r') as f:
        content = f.read()
    
    # Find import statements for blueprints
    pattern = r'from server\.[\w_]+ import ([\w_]+(?:_bp|_api))'
    matches = re.findall(pattern, content)
    
    return matches

def main():
    project_root = Path(__file__).parent.parent.parent
    app_factory_path = project_root / 'server' / 'app_factory.py'
    
    print("=" * 60)
    print("Blueprint Registration Verification")
    print("=" * 60)
    
    # Get registered blueprints
    registered = extract_registered_blueprints(app_factory_path)
    imported = extract_blueprint_imports(app_factory_path)
    
    print(f"\n✓ Found {len(registered)} registered blueprints:")
    for bp in sorted(registered):
        print(f"  - {bp}")
    
    print(f"\n✓ Found {len(imported)} imported blueprints:")
    for bp in sorted(set(imported)):
        print(f"  - {bp}")
    
    # Check for required blueprints
    print("\n" + "=" * 60)
    print("Required Endpoints Check")
    print("=" * 60)
    
    missing_blueprints = []
    for endpoint, required_bp in REQUIRED_ENDPOINTS.items():
        if required_bp in registered:
            print(f"✓ {endpoint:<35} -> {required_bp}")
        else:
            print(f"✗ {endpoint:<35} -> {required_bp} (NOT REGISTERED)")
            missing_blueprints.append(required_bp)
    
    print("\n" + "=" * 60)
    if missing_blueprints:
        print(f"❌ MISSING BLUEPRINTS: {set(missing_blueprints)}")
        print("These blueprints need to be registered in app_factory.py")
        return 1
    else:
        print("✅ ALL REQUIRED BLUEPRINTS ARE REGISTERED")
        return 0

if __name__ == '__main__':
    exit(main())
