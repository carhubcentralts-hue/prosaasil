#!/bin/bash
# ===========================================
# Auth Endpoint Guardrail - Deployment Check
# ===========================================
# This script MUST pass before deploying to production
# If it returns exit code 1, the deployment FAILS
#
# Usage: ./verify_auth_endpoints.sh [URL]
# Default: https://prosaas.pro
# ===========================================

set -e

BASE_URL="${1:-https://prosaas.pro}"

echo "🔥 Critical Auth Endpoint Check"
echo "Testing: $BASE_URL"
echo ""

# Test 1: CSRF endpoint must return 200
echo -n "Testing GET /api/auth/csrf ... "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$BASE_URL/api/auth/csrf")
if [ "$STATUS" = "200" ]; then
    echo "✅ PASS ($STATUS)"
else
    echo "❌ FAIL ($STATUS) - Expected 200"
    echo "🔥 CRITICAL: CSRF endpoint not accessible - DEPLOYMENT BLOCKED"
    exit 1
fi

# Test 2: Me endpoint must return 401 (not 404!)
echo -n "Testing GET /api/auth/me ... "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$BASE_URL/api/auth/me")
if [ "$STATUS" = "401" ]; then
    echo "✅ PASS ($STATUS - unauthenticated)"
else
    echo "❌ FAIL ($STATUS) - Expected 401, got $STATUS"
    if [ "$STATUS" = "404" ]; then
        echo "🔥 CRITICAL: Route not found (404) - Check NGINX proxy_pass configuration"
    fi
    echo "🔥 DEPLOYMENT BLOCKED"
    exit 1
fi

# Test 3: Login endpoint must accept POST (return 401/422, NOT 405!)
echo -n "Testing POST /api/auth/login ... "
STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
    -X POST "$BASE_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"test","password":"test"}')

if echo "$STATUS" | grep -qE "401|422|400"; then
    echo "✅ PASS ($STATUS - POST accepted)"
else
    echo "❌ FAIL ($STATUS) - Expected 401/422/400"
    if [ "$STATUS" = "405" ]; then
        echo "🔥 CRITICAL: Method Not Allowed (405) - Check NGINX proxy_pass configuration"
        echo "🔥 This usually means NGINX is appending /api/ twice: /api/api/auth/login"
    fi
    if [ "$STATUS" = "404" ]; then
        echo "🔥 CRITICAL: Route not found (404) - Check NGINX proxy_pass configuration"
    fi
    echo "🔥 DEPLOYMENT BLOCKED"
    exit 1
fi

echo ""
echo "✅ All critical auth endpoints are accessible"
echo "✅ Deployment can proceed"
exit 0
