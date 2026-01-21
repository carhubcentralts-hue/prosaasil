#!/bin/bash
# ===========================================
# FORCE REBUILD - Nuclear Option
# ===========================================
# Use this when normal deployment fails
# This forces a complete rebuild with no cache
# ===========================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${RED}===========================================
⚠️  FORCE REBUILD (NO CACHE) ⚠️
===========================================${NC}"
echo -e "${YELLOW}This will rebuild ALL images from scratch${NC}"
echo -e "${YELLOW}This may take 10-15 minutes${NC}"
echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo -e "\n${BLUE}Step 1: Stopping all services...${NC}"
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

echo -e "\n${BLUE}Step 2: Removing old images...${NC}"
docker images | grep prosaas | awk '{print $3}' | xargs -r docker rmi -f || true

echo -e "\n${BLUE}Step 3: Building NGINX (no cache, forced)...${NC}"
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache --pull nginx

echo -e "\n${BLUE}Step 4: Building other services (no cache)...${NC}"
docker compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache --pull \
    prosaas-api \
    prosaas-calls \
    worker \
    frontend \
    baileys

echo -e "\n${BLUE}Step 5: Starting all services...${NC}"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

echo -e "\n${BLUE}Step 6: Waiting for services to start...${NC}"
sleep 10

echo -e "\n${BLUE}Step 7: Checking status...${NC}"
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

echo -e "\n${BLUE}Step 8: Verifying NGINX config...${NC}"
echo "Checking proxy_pass directives:"
docker exec prosaas-nginx nginx -T 2>/dev/null | grep "proxy_pass" | grep -E "(prosaas-api|prosaas-calls)" || {
    echo -e "${RED}✗ NGINX config still wrong!${NC}"
    echo "Showing all proxy_pass lines:"
    docker exec prosaas-nginx nginx -T 2>/dev/null | grep "proxy_pass"
    exit 1
}

echo -e "\n${BLUE}Step 9: Checking for errors...${NC}"
docker logs prosaas-nginx --tail 30 2>&1 | grep -i "error" || echo -e "${GREEN}✓ No errors in nginx logs${NC}"

echo -e "\n${GREEN}===========================================
Force rebuild complete!
===========================================${NC}"

echo -e "\n${BLUE}Services status:${NC}"
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

echo -e "\n${BLUE}Test commands:${NC}"
echo "curl http://localhost/health"
echo "docker logs prosaas-nginx -f"
echo "docker logs prosaas-api -f"
