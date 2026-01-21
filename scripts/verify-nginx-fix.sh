#!/bin/bash
# ===========================================
# Quick Verification Script for NGINX Fix
# ===========================================
# This script verifies that all fixes are working correctly
# Run after deployment to ensure everything is functioning

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}===========================================
NGINX Upstream Fix Verification
===========================================${NC}"

ERRORS=0

# Test 1: Check service names in config
echo -e "\n${BLUE}Test 1: Verifying docker-compose configuration...${NC}"
if docker compose -f docker-compose.yml -f docker-compose.prod.yml config --services 2>&1 | grep -q "backend"; then
    echo -e "${GREEN}✓ Backend service defined${NC}"
else
    echo -e "${RED}✗ Backend service NOT found${NC}"
    ERRORS=$((ERRORS + 1))
fi

if docker compose -f docker-compose.yml -f docker-compose.prod.yml config --services 2>&1 | grep -q "worker"; then
    echo -e "${GREEN}✓ Worker service defined${NC}"
else
    echo -e "${RED}✗ Worker service NOT found${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Test 2: Check NGINX build args
echo -e "\n${BLUE}Test 2: Verifying NGINX build configuration...${NC}"
CONFIG_OUTPUT=$(docker compose -f docker-compose.yml -f docker-compose.prod.yml config 2>/dev/null || echo "")

if echo "$CONFIG_OUTPUT" | grep -q "API_UPSTREAM: backend:5000"; then
    echo -e "${GREEN}✓ API_UPSTREAM points to backend:5000${NC}"
else
    echo -e "${RED}✗ API_UPSTREAM not set correctly${NC}"
    ERRORS=$((ERRORS + 1))
fi

if echo "$CONFIG_OUTPUT" | grep -q "CALLS_UPSTREAM: backend:5000"; then
    echo -e "${GREEN}✓ CALLS_UPSTREAM points to backend:5000${NC}"
else
    echo -e "${RED}✗ CALLS_UPSTREAM not set correctly${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Test 3: Check NGINX dependencies
echo -e "\n${BLUE}Test 3: Verifying NGINX depends_on...${NC}"
if echo "$CONFIG_OUTPUT" | grep -A 20 "nginx:" | grep -q "backend:"; then
    echo -e "${GREEN}✓ NGINX depends on backend${NC}"
else
    echo -e "${RED}✗ NGINX does not depend on backend${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Test 4: Check if containers are running (if deployed)
echo -e "\n${BLUE}Test 4: Checking running containers (if deployed)...${NC}"
if docker compose -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null | grep -q "prosaas-nginx"; then
    if docker compose -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null | grep "prosaas-nginx" | grep -q "Up"; then
        echo -e "${GREEN}✓ NGINX container is running${NC}"
        
        # Check for errors in logs
        NGINX_ERRORS=$(docker logs prosaas-nginx 2>&1 | grep -i "host not found in upstream" || true)
        if [ -z "$NGINX_ERRORS" ]; then
            echo -e "${GREEN}✓ No 'host not found' errors in NGINX logs${NC}"
        else
            echo -e "${RED}✗ Found 'host not found' errors in NGINX logs:${NC}"
            echo "$NGINX_ERRORS"
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo -e "${RED}✗ NGINX container is not running${NC}"
        ERRORS=$((ERRORS + 1))
    fi
    
    if docker compose -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null | grep "prosaas-backend" | grep -q "Up"; then
        echo -e "${GREEN}✓ Backend container is running${NC}"
    else
        echo -e "${RED}✗ Backend container is not running${NC}"
        ERRORS=$((ERRORS + 1))
    fi
    
    if docker compose -f docker-compose.yml -f docker-compose.prod.yml ps 2>/dev/null | grep "prosaas-worker" | grep -q "Up"; then
        echo -e "${GREEN}✓ Worker container is running${NC}"
    else
        echo -e "${RED}✗ Worker container is not running${NC}"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${YELLOW}⚠ Containers not deployed yet (this is OK if you haven't deployed)${NC}"
fi

# Test 5: Check worker queues configuration
echo -e "\n${BLUE}Test 5: Verifying worker queue configuration...${NC}"
if echo "$CONFIG_OUTPUT" | grep -A 20 "worker:" | grep -q "RQ_QUEUES: high,default,low,receipts,receipts_sync"; then
    echo -e "${GREEN}✓ Worker configured with all required queues${NC}"
else
    echo -e "${RED}✗ Worker queue configuration incorrect${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Test 6: Check DNS configuration
echo -e "\n${BLUE}Test 6: Verifying DNS configuration...${NC}"
if echo "$CONFIG_OUTPUT" | grep -A 30 "backend:" | grep -q "1.1.1.1"; then
    echo -e "${GREEN}✓ Backend has external DNS configured${NC}"
else
    echo -e "${RED}✗ Backend DNS not configured${NC}"
    ERRORS=$((ERRORS + 1))
fi

if echo "$CONFIG_OUTPUT" | grep -A 30 "worker:" | grep -q "1.1.1.1"; then
    echo -e "${GREEN}✓ Worker has external DNS configured${NC}"
else
    echo -e "${RED}✗ Worker DNS not configured${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Test 7: Check deployment script exists
echo -e "\n${BLUE}Test 7: Checking deployment script...${NC}"
if [ -x "scripts/deploy-prod.sh" ]; then
    echo -e "${GREEN}✓ Deployment script exists and is executable${NC}"
else
    echo -e "${RED}✗ Deployment script missing or not executable${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Summary
echo -e "\n${BLUE}===========================================
Verification Summary
===========================================${NC}"

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed! Configuration is correct.${NC}"
    echo -e "\n${BLUE}Next steps:${NC}"
    echo "1. Deploy: ./scripts/deploy-prod.sh"
    echo "2. Check health: curl http://localhost/health"
    echo "3. Monitor logs: docker logs prosaas-nginx -f"
    exit 0
else
    echo -e "${RED}✗ $ERRORS test(s) failed. Please review the errors above.${NC}"
    exit 1
fi
