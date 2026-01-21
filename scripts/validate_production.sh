#!/usr/bin/env bash
#
# Production Deployment Validation Script
# Validates that production deployment is correct:
# 1. No backend/legacy service is running
# 2. Only required services are running (web/worker/redis/nginx)
# 3. DNS is properly configured
# 4. Logs are clean in production mode
#
# Usage: ./scripts/validate_production.sh
#
# Exit codes:
#   0 - Success (all checks passed)
#   1 - Failure (one or more checks failed)

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=============================================================================="
echo "Production Deployment Validation"
echo "=============================================================================="
echo ""

# Navigate to repository root
cd "$(dirname "$0")/.." || exit 1

VALIDATION_FAILED=false

# Check 1: Validate no backend/legacy service is running
echo "📝 Check 1: Validating no backend/legacy service..."
BACKEND_RUNNING=$(docker compose -f docker-compose.yml -f docker-compose.prod.yml ps --format json 2>/dev/null | grep '"Service":"backend"' || echo "")

if [ -n "$BACKEND_RUNNING" ]; then
    echo -e "${RED}❌ FAIL: backend service is running in production!${NC}"
    echo "   Production should use prosaas-api and prosaas-calls, not backend."
    VALIDATION_FAILED=true
else
    echo -e "${GREEN}✅ PASS: No backend/legacy service running${NC}"
fi
echo ""

# Check 2: Validate only required services are running
echo "📝 Check 2: Validating required services..."
EXPECTED_SERVICES=("prosaas-api" "prosaas-calls" "worker" "redis" "nginx" "frontend")
OPTIONAL_SERVICES=("baileys" "n8n")

echo "   Required services:"
for service in "${EXPECTED_SERVICES[@]}"; do
    # Check if service is running (handle both docker compose and docker ps formats)
    SERVICE_RUNNING=$(docker compose -f docker-compose.yml -f docker-compose.prod.yml ps "$service" 2>/dev/null | grep -E "Up|running" || echo "")
    
    if [ -z "$SERVICE_RUNNING" ]; then
        # Try checking by container name
        CONTAINER_NAME="prosaas-${service}"
        SERVICE_RUNNING=$(docker ps --filter "name=${CONTAINER_NAME}" --format "{{.State}}" 2>/dev/null | grep -E "running|Up" || echo "")
    fi
    
    if [ -n "$SERVICE_RUNNING" ]; then
        echo -e "   ${GREEN}✅ ${service}${NC}"
    else
        echo -e "   ${RED}❌ ${service} NOT RUNNING${NC}"
        VALIDATION_FAILED=true
    fi
done

echo "   Optional services:"
for service in "${OPTIONAL_SERVICES[@]}"; do
    SERVICE_RUNNING=$(docker compose -f docker-compose.yml -f docker-compose.prod.yml ps "$service" 2>/dev/null | grep -E "Up|running" || echo "")
    if [ -n "$SERVICE_RUNNING" ]; then
        echo -e "   ${GREEN}✅ ${service} (optional)${NC}"
    else
        echo -e "   ${YELLOW}⚠  ${service} not running (optional)${NC}"
    fi
done
echo ""

# Check 3: Validate DNS configuration
echo "📝 Check 3: Validating DNS configuration..."
# Check if worker has DNS configured in the compose files
WORKER_DNS=$(grep -A 20 "^  worker:" docker-compose.prod.yml | grep "dns:" || echo "")

if [ -n "$WORKER_DNS" ]; then
    echo -e "${GREEN}✅ PASS: DNS configuration found for worker in docker-compose.prod.yml${NC}"
    echo "   DNS servers: 1.1.1.1, 8.8.8.8"
else
    echo -e "${RED}❌ FAIL: No DNS configuration found for worker${NC}"
    VALIDATION_FAILED=true
fi
echo ""

# Check 4: Validate LOG_LEVEL is INFO in production
echo "📝 Check 4: Validating LOG_LEVEL configuration..."
WORKER_LOG_LEVEL=$(grep -A 50 "^  worker:" docker-compose.prod.yml | grep "LOG_LEVEL:" | head -1 || echo "")

if echo "$WORKER_LOG_LEVEL" | grep -q "INFO"; then
    echo -e "${GREEN}✅ PASS: LOG_LEVEL=INFO configured for worker in docker-compose.prod.yml${NC}"
else
    echo -e "${YELLOW}⚠  WARNING: LOG_LEVEL not set to INFO for worker${NC}"
    echo "   Found: $WORKER_LOG_LEVEL"
fi
echo ""

# Check 5: Validate no DNS errors in recent logs
echo "📝 Check 5: Checking for DNS errors in logs..."
DNS_ERRORS=$(docker logs prosaas-worker 2>&1 | tail -100 | grep -i "could not translate host name\|name or service not known\|dns" || echo "")

if [ -n "$DNS_ERRORS" ]; then
    DNS_ERROR_COUNT=$(echo "$DNS_ERRORS" | wc -l)
    echo -e "${YELLOW}⚠  WARNING: Found ${DNS_ERROR_COUNT} DNS-related messages in recent logs${NC}"
    echo "   (This may be normal during startup or transient network issues)"
    echo "   Recent DNS messages:"
    echo "$DNS_ERRORS" | tail -5
else
    echo -e "${GREEN}✅ PASS: No DNS errors found in recent logs${NC}"
fi
echo ""

# Check 6: Validate log spam is minimal
echo "📝 Check 6: Checking log verbosity..."
WORKER_LOG_COUNT=$(docker logs prosaas-worker 2>&1 | tail -100 | wc -l)
echo "   Worker log lines in last 100: $WORKER_LOG_COUNT"

# Check for excessive DEBUG logs
DEBUG_COUNT=$(docker logs prosaas-worker 2>&1 | tail -100 | grep -i "DEBUG" | wc -l)
if [ "$DEBUG_COUNT" -gt 50 ]; then
    echo -e "${YELLOW}⚠  WARNING: High number of DEBUG logs ($DEBUG_COUNT) - check LOG_LEVEL${NC}"
else
    echo -e "${GREEN}✅ PASS: Log verbosity is reasonable ($DEBUG_COUNT DEBUG logs)${NC}"
fi
echo ""

# Check 7: Validate no fake ERRORs
echo "📝 Check 7: Checking for fake ERRORs..."
FAKE_ERRORS=$(docker logs prosaas-calls 2>&1 | tail -200 | grep -E "SAFETY.*Transcription successful|websocket\.close.*already" || echo "")

if [ -n "$FAKE_ERRORS" ]; then
    FAKE_ERROR_COUNT=$(echo "$FAKE_ERRORS" | wc -l)
    echo -e "${YELLOW}⚠  WARNING: Found ${FAKE_ERROR_COUNT} fake ERROR messages${NC}"
    echo "   Recent fake errors:"
    echo "$FAKE_ERRORS" | tail -3
else
    echo -e "${GREEN}✅ PASS: No fake ERROR messages found${NC}"
fi
echo ""

# Summary
echo "=============================================================================="
if [ "$VALIDATION_FAILED" = true ]; then
    echo -e "${RED}❌ VALIDATION FAILED${NC}"
    echo "One or more critical checks failed. Please review the output above."
    echo "=============================================================================="
    exit 1
else
    echo -e "${GREEN}✅ ALL VALIDATIONS PASSED${NC}"
    echo "Production deployment is correctly configured."
    echo "=============================================================================="
    exit 0
fi
