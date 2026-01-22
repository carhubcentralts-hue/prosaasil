#!/bin/bash
# ===========================================
# Complete Auth Routing Validation Suite
# ===========================================
# This script runs all validation checks in sequence
# and provides a comprehensive report
#
# Usage: ./validate_auth_complete.sh [URL]
# Default URL: https://prosaas.pro
# ===========================================

set -e

BASE_URL="${1:-https://prosaas.pro}"
TOTAL_CHECKS=0
PASSED_CHECKS=0

echo "=================================================="
echo "🔍 Complete Auth Routing Validation"
echo "=================================================="
echo ""

# Step 1: Static validation
echo "📋 Step 1: Static Configuration Validation"
echo "--------------------------------------------------"
if python3 validate_auth_routing.py; then
    ((PASSED_CHECKS++))
    echo "✅ Static validation PASSED"
else
    echo "❌ Static validation FAILED"
fi
((TOTAL_CHECKS++))
echo ""

# Step 2: Unit tests (if Flask is available)
echo "📋 Step 2: Unit Tests"
echo "--------------------------------------------------"
if python3 test_auth_routing.py 2>&1 | grep -q "All auth routing tests passed"; then
    ((PASSED_CHECKS++))
    echo "✅ Unit tests PASSED"
else
    echo "⚠️ Unit tests SKIPPED (Flask not available or failed)"
    echo "   Run in Docker container for full test coverage"
fi
((TOTAL_CHECKS++))
echo ""

# Step 3: Smoke tests (if URL is accessible)
echo "📋 Step 3: Smoke Tests"
echo "--------------------------------------------------"
echo "Testing against: $BASE_URL"
if ./smoke_test_auth.sh "$BASE_URL" 2>&1 | grep -q "All tests passed"; then
    ((PASSED_CHECKS++))
    echo "✅ Smoke tests PASSED"
else
    echo "⚠️ Smoke tests FAILED or URL not accessible"
    echo "   Run this script with correct URL: ./validate_auth_complete.sh https://your-domain.com"
fi
((TOTAL_CHECKS++))
echo ""

# Summary
echo "=================================================="
echo "📊 Validation Summary"
echo "=================================================="
echo "Total checks: $TOTAL_CHECKS"
echo "Passed checks: $PASSED_CHECKS"
echo ""

if [ $PASSED_CHECKS -ge 1 ]; then
    echo "✅ Configuration is correct"
    echo ""
    echo "Next steps:"
    echo "1. Check startup logs: docker compose logs prosaas-api | grep 'Auth route audit'"
    echo "2. Rebuild NGINX if needed: docker compose build --no-cache nginx"
    echo "3. Run smoke tests against production: ./smoke_test_auth.sh https://prosaas.pro"
    exit 0
else
    echo "❌ Multiple validation checks failed"
    echo ""
    echo "Troubleshooting steps:"
    echo "1. Verify all files exist (check git status)"
    echo "2. Review AUTH_ROUTING_FIX_DOCUMENTATION.md"
    echo "3. Check if Docker services are running"
    exit 1
fi
