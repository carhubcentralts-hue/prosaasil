#!/usr/bin/env bash
#
# Docker Compose Validation Script
# Validates that docker-compose files can be merged without errors
# and that nginx upstream services exist in the compose config
#
# Usage: ./scripts/validate_compose.sh [--skip-nginx-build]
#
# Exit codes:
#   0 - Success (compose files merge correctly and upstreams exist)
#   1 - Failure (compose merge failed or upstream validation failed)

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SKIP_NGINX_BUILD=false
if [ "${1:-}" = "--skip-nginx-build" ]; then
    SKIP_NGINX_BUILD=true
    echo -e "${YELLOW}ℹ️  Skipping nginx build validation${NC}"
    echo ""
fi

echo "🔍 Validating Docker Compose configuration..."
echo ""

# Ensure we're in the right directory
cd "$(dirname "$0")/.." || exit 1

# Create temporary .env file if it doesn't exist
# (compose config requires env_file to exist)
TEMP_ENV_CREATED=false
if [ ! -f .env ]; then
    echo -e "${YELLOW}ℹ️  Creating temporary .env file for validation${NC}"
    touch .env
    TEMP_ENV_CREATED=true
fi

# Cleanup function
cleanup() {
    [ "$TEMP_ENV_CREATED" = true ] && rm -f .env
}
trap cleanup EXIT

# Validate base compose file
echo "📝 Checking docker-compose.yml...
"
if docker compose -f docker-compose.yml config --quiet >/dev/null 2>&1; then
    echo -e "${GREEN}✅ docker-compose.yml is valid${NC}"
else
    echo -e "${RED}❌ docker-compose.yml has errors${NC}"
    docker compose -f docker-compose.yml config 2>&1 | grep -i "error" || true
    exit 1
fi

# Validate production override
echo "📝 Checking docker-compose.yml + docker-compose.prod.yml merge..."
if docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Compose files merge successfully${NC}"
else
    echo -e "${RED}❌ Compose merge has errors${NC}"
    echo ""
    echo "Full error output:"
    docker compose -f docker-compose.yml -f docker-compose.prod.yml config 2>&1 | grep -A 3 -i "error\|invalid" || true
    exit 1
fi

# Validate nginx upstream services exist
echo ""
echo "📝 Validating nginx upstream services..."

# Get the merged config
MERGED_CONFIG=$(docker compose -f docker-compose.yml -f docker-compose.prod.yml config 2>/dev/null)

# Extract nginx environment variables
API_UPSTREAM=$(echo "$MERGED_CONFIG" | grep -A 100 "nginx:" | grep "API_UPSTREAM:" | head -1 | sed 's/.*API_UPSTREAM: *//;s/"//g' || echo "backend")
CALLS_UPSTREAM=$(echo "$MERGED_CONFIG" | grep -A 100 "nginx:" | grep "CALLS_UPSTREAM:" | head -1 | sed 's/.*CALLS_UPSTREAM: *//;s/"//g' || echo "backend")
FRONTEND_UPSTREAM=$(echo "$MERGED_CONFIG" | grep -A 100 "nginx:" | grep "FRONTEND_UPSTREAM:" | head -1 | sed 's/.*FRONTEND_UPSTREAM: *//;s/"//g' || echo "frontend")

echo -e "${BLUE}Upstream configuration:${NC}"
echo "  API_UPSTREAM: ${API_UPSTREAM}"
echo "  CALLS_UPSTREAM: ${CALLS_UPSTREAM}"
echo "  FRONTEND_UPSTREAM: ${FRONTEND_UPSTREAM}"
echo ""

# Check each upstream service exists in config
VALIDATION_FAILED=false

for service in "$API_UPSTREAM" "$CALLS_UPSTREAM" "$FRONTEND_UPSTREAM"; do
    if echo "$MERGED_CONFIG" | grep -q "^  ${service}:"; then
        echo -e "${GREEN}✅ Service '${service}' exists in compose config${NC}"
    else
        echo -e "${RED}❌ Service '${service}' NOT FOUND in compose config${NC}"
        VALIDATION_FAILED=true
    fi
done

if [ "$VALIDATION_FAILED" = true ]; then
    echo ""
    echo -e "${RED}❌ Upstream validation FAILED${NC}"
    echo ""
    echo "Available services:"
    echo "$MERGED_CONFIG" | grep "^  [a-z]" | sed 's/:.*//' | sed 's/^/  /'
    exit 1
fi

# Optional: Validate nginx config generation with envsubst
if [ "$SKIP_NGINX_BUILD" = false ]; then
    echo ""
    echo "🧪 Testing nginx image build and config validation..."
    echo -e "${BLUE}Note: Use --skip-nginx-build to skip this step${NC}"
    
    # Build nginx image for testing
    echo "Building nginx test image..."
    if docker build -q -t prosaasil-nginx-test -f Dockerfile.nginx . >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Nginx image built successfully${NC}"
        
        # Test nginx config inside the built image
        echo "Testing nginx configuration..."
        if docker run --rm prosaasil-nginx-test nginx -t 2>&1 | grep -q "successful"; then
            echo -e "${GREEN}✅ nginx config valid${NC}"
        else
            echo -e "${RED}❌ nginx config invalid${NC}"
            docker run --rm prosaasil-nginx-test nginx -t
            exit 1
        fi
        
        # Clean up test image
        docker rmi -f prosaasil-nginx-test >/dev/null 2>&1 || true
    else
        echo -e "${RED}❌ Nginx image build failed${NC}"
        docker build -t prosaasil-nginx-test -f Dockerfile.nginx . 2>&1 | tail -20
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}✅ All validations passed!${NC}"
echo ""
echo "Deployment commands:"
echo "  # Production (without backend, uses prosaas-api/prosaas-calls):"
echo "  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
echo ""
echo "  # Development (with backend using --profile dev):"
echo "  docker compose --profile dev up -d"

exit 0
