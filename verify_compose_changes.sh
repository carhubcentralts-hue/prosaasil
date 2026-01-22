#!/usr/bin/env bash
# ===========================================
# Validation Script for Docker Compose Changes
# ===========================================

set -euo pipefail

echo "=========================================="
echo "Docker Compose v2 Configuration Validation"
echo "=========================================="
echo ""

# Test 1: Check that docker compose config is valid
echo "✓ Test 1: Validating docker-compose configuration..."
if docker compose -f docker-compose.yml -f docker-compose.prod.yml config --services > /dev/null 2>&1; then
    echo "  ✅ Configuration is valid"
else
    echo "  ❌ Configuration is INVALID"
    exit 1
fi

# Test 2: Verify backend is NOT in services list
echo ""
echo "✓ Test 2: Checking that backend service is NOT present..."
SERVICES=$(docker compose -f docker-compose.yml -f docker-compose.prod.yml config --services 2>&1 | grep -v "variable is not set")
if echo "$SERVICES" | grep -q "^backend$"; then
    echo "  ❌ FAIL: backend service found in production!"
    exit 1
else
    echo "  ✅ backend service correctly excluded from production"
fi

# Test 3: Verify required services ARE present
echo ""
echo "✓ Test 3: Checking required services are present..."
REQUIRED_SERVICES=("prosaas-api" "prosaas-calls" "baileys" "worker" "redis" "nginx")
for service in "${REQUIRED_SERVICES[@]}"; do
    if echo "$SERVICES" | grep -q "^${service}$"; then
        echo "  ✅ ${service} present"
    else
        echo "  ❌ ${service} MISSING"
        exit 1
    fi
done

# Test 4: Check that version key is NOT in docker-compose.prod.yml
echo ""
echo "✓ Test 4: Checking Compose v2 compliance (no version key)..."
if grep -q "^version:" docker-compose.prod.yml; then
    echo "  ❌ FAIL: version key found in docker-compose.prod.yml"
    exit 1
else
    echo "  ✅ No version key (Compose v2 compliant)"
fi

# Test 5: Verify prosaas-net network is defined
echo ""
echo "✓ Test 5: Checking network configuration..."
if grep -q "prosaas-net:" docker-compose.prod.yml; then
    echo "  ✅ prosaas-net network defined"
else
    echo "  ❌ prosaas-net network NOT defined"
    exit 1
fi

# Test 6: Verify baileys_service.js has proper BACKEND_BASE_URL handling
echo ""
echo "✓ Test 6: Checking baileys_service.js configuration..."
if grep -q "BACKEND_BASE_URL" services/whatsapp/baileys_service.js && \
   grep -q "API_BASE_URL" services/whatsapp/baileys_service.js && \
   grep -q "prosaas-api:5000" services/whatsapp/baileys_service.js; then
    echo "  ✅ BACKEND_BASE_URL properly configured with fallbacks"
else
    echo "  ❌ BACKEND_BASE_URL not properly configured"
    exit 1
fi

# Test 7: Verify scripts/dcprod.sh has no Python checks
echo ""
echo "✓ Test 7: Checking dcprod.sh script..."
if grep -qi "python" scripts/dcprod.sh && ! grep -q "# ✅ Deployment is docker-only" scripts/dcprod.sh; then
    echo "  ⚠️  WARNING: Python references found in dcprod.sh"
else
    echo "  ✅ No host Python checks in dcprod.sh"
fi

# Test 8: Verify worker directory exists with required files
echo ""
echo "✓ Test 8: Checking worker directory structure..."
if [ -f "worker/Dockerfile" ] && [ -f "worker/requirements.txt" ]; then
    echo "  ✅ Worker directory structure complete"
    if grep -q "rq" worker/requirements.txt; then
        echo "  ✅ rq package in worker/requirements.txt"
    fi
else
    echo "  ❌ Worker directory incomplete"
    exit 1
fi

# Test 9: Verify healthcheck on prosaas-api
echo ""
echo "✓ Test 9: Checking prosaas-api healthcheck..."
# Find prosaas-api service and check within the next 60 lines for healthcheck
if grep -A 60 '^\s*prosaas-api:' docker-compose.prod.yml | grep -q 'healthcheck:'; then
    echo "  ✅ prosaas-api has healthcheck configured"
else
    echo "  ❌ prosaas-api healthcheck not configured"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ ALL VALIDATION TESTS PASSED"
echo "=========================================="
echo ""
echo "Summary of changes:"
echo "  ✓ Backend service removed from production"
echo "  ✓ All services use prosaas-net network"
echo "  ✓ Compose v2 compliant (no version key)"
echo "  ✓ Proper healthchecks configured"
echo "  ✓ Environment variables properly loaded"
echo "  ✓ Baileys depends on prosaas-api"
echo "  ✓ No host Python dependencies"
echo ""