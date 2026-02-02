#!/usr/bin/env python3
"""
Production Hardening Validation Script

This script validates all the production-grade hardening changes:
1. Internal authentication module
2. Protected endpoints
3. Configuration files
4. Security headers
5. Environment variables
"""

import os
import sys
import subprocess
from pathlib import Path

# ANSI colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'=' * 80}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'=' * 80}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✅ {text}{RESET}")

def print_error(text):
    print(f"{RED}❌ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}⚠️  {text}{RESET}")

def check_file_exists(filepath, description):
    """Check if a file exists"""
    if Path(filepath).exists():
        print_success(f"{description} exists: {filepath}")
        return True
    else:
        print_error(f"{description} missing: {filepath}")
        return False

def check_python_syntax(filepath):
    """Check Python file syntax"""
    try:
        subprocess.run(['python3', '-m', 'py_compile', filepath], 
                      check=True, capture_output=True)
        print_success(f"Python syntax valid: {filepath}")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Python syntax error in {filepath}: {e.stderr.decode()}")
        return False

def check_string_in_file(filepath, search_string, description):
    """Check if a string exists in a file"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            if search_string in content:
                print_success(f"{description} found in {filepath}")
                return True
            else:
                print_error(f"{description} NOT found in {filepath}")
                return False
    except Exception as e:
        print_error(f"Error reading {filepath}: {e}")
        return False

def main():
    print_header("Production Hardening Validation")
    
    repo_root = Path(__file__).parent.parent
    os.chdir(repo_root)
    
    all_checks_passed = True
    
    # Phase 1: Critical Bug Fixes
    print_header("Phase 1: Critical Bug Fixes")
    
    # Check jsonify import
    if not check_string_in_file(
        'server/routes_twilio.py',
        'from flask import Blueprint, request, current_app, make_response, Response, jsonify',
        'jsonify import'
    ):
        all_checks_passed = False
    
    # Check backend alias
    if not check_string_in_file(
        'docker-compose.prod.yml',
        '- backend  # Alias for nginx compatibility',
        'backend alias in docker-compose.prod.yml'
    ):
        all_checks_passed = False
    
    # Phase 2: Internal Authentication
    print_header("Phase 2: Internal Authentication")
    
    if not check_file_exists('server/security/internal_auth.py', 'Internal auth module'):
        all_checks_passed = False
    else:
        if not check_python_syntax('server/security/internal_auth.py'):
            all_checks_passed = False
    
    # Check protected endpoints
    if not check_string_in_file(
        'server/routes_jobs.py',
        'from server.security.internal_auth import require_internal_secret',
        'require_internal_secret import in routes_jobs.py'
    ):
        all_checks_passed = False
    
    if not check_string_in_file(
        'server/routes_jobs.py',
        '@require_internal_secret()',
        '@require_internal_secret() decorator in routes_jobs.py'
    ):
        all_checks_passed = False
    
    if not check_string_in_file(
        'server/routes_twilio.py',
        'from server.security.internal_auth import require_internal_secret',
        'require_internal_secret import in routes_twilio.py'
    ):
        all_checks_passed = False
    
    # Phase 4: Nginx Security
    print_header("Phase 4: Nginx Security Headers")
    
    # Check server_tokens in main nginx.conf
    if not check_string_in_file(
        'docker/nginx/nginx.conf',
        'server_tokens off;',
        'server_tokens off in nginx.conf'
    ):
        all_checks_passed = False
    
    # Check security headers in SSL template
    headers_to_check = [
        ('Referrer-Policy', 'Referrer-Policy header'),
        ('Permissions-Policy', 'Permissions-Policy header'),
        ('Cross-Origin-Opener-Policy', 'COOP header'),
        ('Cross-Origin-Resource-Policy', 'CORP header'),
        ('Cross-Origin-Embedder-Policy', 'COEP header'),
        ('Content-Security-Policy', 'CSP header'),
    ]
    
    for header, description in headers_to_check:
        if not check_string_in_file(
            'docker/nginx/templates/prosaas-ssl.conf.template',
            header,
            description
        ):
            all_checks_passed = False
    
    # Phase 5: Environment Configuration
    print_header("Phase 5: Environment Configuration")
    
    if not check_string_in_file(
        '.env.example',
        'INTERNAL_SECRET=',
        'INTERNAL_SECRET in .env.example'
    ):
        all_checks_passed = False
    
    if not check_string_in_file(
        '.env.example',
        'COOKIE_SECURE=',
        'COOKIE_SECURE in .env.example'
    ):
        all_checks_passed = False
    
    # Phase 6: CI/CD Pipeline
    print_header("Phase 6: CI/CD Pipeline")
    
    if not check_file_exists('.github/workflows/ci.yml', 'GitHub Actions CI workflow'):
        all_checks_passed = False
    else:
        # Check CI includes key steps
        ci_checks = [
            ('pip-audit', 'Backend security scanning'),
            ('npm audit', 'Frontend security scanning'),
            ('sourcemap', 'Sourcemap validation'),
            ('docker compose', 'Docker validation'),
        ]
        
        for check_string, description in ci_checks:
            if not check_string_in_file(
                '.github/workflows/ci.yml',
                check_string,
                description
            ):
                all_checks_passed = False
    
    # Phase 7: Vite Configuration
    print_header("Phase 7: Frontend Build Configuration")
    
    if not check_string_in_file(
        'client/vite.config.js',
        "sourcemap: mode !== 'production'",
        'Sourcemap disabled in production'
    ):
        all_checks_passed = False
    
    # Summary
    print_header("Validation Summary")
    
    if all_checks_passed:
        print_success("All validation checks passed! ✨")
        return 0
    else:
        print_error("Some validation checks failed. Please review the output above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
