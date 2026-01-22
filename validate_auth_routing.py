#!/usr/bin/env python3
"""
Static validation of auth routing configuration
This script validates the auth routing setup without running the Flask app
"""
import os
import re
import sys

def check_file_exists(filepath, description):
    """Check if a file exists"""
    if os.path.exists(filepath):
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description}: NOT FOUND - {filepath}")
        return False

def check_content(filepath, pattern, description):
    """Check if file contains a specific pattern"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            if re.search(pattern, content, re.MULTILINE):
                print(f"✅ {description}")
                return True
            else:
                print(f"❌ {description} - pattern not found")
                return False
    except Exception as e:
        print(f"❌ {description} - error reading file: {e}")
        return False

def main():
    print("🔍 Validating Auth Routing Configuration")
    print("=" * 60)
    
    checks_passed = 0
    checks_total = 0
    
    # Check 1: auth_api.py exists
    checks_total += 1
    if check_file_exists('server/auth_api.py', 'Auth API module'):
        checks_passed += 1
        
        # Check 1a: Blueprint has correct url_prefix
        checks_total += 1
        if check_content('server/auth_api.py', 
                        r"auth_api\s*=\s*Blueprint\([^)]+url_prefix\s*=\s*['\"]\/api\/auth['\"]",
                        "  Blueprint url_prefix is '/api/auth'"):
            checks_passed += 1
        
        # Check 1b: CSRF endpoint exists with GET
        checks_total += 1
        if check_content('server/auth_api.py',
                        r"@auth_api\.get\(['\"]\/csrf['\"]",
                        "  GET /csrf endpoint exists"):
            checks_passed += 1
        
        # Check 1c: Me endpoint exists with GET
        checks_total += 1
        if check_content('server/auth_api.py',
                        r"@auth_api\.route\(['\"]\/me['\"].*methods\s*=\s*\[['\"]GET['\"]\]|@auth_api\.get\(['\"]\/me['\"]",
                        "  GET /me endpoint exists"):
            checks_passed += 1
        
        # Check 1d: Login endpoint exists with POST
        checks_total += 1
        if check_content('server/auth_api.py',
                        r"@auth_api\.route\(['\"]\/login['\"].*methods\s*=\s*\[['\"]POST['\"]|@auth_api\.post\(['\"]\/login['\"]",
                        "  POST /login endpoint exists"):
            checks_passed += 1
    
    # Check 2: app_factory.py registers blueprint
    checks_total += 1
    if check_file_exists('server/app_factory.py', 'App factory module'):
        checks_passed += 1
        
        # Check 2a: Import auth_api
        checks_total += 1
        if check_content('server/app_factory.py',
                        r"from server\.auth_api import auth_api",
                        "  Imports auth_api blueprint"):
            checks_passed += 1
        
        # Check 2b: Register blueprint
        checks_total += 1
        if check_content('server/app_factory.py',
                        r"app\.register_blueprint\(auth_api\)",
                        "  Registers auth_api blueprint"):
            checks_passed += 1
        
        # Check 2c: Route audit added
        checks_total += 1
        if check_content('server/app_factory.py',
                        r"Auth route audit|auth.*route.*audit",
                        "  Route audit guardrail added"):
            checks_passed += 1
    
    # Check 3: NGINX config template
    checks_total += 1
    if check_file_exists('docker/nginx/templates/prosaas.conf.template', 'NGINX config template'):
        checks_passed += 1
        
        # Check 3a: API location block
        checks_total += 1
        if check_content('docker/nginx/templates/prosaas.conf.template',
                        r"location\s+\/api\/",
                        "  location /api/ block exists"):
            checks_passed += 1
        
        # Check 3b: Proxy pass with variable (WITHOUT /api/ suffix to prevent double path)
        checks_total += 1
        if check_content('docker/nginx/templates/prosaas.conf.template',
                        r"proxy_pass\s+http:\/\/\$api_upstream\s*;",
                        "  proxy_pass uses $api_upstream (no /api/ suffix - correct!)"):
            checks_passed += 1
    
    # Check 4: Frontend auth API
    checks_total += 1
    if check_file_exists('client/src/features/auth/api.ts', 'Frontend auth API'):
        checks_passed += 1
        
        # Check 4a: CSRF endpoint
        checks_total += 1
        if check_content('client/src/features/auth/api.ts',
                        r"['\"]\/api\/auth\/csrf['\"]",
                        "  Frontend calls /api/auth/csrf"):
            checks_passed += 1
        
        # Check 4b: Me endpoint
        checks_total += 1
        if check_content('client/src/features/auth/api.ts',
                        r"['\"]\/api\/auth\/me['\"]",
                        "  Frontend calls /api/auth/me"):
            checks_passed += 1
        
        # Check 4c: Login endpoint
        checks_total += 1
        if check_content('client/src/features/auth/api.ts',
                        r"['\"]\/api\/auth\/login['\"]",
                        "  Frontend calls /api/auth/login"):
            checks_passed += 1
    
    # Check 5: Test files exist
    checks_total += 1
    if check_file_exists('test_auth_routing.py', 'Auth routing test'):
        checks_passed += 1
    
    checks_total += 1
    if check_file_exists('smoke_test_auth.sh', 'Smoke test script'):
        checks_passed += 1
    
    checks_total += 1
    if check_file_exists('AUTH_ROUTING_FIX_DOCUMENTATION.md', 'Documentation'):
        checks_passed += 1
    
    print("=" * 60)
    print(f"Results: {checks_passed}/{checks_total} checks passed")
    print("=" * 60)
    
    if checks_passed == checks_total:
        print("✅ All validation checks passed!")
        print("✅ Auth routing configuration is correct")
        return 0
    else:
        print(f"⚠️ {checks_total - checks_passed} validation check(s) failed")
        print("⚠️ Please review the configuration")
        return 1

if __name__ == '__main__':
    os.chdir('/home/runner/work/prosaasil/prosaasil')
    sys.exit(main())
