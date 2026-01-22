#!/usr/bin/env bash
# ===========================================
# Production Verification Script - Enhanced
# Verifies DB connectivity, env vars, and n8n proxy
# Based on feedback to ensure proper deployment
# ===========================================

set -euo pipefail

cd "$(dirname "$0")/.."

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║            Production Verification - DB, ENV, and n8n Checks                 ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAILURES=0

# Check 1: DATABASE_URL is set in prosaas-api
echo "=== Check 1: DATABASE_URL Environment Variable ==="
echo "Checking if DATABASE_URL is set in prosaas-api container..."
if docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T prosaas-api env | grep -q "DATABASE_URL="; then
    echo -e "${GREEN}✅ PASS: DATABASE_URL is set in prosaas-api${NC}"
    # Show only driver without exposing credentials
    DB_URL=$(docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T prosaas-api env | grep "^DATABASE_URL=" | cut -d'=' -f2 || echo "")
    if [ -n "$DB_URL" ]; then
        DB_DRIVER=$(echo "$DB_URL" | cut -d':' -f1)
        echo "   Database driver: $DB_DRIVER"
    fi
else
    echo -e "${RED}❌ FAIL: DATABASE_URL is NOT set in prosaas-api${NC}"
    echo "   This will cause login failures!"
    FAILURES=$((FAILURES + 1))
fi
echo ""

# Check 2: DATABASE_URL is set in prosaas-calls
echo "=== Check 2: DATABASE_URL in prosaas-calls ==="
echo "Checking if DATABASE_URL is set in prosaas-calls container..."
if docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T prosaas-calls env | grep -q "DATABASE_URL="; then
    echo -e "${GREEN}✅ PASS: DATABASE_URL is set in prosaas-calls${NC}"
else
    echo -e "${RED}❌ FAIL: DATABASE_URL is NOT set in prosaas-calls${NC}"
    echo "   This will cause WebSocket call failures!"
    FAILURES=$((FAILURES + 1))
fi
echo ""

# Check 3: Database connectivity from prosaas-api
echo "=== Check 3: Database Connectivity Test ==="
echo "Testing actual database connection from prosaas-api..."
if docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T prosaas-api python3 -c "
from server.db import db
from sqlalchemy import text
try:
    db.session.execute(text('SELECT 1'))
    print('✅ Database connection successful')
    exit(0)
except Exception as e:
    # Sanitize error message to avoid exposing credentials
    error_msg = str(e)[:100]
    print(f'❌ Database connection failed: {error_msg}')
    exit(1)
" 2>&1; then
    echo -e "${GREEN}✅ PASS: Database is reachable and query works${NC}"
else
    echo -e "${RED}❌ FAIL: Database connection test failed${NC}"
    echo "   Check DATABASE_URL and database availability"
    FAILURES=$((FAILURES + 1))
fi
echo ""

# Check 4: Migrations completion
echo "=== Check 4: Migrations Status ==="
echo "Checking if migrations completed successfully..."
if docker logs prosaasil-prosaas-api-1 2>&1 | grep -q "Migrations complete - warmup can now proceed"; then
    echo -e "${GREEN}✅ PASS: Migrations completed successfully${NC}"
elif docker logs prosaasil-prosaas-api-1 2>&1 | grep -q "MIGRATION FAILED"; then
    echo -e "${RED}❌ FAIL: Migrations failed!${NC}"
    echo "   Check logs: docker logs prosaasil-prosaas-api-1 | grep MIGRATION"
    FAILURES=$((FAILURES + 1))
else
    echo -e "${YELLOW}⚠️  WARNING: Migration completion status unclear${NC}"
    echo "   Migrations may still be running"
fi
echo ""

# Check 5: API health endpoint (with retry loop)
echo "=== Check 5: API Health Endpoint (Wait for Ready) ==="
echo "Waiting for /api/health to return 200 OK..."

MAX_WAIT=120  # Wait up to 2 minutes
ELAPSED=0
HEALTH_OK=false

while [ $ELAPSED -lt $MAX_WAIT ]; do
    HEALTH_RESPONSE=$(curl -s http://localhost/api/health 2>&1 || echo "failed")
    
    if echo "$HEALTH_RESPONSE" | grep -q '"status":"ok"'; then
        echo -e "${GREEN}✅ PASS: API health endpoint returns OK (after ${ELAPSED}s)${NC}"
        HEALTH_OK=true
        break
    elif echo "$HEALTH_RESPONSE" | grep -q '"status":"initializing"'; then
        echo -n "⏳ Waiting for migrations to complete... (${ELAPSED}s/${MAX_WAIT}s)\r"
    elif echo "$HEALTH_RESPONSE" | grep -q '"status":"unhealthy"'; then
        echo -e "\n${RED}❌ FAIL: API reports unhealthy status${NC}"
        echo "   Response: $HEALTH_RESPONSE"
        FAILURES=$((FAILURES + 1))
        break
    else
        echo -n "⏳ Waiting for API to respond... (${ELAPSED}s/${MAX_WAIT}s)\r"
    fi
    
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done

if [ "$HEALTH_OK" = false ]; then
    if [ $ELAPSED -ge $MAX_WAIT ]; then
        echo -e "\n${RED}❌ FAIL: API health endpoint did not become healthy within ${MAX_WAIT}s${NC}"
        echo "   Last response: $HEALTH_RESPONSE"
        FAILURES=$((FAILURES + 1))
    fi
fi
echo ""

# Check 6: n8n container is running and responding
echo "=== Check 6: n8n Service Status ==="
if docker ps --format '{{.Names}}' | grep -q "prosaasil-n8n"; then
    echo -e "${GREEN}✅ n8n container is running${NC}"
    
    # Test direct connection to n8n
    echo "Testing direct connection to n8n:5678..."
    if docker exec prosaasil-n8n-1 curl -s -o /dev/null -w "%{http_code}" http://localhost:5678 2>&1 | grep -q "200"; then
        echo -e "${GREEN}✅ PASS: n8n is responding on port 5678${NC}"
    else
        echo -e "${RED}❌ FAIL: n8n is not responding on port 5678${NC}"
        FAILURES=$((FAILURES + 1))
    fi
else
    echo -e "${RED}❌ FAIL: n8n container is not running${NC}"
    FAILURES=$((FAILURES + 1))
fi
echo ""

# Check 7: nginx can reach n8n
echo "=== Check 7: Nginx → n8n Proxy Test ==="
echo "Testing nginx proxy to n8n..."
if docker exec prosaasil-nginx-1 curl -s -o /dev/null -w "%{http_code}" http://n8n:5678 2>&1 | grep -q "200"; then
    echo -e "${GREEN}✅ PASS: Nginx can reach n8n backend${NC}"
else
    echo -e "${RED}❌ FAIL: Nginx cannot reach n8n backend${NC}"
    echo "   Check docker network configuration"
    FAILURES=$((FAILURES + 1))
fi
echo ""

# Check 8: n8n environment variables
echo "=== Check 8: n8n Environment Configuration ==="
echo "Checking n8n environment variables..."

N8N_PATH=$(docker exec prosaasil-n8n-1 env | grep "^N8N_PATH=" | cut -d'=' -f2 || echo "NOT_SET")
N8N_EDITOR_BASE_URL=$(docker exec prosaasil-n8n-1 env | grep "^N8N_EDITOR_BASE_URL=" | cut -d'=' -f2 || echo "NOT_SET")

if [ "$N8N_PATH" = "/" ]; then
    echo -e "${GREEN}✅ N8N_PATH is correctly set to /${NC}"
else
    echo -e "${YELLOW}⚠️  N8N_PATH is: $N8N_PATH (expected: /)${NC}"
fi

if echo "$N8N_EDITOR_BASE_URL" | grep -q "n8n.prosaas.pro"; then
    echo -e "${GREEN}✅ N8N_EDITOR_BASE_URL is correctly set${NC}"
else
    echo -e "${YELLOW}⚠️  N8N_EDITOR_BASE_URL is: $N8N_EDITOR_BASE_URL${NC}"
fi
echo ""

# Check 9: Agent warmup status
echo "=== Check 9: Agent Warmup Status ==="
echo "Checking agent warmup logs..."
if docker logs prosaasil-prosaas-api-1 2>&1 | grep -q "Agent warmup waiting for migrations"; then
    if docker logs prosaasil-prosaas-api-1 2>&1 | grep -q "Migrations complete - starting agent warmup"; then
        echo -e "${GREEN}✅ PASS: Agent warmup completed successfully${NC}"
    elif docker logs prosaasil-prosaas-api-1 2>&1 | grep -q "Skipping agent warmup in production due to timeout"; then
        echo -e "${YELLOW}⚠️  WARNING: Agent warmup timed out (non-blocking)${NC}"
        echo "   First requests may be slower, but app is running"
    else
        echo -e "${YELLOW}⚠️  Agent warmup status unclear${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Agent warmup not detected in logs${NC}"
fi
echo ""

# Summary
echo "═══════════════════════════════════════════════════════════════"
if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}✅ All critical checks PASSED${NC}"
    echo "   Deployment is healthy and ready for production use"
    exit 0
else
    echo -e "${RED}❌ $FAILURES check(s) FAILED${NC}"
    echo "   Review the failures above and fix before using in production"
    exit 1
fi
