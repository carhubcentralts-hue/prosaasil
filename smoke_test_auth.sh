#!/bin/bash
# ===========================================
# Auth Routing Smoke Tests
# ===========================================
# This script validates that auth endpoints are accessible
# and return correct status codes.
#
# Usage:
#   ./smoke_test_auth.sh [BASE_URL]
#
# Default BASE_URL: https://prosaas.pro
# ===========================================

set -e

BASE_URL="${1:-https://prosaas.pro}"
PASS=0
FAIL=0

echo "🔍 Testing auth endpoints at: $BASE_URL"
echo "========================================="

# Helper function to test endpoint
test_endpoint() {
    local method=$1
    local path=$2
    local expected_status=$3
    local description=$4
    local data=$5
    
    echo -n "Testing $method $path ... "
    
    if [ "$method" = "GET" ]; then
        status=$(curl -s -o /dev/null -w "%{http_code}" -X GET "$BASE_URL$path")
    elif [ "$method" = "POST" ]; then
        status=$(curl -s -o /dev/null -w "%{http_code}" \
            -X POST "$BASE_URL$path" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi
    
    if [ "$status" = "$expected_status" ]; then
        echo "✅ PASS ($status) - $description"
        ((PASS++))
    else
        echo "❌ FAIL (got $status, expected $expected_status) - $description"
        ((FAIL++))
    fi
}

# Test 1: Health endpoint (baseline test)
test_endpoint "GET" "/health" "200" "Health check endpoint"

# Test 2: CSRF token endpoint
test_endpoint "GET" "/api/auth/csrf" "200" "CSRF token should be accessible"

# Test 3: Me endpoint (should return 401 when not authenticated, not 404)
test_endpoint "GET" "/api/auth/me" "401" "Me endpoint should return 401 when not authenticated (not 404)"

# Test 4: Login endpoint with valid structure (should not return 405)
# Note: Will return 401 for invalid credentials, but that's better than 405
login_data='{"email":"test@example.com","password":"test123"}'
test_endpoint "POST" "/api/auth/login" "401" "Login endpoint should accept POST method (401 for invalid creds, not 405)" "$login_data"

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed"
echo "========================================="

if [ $FAIL -gt 0 ]; then
    echo "❌ Some tests failed!"
    exit 1
else
    echo "✅ All tests passed!"
    exit 0
fi
