#!/usr/bin/env bash
#
# Docker Compose Validation Script
# Validates that docker-compose files can be merged without errors
#
# Usage: ./scripts/validate_compose.sh
#
# Exit codes:
#   0 - Success (compose files merge correctly)
#   1 - Failure (compose merge failed)

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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

# Validate base compose file
echo "📝 Checking docker-compose.yml..."
if docker compose -f docker-compose.yml config --quiet >/dev/null 2>&1; then
    echo -e "${GREEN}✅ docker-compose.yml is valid${NC}"
else
    echo -e "${RED}❌ docker-compose.yml has errors${NC}"
    docker compose -f docker-compose.yml config 2>&1 | grep -i "error" || true
    [ "$TEMP_ENV_CREATED" = true ] && rm -f .env
    exit 1
fi

# Validate production override
echo "📝 Checking docker-compose.prod.yml..."
if docker compose -f docker-compose.yml -f docker-compose.prod.yml config --quiet >/dev/null 2>&1; then
    echo -e "${GREEN}✅ docker-compose.yml + docker-compose.prod.yml merge is valid${NC}"
else
    echo -e "${RED}❌ Compose merge has errors${NC}"
    echo ""
    echo "Full error output:"
    docker compose -f docker-compose.yml -f docker-compose.prod.yml config 2>&1 | grep -A 3 -i "error\|invalid" || true
    [ "$TEMP_ENV_CREATED" = true ] && rm -f .env
    exit 1
fi

# Clean up temporary .env if we created it
[ "$TEMP_ENV_CREATED" = true ] && rm -f .env

echo ""
echo -e "${GREEN}✅ All Docker Compose validations passed!${NC}"
echo ""
echo "You can now deploy with:"
echo "  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d"

exit 0
