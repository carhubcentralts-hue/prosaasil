#!/usr/bin/env python3
"""
API Smoke Test - Validates critical endpoints after deployment
Tests all endpoints mentioned in the production fix guide
"""
import requests
import sys
import os
from typing import List, Tuple

# Color codes for terminal output
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def test_endpoint(base_url: str, path: str, expected_status: List[int], name: str = None) -> Tuple[bool, str]:
    """
    Test a single endpoint
    
    Args:
        base_url: Base URL of the application
        path: Endpoint path to test
        expected_status: List of acceptable HTTP status codes
        name: Optional display name for the endpoint
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    url = f"{base_url}{path}"
    display_name = name or path
    
    try:
        response = requests.get(url, timeout=10, allow_redirects=False)
        status = response.status_code
        
        if status in expected_status:
            return True, f"{GREEN}✓{RESET} {display_name}: {status}"
        elif status == 404:
            return False, f"{RED}✗{RESET} {display_name}: 404 NOT FOUND"
        elif status == 401:
            return True, f"{GREEN}✓{RESET} {display_name}: {status} (auth required - endpoint exists)"
        elif status == 403:
            return True, f"{GREEN}✓{RESET} {display_name}: {status} (forbidden - endpoint exists)"
        else:
            return False, f"{YELLOW}⚠{RESET} {display_name}: Unexpected {status}"
    except requests.exceptions.RequestException as e:
        return False, f"{RED}✗{RESET} {display_name}: Connection error - {str(e)}"

def run_smoke_tests(base_url: str = None) -> bool:
    """
    Run all smoke tests
    
    Args:
        base_url: Base URL to test (default: from env or https://prosaas.pro)
    
    Returns:
        True if all critical tests pass, False otherwise
    """
    if base_url is None:
        base_url = os.getenv('API_BASE_URL', 'https://prosaas.pro')
    
    # Remove trailing slash
    base_url = base_url.rstrip('/')
    
    print(f"\n{BLUE}═══════════════════════════════════════════════════════════{RESET}")
    print(f"{BLUE}API Smoke Test - Production Readiness Check{RESET}")
    print(f"{BLUE}Testing: {base_url}{RESET}")
    print(f"{BLUE}═══════════════════════════════════════════════════════════{RESET}\n")
    
    # Define all critical endpoints to test
    # Format: (path, expected_status_codes, display_name)
    tests = [
        # Health endpoints - must return 200
        ("/health", [200], "Health Check"),
        ("/api/health", [200], "API Health"),
        
        # Auth endpoints - should exist (401/403 is OK, 404 is not)
        ("/api/auth/csrf", [200, 401], "CSRF Token"),
        ("/api/auth/me", [200, 401], "Auth Me"),
        
        # Dashboard endpoints - critical for UI
        ("/api/dashboard/stats?time_filter=today", [200, 401, 403], "Dashboard Stats"),
        ("/api/dashboard/activity?time_filter=today", [200, 401, 403], "Dashboard Activity"),
        
        # Business endpoints - critical for settings
        ("/api/business/current", [200, 401, 403], "Business Current"),
        ("/api/business/current/prompt", [200, 401, 403], "Business Current Prompt"),
        
        # Search endpoint
        ("/api/search?q=test", [200, 401, 403], "Global Search"),
        
        # Leads endpoint - critical for core functionality
        ("/api/leads?page=1&pageSize=1", [200, 401, 403], "Leads List"),
        
        # CRM endpoints
        ("/api/crm/threads", [200, 401, 403], "CRM Threads"),
        
        # WhatsApp endpoints - critical for messaging
        ("/api/whatsapp/status", [200, 401, 403], "WhatsApp Status"),
        ("/api/whatsapp/templates", [200, 401, 403], "WhatsApp Templates"),
        ("/api/whatsapp/broadcasts", [200, 401, 403], "WhatsApp Broadcasts"),
        
        # Notifications endpoint
        ("/api/notifications", [200, 204, 401, 403], "Notifications"),
        
        # Admin endpoints
        ("/api/admin/businesses?pageSize=1", [200, 401, 403], "Admin Businesses"),
        
        # Outbound endpoints
        ("/api/outbound/import-lists", [200, 401, 403], "Outbound Import Lists"),
        ("/api/outbound_calls/counts", [200, 401, 403], "Outbound Call Counts"),
        
        # Status endpoint (from problem statement)
        ("/api/statuses", [200, 401, 403], "Statuses"),
    ]
    
    results = []
    for path, expected_codes, name in tests:
        success, message = test_endpoint(base_url, path, expected_codes, name)
        results.append((success, message))
        print(message)
    
    # Summary
    passed = sum(1 for success, _ in results if success)
    total = len(results)
    failed = total - passed
    
    print(f"\n{BLUE}═══════════════════════════════════════════════════════════{RESET}")
    print(f"{BLUE}Results: {passed}/{total} tests passed{RESET}")
    
    if failed > 0:
        print(f"{RED}Failed: {failed} endpoints returning 404 or errors{RESET}")
        print(f"{RED}❌ SMOKE TEST FAILED - NOT PRODUCTION READY{RESET}")
        print(f"\n{YELLOW}Common fixes:{RESET}")
        print(f"  1. Check nginx.conf has trailing slashes: location /api/ {{ proxy_pass http://backend:5000/api/; }}")
        print(f"  2. Verify all blueprints are registered in server/app_factory.py")
        print(f"  3. Restart nginx and backend containers")
    else:
        print(f"{GREEN}✅ ALL TESTS PASSED - PRODUCTION READY{RESET}")
    
    print(f"{BLUE}═══════════════════════════════════════════════════════════{RESET}\n")
    
    return failed == 0

if __name__ == "__main__":
    # Allow base URL as command line argument
    base_url = sys.argv[1] if len(sys.argv) > 1 else None
    
    success = run_smoke_tests(base_url)
    sys.exit(0 if success else 1)
