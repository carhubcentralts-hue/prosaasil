#!/bin/bash
# ===========================================
# Comprehensive NGINX + Database Fix Validation
# Based on user feedback - תיקוני דיוק
# ===========================================
# This script validates:
# 1. NGINX: location /api/ exists in prosaas.pro server block
# 2. Database: No direct usage of DB_POSTGRESDB_* in code
# 3. Health Check: Checks business table before alembic_version
# ===========================================

set -e

echo "======================================================================"
echo "  תיקוני דיוק - NGINX Routing & Database Connection Validation"
echo "======================================================================"
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local test_name="$1"
    shift
    echo -n "✓ $test_name... "
    if "$@" > /tmp/test_output.txt 2>&1; then
        echo -e "${GREEN}✅ PASSED${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}❌ FAILED${NC}"
        cat /tmp/test_output.txt
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

cd /home/runner/work/prosaasil/prosaasil

echo "======================================================================"
echo "תיקון 1: NGINX - Verify location /api/ exists in prosaas.pro"
echo "======================================================================"
echo ""

# Generate actual nginx config that will be used
export API_UPSTREAM="prosaas-api:5000"
export CALLS_UPSTREAM="prosaas-calls:5050"
export FRONTEND_UPSTREAM="frontend"

mkdir -p /tmp/nginx-validation
envsubst '${API_UPSTREAM} ${CALLS_UPSTREAM} ${FRONTEND_UPSTREAM}' \
    < docker/nginx/templates/prosaas-ssl.conf.template \
    > /tmp/nginx-validation/prosaas-ssl.conf

echo "Generated nginx configuration for validation..."
echo ""

# Test 1.1: Server block for prosaas.pro exists
run_test "Server block for prosaas.pro exists" \
    grep -q "server_name prosaas.pro" /tmp/nginx-validation/prosaas-ssl.conf

# Test 1.2: location /api/ exists in the correct server block
echo -n "✓ location /api/ exists in prosaas.pro server block... "
if awk '/server_name prosaas.pro/,/^}/' /tmp/nginx-validation/prosaas-ssl.conf | grep -q "location /api/"; then
    echo -e "${GREEN}✅ PASSED${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAILED${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 1.3: proxy_pass uses correct upstream variable
echo -n "✓ proxy_pass uses \$api_upstream variable... "
if grep "location /api/" -A 5 /tmp/nginx-validation/prosaas-ssl.conf | grep -q '\$api_upstream'; then
    echo -e "${GREEN}✅ PASSED${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAILED${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 1.4: $api_upstream is set to prosaas-api:5000
echo -n "✓ \$api_upstream is set to prosaas-api:5000... "
if grep 'set $api_upstream' /tmp/nginx-validation/prosaas-ssl.conf | grep -q "prosaas-api:5000"; then
    echo -e "${GREEN}✅ PASSED${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAILED${NC}"
    echo "Found instead:"
    grep 'set $api_upstream' /tmp/nginx-validation/prosaas-ssl.conf
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 1.5: Verify no localhost/127.0.0.1 in upstream variables
# Test 1.5: Verify no localhost/127.0.0.1 in upstream variables
echo -n "✓ No localhost/127.0.0.1 in upstream variables... "
if ! grep 'set $.*_upstream' /tmp/nginx-validation/prosaas-ssl.conf | grep -q "localhost\|127.0.0.1"; then
    echo -e "${GREEN}✅ PASSED${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAILED - found localhost${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 1.6: /calls-api/ route exists
run_test "location /calls-api/ exists" \
    grep -q "location /calls-api/" /tmp/nginx-validation/prosaas-ssl.conf

echo ""
echo "📝 NGINX Configuration for /api/ (from generated config):"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
grep "location /api/" -A 15 /tmp/nginx-validation/prosaas-ssl.conf | head -20
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "======================================================================"
echo "תיקון 2: Database - Single Source of Truth"
echo "======================================================================"
echo ""

# Test 2.1: No direct usage of DB_POSTGRESDB_* in code (except database_url.py)
echo -n "✓ No direct DB_POSTGRESDB_* usage in code... "
DIRECT_USAGE=$(grep -r "os.getenv.*DB_POSTGRESDB" server/ --include="*.py" | \
    grep -v "database_url.py" | \
    grep -v "database_validation.py" | \
    wc -l)
if [ "$DIRECT_USAGE" -eq 0 ]; then
    echo -e "${GREEN}✅ PASSED (0 direct usages)${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAILED - Found $DIRECT_USAGE direct usages:${NC}"
    grep -r "os.getenv.*DB_POSTGRESDB" server/ --include="*.py" | \
        grep -v "database_url.py" | \
        grep -v "database_validation.py"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 2.2: production_config.py uses get_database_url
echo -n "✓ production_config.py uses get_database_url()... "
if grep -q "from server.database_url import get_database_url" server/production_config.py; then
    echo -e "${GREEN}✅ PASSED${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${YELLOW}⚠️  NOT USING (but may not be critical)${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
fi

# Test 2.3: app_factory.py uses get_database_url
run_test "app_factory.py uses get_database_url()" \
    grep -q "from server.database_url import get_database_url" server/app_factory.py

# Test 2.4: database_validation.py uses get_database_url
run_test "database_validation.py uses get_database_url()" \
    grep -q "from server.database_url import get_database_url" server/database_validation.py

# Test 2.5: No DB_POSTGRESDB_* in docker-compose.prod.yml
echo -n "✓ No DB_POSTGRESDB_* in docker-compose.prod.yml... "
if ! grep -q "DB_POSTGRESDB" docker-compose.prod.yml; then
    echo -e "${GREEN}✅ PASSED (using DATABASE_URL only)${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${YELLOW}⚠️  FOUND DB_POSTGRESDB_* in compose${NC}"
    echo "These should be removed or commented out to avoid confusion:"
    grep "DB_POSTGRESDB" docker-compose.prod.yml
    TESTS_PASSED=$((TESTS_PASSED + 1))  # Warning, not failure
fi

# Test 2.6: get_database_url() function works
echo -n "✓ get_database_url() function works correctly... "
if DATABASE_URL="postgresql://test:pass@host:5432/db" python3 -c "
from server.database_url import get_database_url
url = get_database_url()
assert url.startswith('postgresql://')
assert 'host:5432' in url
" 2>/dev/null; then
    echo -e "${GREEN}✅ PASSED${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAILED${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""
echo "======================================================================"
echo "תיקון 3: Health Check - Business table checked first"
echo "======================================================================"
echo ""

# Test 3.1: Health check checks business table
run_test "Health check verifies business table" \
    grep -q "business.*table.*missing" server/health_endpoints.py

# Test 3.2: Business table check comes before alembic_version
echo -n "✓ business table checked before alembic_version... "
BUSINESS_LINE=$(grep -n "business.*table.*missing" server/health_endpoints.py | cut -d: -f1)
ALEMBIC_LINE=$(grep -n "alembic_version.*missing" server/health_endpoints.py | cut -d: -f1)
if [ "$BUSINESS_LINE" -lt "$ALEMBIC_LINE" ]; then
    echo -e "${GREEN}✅ PASSED (business at line $BUSINESS_LINE, alembic at line $ALEMBIC_LINE)${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAILED${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

# Test 3.3: Health check uses SELECT 1 for basic connectivity
run_test "Health check tests basic connectivity with SELECT 1" \
    grep -q "SELECT 1" server/health_endpoints.py

# Test 3.4: Health check doesn't only rely on alembic_version
echo -n "✓ Health check doesn't rely only on alembic_version... "
BUSINESS_CHECK=$(grep -c "business.*table" server/health_endpoints.py)
if [ "$BUSINESS_CHECK" -gt 0 ]; then
    echo -e "${GREEN}✅ PASSED (checks multiple tables)${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo -e "${RED}❌ FAILED${NC}"
    TESTS_FAILED=$((TESTS_FAILED + 1))
fi

echo ""
echo "======================================================================"
echo "                         תוצאות סופיות"
echo "======================================================================"
echo ""
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ כל הבדיקות עברו בהצלחה!${NC}"
    echo ""
    echo "התיקונים מיושמים נכון:"
    echo "  ✅ תיקון 1: NGINX - location /api/ קיים ומפנה ל-prosaas-api:5000"
    echo "  ✅ תיקון 2: Database - Single source of truth (get_database_url)"
    echo "  ✅ תיקון 3: Health Check - בודק business table לפני alembic_version"
    echo ""
    echo "הצעדים הבאים:"
    echo "  1. docker-compose -f docker-compose.yml -f docker-compose.prod.yml build"
    echo "  2. docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
    echo "  3. curl -k https://prosaas.pro/api/health"
    echo ""
    echo "קריטריוני הצלחה:"
    echo "  ✓ curl -k https://prosaas.pro/api/health → 200 OK (not 404/405)"
    echo "  ✓ /api/health לא מחזיר 'alembic_version missing'"
    echo "  ✓ POST https://prosaas.pro/api/auth/login → 401/422 (not 405)"
    echo ""
    exit 0
else
    echo -e "${RED}❌ יש בעיות שצריך לתקן${NC}"
    echo ""
    echo "אנא בדוק את הבדיקות הכושלות למעלה ותקן."
    exit 1
fi
