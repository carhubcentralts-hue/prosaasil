#!/bin/bash
# ===========================================
# Deployment Verification Script
# Verifies all critical API endpoints are accessible
# ===========================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default to production URL
BASE_URL="${1:-https://prosaas.pro}"
BACKEND_URL="${2:-http://127.0.0.1:5000}"

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}ProSaaS Deployment Verification${NC}"
echo -e "${BLUE}Testing: ${BASE_URL}${NC}"
echo -e "${BLUE}Backend (direct): ${BACKEND_URL}${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Function to test endpoint
test_endpoint() {
    local url="$1"
    local name="$2"
    local expected_codes="$3"
    
    # Make request and capture status code
    status=$(curl -s -o /dev/null -w "%{http_code}" -L "$url" 2>/dev/null || echo "000")
    
    # Check if status is in expected codes (supports 200, 401, 403)
    if echo "$expected_codes" | grep -q "$status"; then
        echo -e "${GREEN}✓${NC} $name: $status"
        return 0
    elif [ "$status" = "404" ]; then
        echo -e "${RED}✗${NC} $name: 404 NOT FOUND"
        return 1
    elif [ "$status" = "000" ]; then
        echo -e "${RED}✗${NC} $name: CONNECTION FAILED"
        return 1
    else
        echo -e "${YELLOW}⚠${NC} $name: Unexpected $status"
        return 1
    fi
}

# Track failures
FAILED=0
TOTAL=0

echo -e "${BLUE}Testing Public Endpoints (via Nginx)${NC}"
echo "───────────────────────────────────────────────────────────"

# Test public endpoints
endpoints=(
    "/health:Health Check:200"
    "/api/health:API Health:200"
    "/api/dashboard/stats?time_filter=today:Dashboard Stats:200,401,403"
    "/api/dashboard/activity?time_filter=today:Dashboard Activity:200,401,403"
    "/api/business/current:Business Current:200,401,403"
    "/api/notifications:Notifications:200,401,403"
    "/api/admin/businesses?pageSize=1:Admin Businesses:200,401,403"
    "/api/search?q=test:Global Search:200,401,403"
    "/api/whatsapp/status:WhatsApp Status:200,401,403"
    "/api/whatsapp/templates:WhatsApp Templates:200,401,403"
    "/api/whatsapp/broadcasts:WhatsApp Broadcasts:200,401,403"
    "/api/crm/threads:CRM Threads:200,401,403"
    "/api/statuses:Statuses:200,401,403"
    "/api/leads?page=1&pageSize=1:Leads List:200,401,403"
)

for endpoint_def in "${endpoints[@]}"; do
    IFS=':' read -r path name expected_codes <<< "$endpoint_def"
    TOTAL=$((TOTAL + 1))
    if ! test_endpoint "${BASE_URL}${path}" "$name" "$expected_codes"; then
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo -e "${BLUE}Testing Backend Directly (bypass Nginx)${NC}"
echo "───────────────────────────────────────────────────────────"

# Test backend directly
backend_endpoints=(
    "/api/health:API Health (direct):200"
    "/api/dashboard/stats?time_filter=today:Dashboard Stats (direct):200,401,403"
)

for endpoint_def in "${backend_endpoints[@]}"; do
    IFS=':' read -r path name expected_codes <<< "$endpoint_def"
    TOTAL=$((TOTAL + 1))
    if ! test_endpoint "${BACKEND_URL}${path}" "$name" "$expected_codes"; then
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo -e "${BLUE}Testing Debug Endpoints${NC}"
echo "───────────────────────────────────────────────────────────"

# Test debug endpoint to list routes
debug_url="${BASE_URL}/api/debug/routes"
echo -n "Fetching registered routes... "
routes_json=$(curl -s "$debug_url" 2>/dev/null || echo "{}")
route_count=$(echo "$routes_json" | grep -o '"api_routes_count":[0-9]*' | grep -o '[0-9]*' || echo "0")

if [ "$route_count" -gt 0 ]; then
    echo -e "${GREEN}✓ Found $route_count API routes${NC}"
    # List critical routes
    echo "Critical routes registered:"
    echo "$routes_json" | grep -o '"/api/[^"]*"' | sort | uniq | head -20
else
    echo -e "${RED}✗ No API routes found or endpoint not accessible${NC}"
    FAILED=$((FAILED + 1))
    TOTAL=$((TOTAL + 1))
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Results: $((TOTAL - FAILED))/$TOTAL tests passed${NC}"

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Failed: $FAILED endpoints${NC}"
    echo -e "${RED}❌ DEPLOYMENT VERIFICATION FAILED${NC}"
    echo ""
    echo -e "${YELLOW}Troubleshooting steps:${NC}"
    echo "1. Check if backend is running: docker ps | grep backend"
    echo "2. Check backend logs: docker logs prosaas-backend"
    echo "3. Check nginx logs: docker logs prosaas-frontend"
    echo "4. Test backend directly: curl http://127.0.0.1:5000/api/health"
    echo "5. Verify nginx config: docker exec prosaas-frontend cat /etc/nginx/conf.d/default.conf"
    echo "6. Check route registration: curl ${BASE_URL}/api/debug/routes | jq '.api_routes_count'"
    echo ""
    exit 1
else
    echo -e "${GREEN}✅ ALL TESTS PASSED - DEPLOYMENT VERIFIED${NC}"
fi

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

exit 0
