#!/bin/bash
# ===========================================
# Pre-Deployment Verification Script
# Runs route existence test before deployment
# ===========================================

set -euo pipefail

echo "═══════════════════════════════════════════════════════════"
echo "Pre-Deployment Verification"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Set migration mode to avoid DB connection during tests
export MIGRATION_MODE=1

echo "Step 1: Testing route registration..."
echo "───────────────────────────────────────────────────────────"

# Run the route existence test
if command -v pytest &> /dev/null; then
    echo "Running pytest..."
    python3 -m pytest tests/test_api_routes.py -v
    TEST_RESULT=$?
else
    echo "pytest not found, running test directly..."
    python3 tests/test_api_routes.py
    TEST_RESULT=$?
fi

if [ $TEST_RESULT -eq 0 ]; then
    echo ""
    echo "✅ Route registration test PASSED"
else
    echo ""
    echo "❌ Route registration test FAILED"
    echo "   Critical API routes are not being registered!"
    echo "   Check server/app_factory.py for blueprint registration errors"
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "✅ Pre-deployment verification PASSED"
echo "   Safe to deploy!"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "After deployment, run:"
echo "  ./scripts/verify_critical_endpoints.sh https://your-domain.com"
echo ""

exit 0
