#!/bin/bash
# ===========================================
# ProSaaS Production Deployment Script
# ===========================================
# This script automates production deployment:
# 1. Pulls latest code changes
# 2. Rebuilds Docker images with latest changes
# 3. Recreates containers to pick up new config
# 4. Cleans up old images
#
# Usage:
#   ./scripts/deploy-prod.sh
#
# Requirements:
#   - Docker and Docker Compose installed
#   - .env file with production configuration
#   - SSL certificates in docker/nginx/ssl/ (if USE_SSL=true)
# ===========================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===========================================
ProSaaS Production Deployment
===========================================${NC}"

# Step 1: Check prerequisites
echo -e "\n${BLUE}Step 1: Checking prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    exit 1
fi

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found. Using environment variables only.${NC}"
fi

echo -e "${GREEN}✓ Prerequisites OK${NC}"

# Step 2: Pull latest changes (optional, comment out if deploying from local changes)
echo -e "\n${BLUE}Step 2: Pulling latest code...${NC}"
if [ -d ".git" ]; then
    git fetch origin
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    echo -e "Current branch: ${YELLOW}${CURRENT_BRANCH}${NC}"
    
    # Only pull if on a tracking branch
    if git rev-parse --abbrev-ref --symbolic-full-name @{u} &> /dev/null; then
        git pull
        echo -e "${GREEN}✓ Code updated${NC}"
    else
        echo -e "${YELLOW}Branch not tracking remote, skipping pull${NC}"
    fi
else
    echo -e "${YELLOW}Not a git repository, skipping git pull${NC}"
fi

# Step 3: Build images with latest changes
echo -e "\n${BLUE}Step 3: Building Docker images...${NC}"
echo -e "This may take several minutes..."
echo -e "${YELLOW}⚠ Using --no-cache for nginx to ensure config is rebuilt${NC}"

# Build nginx with --no-cache to ensure build args are applied
./scripts/dcprod.sh build --pull --no-cache nginx

# Build other services normally (with cache)
./scripts/dcprod.sh build --pull \
    prosaas-api \
    prosaas-calls \
    worker \
    frontend \
    baileys

echo -e "${GREEN}✓ Images built${NC}"

# Step 4: Stop and recreate containers
echo -e "\n${BLUE}Step 4: Recreating containers...${NC}"

# Use --force-recreate to ensure containers pick up new config
# Use --no-deps to avoid recreating dependencies unnecessarily
./scripts/dcprod.sh up -d --force-recreate \
    nginx \
    prosaas-api \
    prosaas-calls \
    worker \
    frontend \
    baileys \
    redis \
    n8n

echo -e "${GREEN}✓ Containers recreated${NC}"

# Step 5: Wait for services to be healthy
echo -e "\n${BLUE}Step 5: Waiting for services to be healthy...${NC}"
sleep 5

# Check container status
echo -e "\nContainer Status:"
./scripts/dcprod.sh ps

# Step 6: Clean up old images (optional, saves disk space)
echo -e "\n${BLUE}Step 6: Cleaning up old images...${NC}"
docker image prune -f --filter "dangling=true"
echo -e "${GREEN}✓ Cleanup complete${NC}"

# Step 7: Show logs from nginx to verify it's working
echo -e "\n${BLUE}Step 7: Checking NGINX logs for errors...${NC}"
sleep 2
NGINX_LOGS=$(docker logs prosaas-nginx --tail 20 2>&1 || true)

if echo "$NGINX_LOGS" | grep -qi "host not found in upstream"; then
    echo -e "${RED}✗ NGINX ERROR: Upstream host not found${NC}"
    echo "$NGINX_LOGS"
    echo -e "\n${YELLOW}Troubleshooting:${NC}"
    echo "1. Check running containers: docker compose ps"
    echo "2. Verify nginx config: docker exec prosaas-nginx nginx -T | grep proxy_pass"
    echo "3. Check if prosaas-api and prosaas-calls are healthy"
    exit 1
elif echo "$NGINX_LOGS" | grep -qi "error"; then
    echo -e "${YELLOW}⚠ NGINX warnings detected (may be normal):${NC}"
    echo "$NGINX_LOGS" | grep -i error
else
    echo -e "${GREEN}✓ NGINX logs look good${NC}"
fi

# Step 8: Verify proxy_pass configuration
echo -e "\n${BLUE}Step 8: Verifying NGINX proxy configuration...${NC}"
PROXY_CONFIG=$(docker exec prosaas-nginx nginx -T 2>/dev/null | grep "proxy_pass" || true)

if echo "$PROXY_CONFIG" | grep -q "prosaas-api:5000"; then
    echo -e "${GREEN}✓ API upstream: prosaas-api:5000${NC}"
else
    echo -e "${RED}✗ API upstream NOT pointing to prosaas-api:5000${NC}"
    echo "Current config:"
    echo "$PROXY_CONFIG" | grep -i "api"
fi

if echo "$PROXY_CONFIG" | grep -q "prosaas-calls:5050"; then
    echo -e "${GREEN}✓ Calls upstream: prosaas-calls:5050${NC}"
else
    echo -e "${RED}✗ Calls upstream NOT pointing to prosaas-calls:5050${NC}"
    echo "Current config:"
    echo "$PROXY_CONFIG" | grep -i "calls"
fi

# Summary
echo -e "\n${GREEN}===========================================
Deployment Complete! 🚀
===========================================${NC}"

echo -e "\n${BLUE}Next steps:${NC}"
echo "1. Check service status: docker compose -f docker-compose.yml -f docker-compose.prod.yml ps"
echo "2. View API logs: docker logs prosaas-api"
echo "3. View Calls logs: docker logs prosaas-calls"
echo "4. Test health endpoint: curl http://localhost/health"
echo "5. Monitor worker: docker logs prosaas-worker -f"

echo -e "\n${YELLOW}Important: If you STILL see 'host not found' errors:${NC}"
echo "  1. Verify services are running: docker compose ps"
echo "  2. Check nginx sees correct upstreams: docker exec prosaas-nginx nginx -T | grep proxy_pass"
echo "  3. If upstreams are wrong, rebuild nginx: docker compose build --no-cache nginx"
echo "  4. Then recreate: docker compose up -d --force-recreate nginx"
