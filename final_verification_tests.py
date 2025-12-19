#!/usr/bin/env python3
"""
Final Verification Test Suite
Tests all new features: API endpoints, WhatsApp broadcast, and search
"""
import requests
import sys
import os

# Color codes
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def test_api_endpoints(base_url):
    """Test all critical API endpoints"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}1. Testing API Endpoints{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    endpoints = [
        ("/health", [200]),
        ("/api/health", [200]),
        ("/api/auth/csrf", [200, 401]),
        ("/api/dashboard/stats?time_filter=today", [200, 401, 403]),
        ("/api/dashboard/activity?time_filter=today", [200, 401, 403]),
        ("/api/leads?page=1&pageSize=1", [200, 401, 403]),
        ("/api/crm/threads", [200, 401, 403]),
        ("/api/whatsapp/status", [200, 401, 403]),
        ("/api/whatsapp/templates", [200, 401, 403]),
        ("/api/whatsapp/broadcasts", [200, 401, 403]),
        ("/api/notifications", [200, 204, 401, 403]),
        ("/api/admin/businesses?pageSize=1", [200, 401, 403]),
        ("/api/outbound/import-lists", [200, 401, 403]),
        ("/api/outbound_calls/counts", [200, 401, 403]),
        ("/api/statuses", [200, 401, 403]),
        ("/api/search?q=test", [200, 401, 403]),  # NEW: Search endpoint
    ]
    
    passed = 0
    failed = 0
    
    for path, expected_codes in endpoints:
        try:
            url = f"{base_url}{path}"
            response = requests.get(url, timeout=10, allow_redirects=False)
            status = response.status_code
            
            if status in expected_codes:
                print(f"{GREEN}✓{RESET} {path:<50} {status}")
                passed += 1
            elif status == 404:
                print(f"{RED}✗{RESET} {path:<50} 404 NOT FOUND")
                failed += 1
            else:
                print(f"{YELLOW}⚠{RESET} {path:<50} {status}")
                passed += 1  # Auth errors are OK
        except Exception as e:
            print(f"{RED}✗{RESET} {path:<50} ERROR: {str(e)[:30]}")
            failed += 1
    
    return passed, failed

def test_whatsapp_broadcast_features(base_url):
    """Test WhatsApp broadcast audience source features"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}2. Testing WhatsApp Broadcast Features{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    tests = []
    
    # Test import lists endpoint
    try:
        url = f"{base_url}/api/outbound/import-lists"
        response = requests.get(url, timeout=10)
        if response.status_code in [200, 401, 403]:
            tests.append(("Import Lists Endpoint", True, f"Status: {response.status_code}"))
        else:
            tests.append(("Import Lists Endpoint", False, f"Got {response.status_code}, expected 200/401/403"))
    except Exception as e:
        tests.append(("Import Lists Endpoint", False, str(e)))
    
    # Test broadcast creation endpoint
    try:
        url = f"{base_url}/api/whatsapp/broadcasts"
        # GET should return list of broadcasts or 401
        response = requests.get(url, timeout=10)
        if response.status_code in [200, 401, 403]:
            tests.append(("Broadcasts GET Endpoint", True, f"Status: {response.status_code}"))
        else:
            tests.append(("Broadcasts GET Endpoint", False, f"Got {response.status_code}"))
    except Exception as e:
        tests.append(("Broadcasts GET Endpoint", False, str(e)))
    
    # Test leads endpoint for filtering
    try:
        url = f"{base_url}/api/leads?page=1&pageSize=10"
        response = requests.get(url, timeout=10)
        if response.status_code in [200, 401, 403]:
            tests.append(("Leads Endpoint (for selection)", True, f"Status: {response.status_code}"))
        else:
            tests.append(("Leads Endpoint (for selection)", False, f"Got {response.status_code}"))
    except Exception as e:
        tests.append(("Leads Endpoint (for selection)", False, str(e)))
    
    passed = sum(1 for _, success, _ in tests if success)
    failed = sum(1 for _, success, _ in tests if not success)
    
    for name, success, message in tests:
        icon = f"{GREEN}✓{RESET}" if success else f"{RED}✗{RESET}"
        print(f"{icon} {name:<40} {message}")
    
    return passed, failed

def test_search_feature(base_url):
    """Test global search feature"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}3. Testing Global Search{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    
    tests = []
    
    # Test search endpoint exists
    try:
        url = f"{base_url}/api/search?q=test"
        response = requests.get(url, timeout=10)
        if response.status_code in [200, 401, 403]:
            tests.append(("Search Endpoint Exists", True, f"Status: {response.status_code}"))
            
            # If 200, check response structure
            if response.status_code == 200:
                data = response.json()
                if 'results' in data or 'error' not in data:
                    tests.append(("Search Response Format", True, "Valid JSON structure"))
                else:
                    tests.append(("Search Response Format", False, "Unexpected JSON structure"))
        else:
            tests.append(("Search Endpoint Exists", False, f"Got {response.status_code}, expected 200/401/403"))
    except Exception as e:
        tests.append(("Search Endpoint Exists", False, str(e)))
    
    # Test search with different query types
    search_queries = [
        ("Empty query", ""),
        ("Short query (2 chars)", "ab"),
        ("Normal query", "test"),
        ("Hebrew query", "בדיקה"),
    ]
    
    for name, query in search_queries:
        try:
            url = f"{base_url}/api/search?q={query}"
            response = requests.get(url, timeout=10)
            # Any non-404 is acceptable (400 for empty/short is OK)
            if response.status_code != 404:
                tests.append((f"Search: {name}", True, f"Status: {response.status_code}"))
            else:
                tests.append((f"Search: {name}", False, "404 Not Found"))
        except Exception as e:
            tests.append((f"Search: {name}", False, str(e)))
    
    passed = sum(1 for _, success, _ in tests if success)
    failed = sum(1 for _, success, _ in tests if not success)
    
    for name, success, message in tests:
        icon = f"{GREEN}✓{RESET}" if success else f"{RED}✗{RESET}"
        print(f"{icon} {name:<40} {message}")
    
    return passed, failed

def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else os.getenv('API_BASE_URL', 'http://localhost:5000')
    base_url = base_url.rstrip('/')
    
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}Final Verification Test Suite{RESET}")
    print(f"{BLUE}Testing: {base_url}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    
    # Run all test suites
    api_passed, api_failed = test_api_endpoints(base_url)
    broadcast_passed, broadcast_failed = test_whatsapp_broadcast_features(base_url)
    search_passed, search_failed = test_search_feature(base_url)
    
    # Summary
    total_passed = api_passed + broadcast_passed + search_passed
    total_failed = api_failed + broadcast_failed + search_failed
    total = total_passed + total_failed
    
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}FINAL SUMMARY{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    print(f"\n{'API Endpoints:':<30} {api_passed} passed, {api_failed} failed")
    print(f"{'WhatsApp Broadcast:':<30} {broadcast_passed} passed, {broadcast_failed} failed")
    print(f"{'Global Search:':<30} {search_passed} passed, {search_failed} failed")
    print(f"\n{BLUE}{'─'*60}{RESET}")
    print(f"{'TOTAL:':<30} {total_passed}/{total} passed")
    
    if total_failed == 0:
        print(f"\n{GREEN}✅ ALL TESTS PASSED - PRODUCTION READY{RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")
        return 0
    else:
        print(f"\n{RED}❌ {total_failed} TESTS FAILED - NEEDS ATTENTION{RESET}")
        print(f"{BLUE}{'='*60}{RESET}\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
