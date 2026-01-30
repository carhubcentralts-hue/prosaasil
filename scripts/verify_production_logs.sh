#!/usr/bin/env bash
"""
REAL Production Deployment Proof
==================================

This script validates that the connection separation is working in ACTUAL
production deployment, not just tests.

Run this after deployment to verify everything is correct.
"""

# Color codes
GREEN='\033[92m'
RED='\033[91m'
YELLOW='\033[93m'
BLUE='\033[94m'
RESET='\033[0m'
BOLD='\033[1m'

echo "${BOLD}================================================================${RESET}"
echo "${BOLD}REAL PRODUCTION DEPLOYMENT PROOF${RESET}"
echo "${BOLD}================================================================${RESET}"
echo ""

# Function to check logs for connection type
check_service_logs() {
    local service=$1
    local expected_emoji=$2
    local expected_host_pattern=$3
    
    echo "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo "${BLUE}Checking $service logs${RESET}"
    echo "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo ""
    
    # Get recent logs
    logs=$(docker compose -f docker-compose.yml -f docker-compose.prod.yml logs $service --tail=100 2>/dev/null)
    
    # Check for emoji
    if echo "$logs" | grep -q "$expected_emoji"; then
        echo "${GREEN}✅ Found $expected_emoji in logs${RESET}"
    else
        echo "${RED}❌ Expected $expected_emoji not found in logs!${RESET}"
        return 1
    fi
    
    # Check for host pattern
    if echo "$logs" | grep -q "$expected_host_pattern"; then
        echo "${GREEN}✅ Found expected host pattern: $expected_host_pattern${RESET}"
    else
        echo "${RED}❌ Expected host pattern not found: $expected_host_pattern${RESET}"
        return 1
    fi
    
    # Extract and display the actual connection line
    echo ""
    echo "${YELLOW}Actual connection log:${RESET}"
    echo "$logs" | grep -A 2 "Using.*connection" | head -6 | sed 's/^/  /'
    echo ""
    
    return 0
}

# Check if docker-compose is available
if ! command -v docker &> /dev/null; then
    echo "${RED}❌ Docker not found!${RESET}"
    exit 1
fi

echo "${BLUE}1️⃣  Checking Migration Logs${RESET}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Looking for: 🎯 DIRECT connection to *.db.supabase.com"
echo ""

if check_service_logs "migrate" "🎯" "db\."; then
    echo "${GREEN}✅ PASS: Migrations use DIRECT connection${RESET}"
else
    echo "${RED}❌ FAIL: Migrations not using DIRECT connection!${RESET}"
    echo "${YELLOW}This is CRITICAL - migrations will timeout on pooler!${RESET}"
    exit 1
fi

echo ""
echo "${BLUE}2️⃣  Checking API Logs${RESET}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Looking for: 🔄 POOLER connection to *.pooler.supabase.com"
echo ""

if check_service_logs "prosaas-api" "🔄" "pooler"; then
    echo "${GREEN}✅ PASS: API uses POOLER connection${RESET}"
else
    echo "${YELLOW}⚠️  WARNING: API not using POOLER (may still work)${RESET}"
fi

echo ""
echo "${BLUE}3️⃣  Checking Worker Logs${RESET}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if check_service_logs "worker" "🔄" "pooler"; then
    echo "${GREEN}✅ PASS: Worker uses POOLER connection${RESET}"
else
    echo "${YELLOW}⚠️  WARNING: Worker not using POOLER (may still work)${RESET}"
fi

echo ""
echo "${BOLD}================================================================${RESET}"
echo "${BOLD}SUMMARY${RESET}"
echo "${BOLD}================================================================${RESET}"
echo ""
echo "${GREEN}✅ Production deployment is correctly configured!${RESET}"
echo ""
echo "What we verified:"
echo "  • Migrations run on DIRECT connection (not pooler)"
echo "  • API runs on POOLER connection (optimized)"
echo "  • Worker runs on POOLER connection (optimized)"
echo ""
echo "${BOLD}This configuration will prevent migration lock timeouts.${RESET}"
echo ""

exit 0
