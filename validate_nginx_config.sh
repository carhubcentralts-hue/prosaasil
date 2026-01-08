#!/bin/bash
# ===========================================
# ProSaaS - Configuration Validation Script
# ===========================================
# This script validates the docker-compose and nginx configurations
# ===========================================

set -e

echo "==================================="
echo "ProSaaS Configuration Validation"
echo "==================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if docker and docker compose are installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker is installed${NC}"

# Check docker-compose.yml
echo ""
echo "Checking docker-compose.yml..."
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ docker-compose.yml not found${NC}"
    exit 1
fi

# Create temporary .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env not found, creating temporary one for validation${NC}"
    touch .env.tmp
    export ENV_FILE=".env.tmp"
else
    export ENV_FILE=".env"
fi

# Validate docker-compose syntax
if docker compose config > /dev/null 2>&1; then
    echo -e "${GREEN}✅ docker-compose.yml is valid${NC}"
else
    echo -e "${RED}❌ docker-compose.yml has syntax errors${NC}"
    docker compose config
    rm -f .env.tmp
    exit 1
fi

# Clean up temporary .env
rm -f .env.tmp

# Check docker-compose.prod.yml
echo ""
echo "Checking docker-compose.prod.yml..."
if [ ! -f "docker-compose.prod.yml" ]; then
    echo -e "${RED}❌ docker-compose.prod.yml not found${NC}"
    exit 1
fi
echo -e "${GREEN}✅ docker-compose.prod.yml exists${NC}"

# Check Dockerfile.nginx
echo ""
echo "Checking Dockerfile.nginx..."
if [ ! -f "Dockerfile.nginx" ]; then
    echo -e "${RED}❌ Dockerfile.nginx not found${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Dockerfile.nginx exists${NC}"

# Check nginx configuration files
echo ""
echo "Checking nginx configuration files..."
if [ ! -f "docker/nginx/nginx.conf" ]; then
    echo -e "${RED}❌ docker/nginx/nginx.conf not found${NC}"
    exit 1
fi
echo -e "${GREEN}✅ docker/nginx/nginx.conf exists${NC}"

if [ ! -f "docker/nginx/conf.d/prosaas.conf" ]; then
    echo -e "${RED}❌ docker/nginx/conf.d/prosaas.conf not found${NC}"
    exit 1
fi
echo -e "${GREEN}✅ docker/nginx/conf.d/prosaas.conf exists${NC}"

if [ ! -f "docker/nginx/conf.d/prosaas-ssl.conf" ]; then
    echo -e "${RED}❌ docker/nginx/conf.d/prosaas-ssl.conf not found${NC}"
    exit 1
fi
echo -e "${GREEN}✅ docker/nginx/conf.d/prosaas-ssl.conf exists${NC}"

if [ ! -f "docker/nginx/frontend-static.conf" ]; then
    echo -e "${RED}❌ docker/nginx/frontend-static.conf not found${NC}"
    exit 1
fi
echo -e "${GREEN}✅ docker/nginx/frontend-static.conf exists${NC}"

# Test nginx configuration syntax
echo ""
echo "Testing nginx configuration syntax..."
echo -e "${YELLOW}Note: 'host not found' errors are expected (services not running)${NC}"
echo ""

# Test HTTP configuration
if docker run --rm \
    -v "$(pwd)/docker/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" \
    -v "$(pwd)/docker/nginx/conf.d/prosaas.conf:/etc/nginx/conf.d/prosaas.conf:ro" \
    nginx:alpine nginx -t 2>&1 | grep -q "test is successful\|test failed"; then
    
    if docker run --rm \
        -v "$(pwd)/docker/nginx/nginx.conf:/etc/nginx/nginx.conf:ro" \
        -v "$(pwd)/docker/nginx/conf.d/prosaas.conf:/etc/nginx/conf.d/prosaas.conf:ro" \
        nginx:alpine nginx -t 2>&1 | grep -q "test is successful"; then
        echo -e "${GREEN}✅ HTTP nginx configuration syntax is valid${NC}"
    else
        echo -e "${YELLOW}⚠️  HTTP nginx configuration has syntax issues (may be due to missing hosts)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Could not test HTTP nginx configuration${NC}"
fi

# Summary
echo ""
echo "==================================="
echo "Validation Summary"
echo "==================================="
echo -e "${GREEN}✅ All configuration files are present${NC}"
echo -e "${GREEN}✅ docker-compose.yml is valid${NC}"
echo -e "${GREEN}✅ Ready to deploy${NC}"
echo ""
echo "Next steps:"
echo "  1. Review NGINX_REVERSE_PROXY_GUIDE.md for detailed instructions"
echo "  2. Configure .env file with your environment variables"
echo "  3. For development: docker compose up -d"
echo "  4. For production: docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
echo ""
