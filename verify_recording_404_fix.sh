#!/bin/bash
# Verification script for recording 404 fix
# Tests that all services have the recordings_data volume mounted correctly

set -e

echo "=========================================="
echo "Recording 404 Fix Verification"
echo "=========================================="
echo ""

# Check if docker-compose is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    exit 1
fi

echo "✅ Docker is available"
echo ""

# Parse docker-compose files to check volume mounts
echo "Checking volume mounts in docker-compose files..."
echo ""

# Check docker-compose.yml
echo "📄 docker-compose.yml:"
if grep -A 50 "^  worker:" docker-compose.yml | grep -q "recordings_data:/app/server/recordings"; then
    echo "  ✅ worker service has recordings_data volume"
else
    echo "  ❌ worker service missing recordings_data volume"
    exit 1
fi

if grep -A 50 "^  backend:" docker-compose.yml | grep -q "recordings_data:/app/server/recordings"; then
    echo "  ✅ backend service has recordings_data volume"
else
    echo "  ⚠️  backend service missing recordings_data volume (check if using prosaas-api instead)"
fi

if grep -A 50 "^  prosaas-calls:" docker-compose.yml | grep -q "recordings_data:/app/server/recordings"; then
    echo "  ✅ prosaas-calls service has recordings_data volume"
else
    echo "  ❌ prosaas-calls service missing recordings_data volume"
    exit 1
fi

echo ""
echo "📄 docker-compose.prod.yml:"
if grep -A 80 "^  worker:" docker-compose.prod.yml | grep -q "recordings_data:/app/server/recordings"; then
    echo "  ✅ worker service has recordings_data volume"
else
    echo "  ❌ worker service missing recordings_data volume"
    exit 1
fi

if grep -A 80 "^  prosaas-api:" docker-compose.prod.yml | grep -q "recordings_data:/app/server/recordings"; then
    echo "  ✅ prosaas-api service has recordings_data volume"
else
    echo "  ❌ prosaas-api service missing recordings_data volume"
    exit 1
fi

if grep -A 80 "^  prosaas-calls:" docker-compose.prod.yml | grep -q "recordings_data:/app/server/recordings"; then
    echo "  ✅ prosaas-calls service has recordings_data volume"
else
    echo "  ❌ prosaas-calls service missing recordings_data volume"
    exit 1
fi

echo ""
echo "Checking that recordings_data volume is defined..."
if grep -q "^  recordings_data:" docker-compose.yml; then
    echo "  ✅ recordings_data volume is defined in docker-compose.yml"
else
    echo "  ❌ recordings_data volume not defined in docker-compose.yml"
    exit 1
fi

if grep -q "^  recordings_data:" docker-compose.prod.yml; then
    echo "  ✅ recordings_data volume is defined in docker-compose.prod.yml"
else
    echo "  ✅ recordings_data volume inherited from docker-compose.yml"
fi

echo ""
echo "Validating YAML syntax..."
python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml')); yaml.safe_load(open('docker-compose.prod.yml')); print('  ✅ YAML syntax is valid')"

echo ""
echo "=========================================="
echo "✅ All checks passed!"
echo "=========================================="
echo ""
echo "Next steps for deployment:"
echo "1. Stop services: docker compose -f docker-compose.yml -f docker-compose.prod.yml down"
echo "2. Pull changes: git pull"
echo "3. Start services: docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
echo "4. Verify mounts: docker compose exec worker ls -la /app/server/recordings"
echo "5. Test recording playback in UI"
echo ""
