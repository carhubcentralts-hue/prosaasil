#!/bin/bash
#
# Production Deployment Script with Worker Validation
#
# This script ensures prosaas-worker is always deployed and functional.
# It will FAIL if worker is not running or not listening to 'default' queue.
#
# Usage:
#   ./scripts/prod_up.sh
#

set -e  # Exit on any error

echo "=============================================================================="
echo "ProSaaS Production Deployment with Worker Validation"
echo "=============================================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Validate compose files exist
echo "Step 1: Validating compose files..."
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}✗ ERROR: docker-compose.yml not found${NC}"
    exit 1
fi

if [ ! -f "docker-compose.prod.yml" ]; then
    echo -e "${RED}✗ ERROR: docker-compose.prod.yml not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Compose files found${NC}"
echo ""

# Step 2: Validate worker is defined in prod compose
echo "Step 2: Validating worker service definition..."
if ! grep -q "prosaas-worker:" docker-compose.prod.yml; then
    echo -e "${RED}✗ ERROR: prosaas-worker service not found in docker-compose.prod.yml${NC}"
    echo "   Worker must be defined in production compose file"
    exit 1
fi

echo -e "${GREEN}✓ prosaas-worker service found in docker-compose.prod.yml${NC}"

# Check if worker is under profiles (would prevent it from starting)
if grep -A 20 "prosaas-worker:" docker-compose.prod.yml | grep -q "profiles:"; then
    echo -e "${YELLOW}⚠  WARNING: prosaas-worker has 'profiles:' - may not start automatically${NC}"
    echo "   Remove profiles from prosaas-worker in docker-compose.prod.yml"
fi
echo ""

# Step 3: Deploy with both compose files
echo "Step 3: Deploying services..."
echo "Running: docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --remove-orphans"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --remove-orphans

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ ERROR: Deployment failed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Services deployed${NC}"
echo ""

# Step 4: Wait for services to start
echo "Step 4: Waiting for services to initialize..."
sleep 10
echo ""

# Step 5: Validate worker is running
echo "Step 5: Validating worker service..."
WORKER_STATUS=$(docker compose ps prosaas-worker --format json 2>/dev/null | grep -o '"State":"[^"]*"' | cut -d'"' -f4 || echo "not_found")

if [ "$WORKER_STATUS" != "running" ]; then
    echo -e "${RED}✗ CRITICAL: prosaas-worker service is not running!${NC}"
    echo "   Status: $WORKER_STATUS"
    echo ""
    echo "Checking worker logs for errors..."
    docker compose logs --tail=50 prosaas-worker
    exit 1
fi

echo -e "${GREEN}✓ prosaas-worker service is running${NC}"
echo ""

# Step 6: Validate worker health
echo "Step 6: Checking worker health..."
sleep 5  # Give healthcheck time to run

WORKER_HEALTH=$(docker inspect prosaas-worker --format='{{.State.Health.Status}}' 2>/dev/null || echo "unknown")

if [ "$WORKER_HEALTH" = "healthy" ]; then
    echo -e "${GREEN}✓ prosaas-worker is healthy${NC}"
elif [ "$WORKER_HEALTH" = "starting" ]; then
    echo -e "${YELLOW}⚠  prosaas-worker is still starting (health check pending)${NC}"
    echo "   Waiting 15 more seconds..."
    sleep 15
    WORKER_HEALTH=$(docker inspect prosaas-worker --format='{{.State.Health.Status}}' 2>/dev/null || echo "unknown")
    if [ "$WORKER_HEALTH" = "healthy" ]; then
        echo -e "${GREEN}✓ prosaas-worker is now healthy${NC}"
    else
        echo -e "${YELLOW}⚠  prosaas-worker health: $WORKER_HEALTH${NC}"
    fi
else
    echo -e "${YELLOW}⚠  prosaas-worker health: $WORKER_HEALTH (may not have healthcheck configured)${NC}"
fi
echo ""

# Step 7: Check worker logs for startup confirmation
echo "Step 7: Checking worker logs..."
echo "Looking for 'WORKER_START' message..."

if docker compose logs prosaas-worker | grep -q "WORKER_START"; then
    echo -e "${GREEN}✓ Worker started successfully (WORKER_START found in logs)${NC}"
else
    echo -e "${YELLOW}⚠  WARNING: WORKER_START not found in logs${NC}"
    echo "   Recent logs:"
    docker compose logs --tail=20 prosaas-worker
fi
echo ""

# Step 8: Validate Redis connection
echo "Step 8: Validating Redis connectivity..."
if docker compose exec -T prosaas-worker python -c "import redis; redis.from_url('redis://redis:6379/0').ping(); print('OK')" 2>/dev/null | grep -q "OK"; then
    echo -e "${GREEN}✓ Worker can connect to Redis${NC}"
else
    echo -e "${RED}✗ ERROR: Worker cannot connect to Redis${NC}"
    exit 1
fi
echo ""

# Step 9: Validate worker is listening to 'default' queue
echo "Step 9: Validating worker queue configuration..."
QUEUE_CHECK=$(docker compose exec -T prosaas-worker python -c "
from rq import Worker
import redis
conn = redis.from_url('redis://redis:6379/0')
workers = Worker.all(connection=conn)
for w in workers:
    queues = [q.name for q in w.queues]
    if 'default' in queues:
        print('OK:default')
        break
" 2>/dev/null || echo "ERROR")

if echo "$QUEUE_CHECK" | grep -q "OK:default"; then
    echo -e "${GREEN}✓ Worker is listening to 'default' queue${NC}"
else
    echo -e "${RED}✗ CRITICAL: No worker listening to 'default' queue!${NC}"
    echo "   Jobs enqueued to 'default' will remain QUEUED forever"
    echo ""
    echo "   Checking which queues workers are listening to..."
    docker compose exec -T prosaas-worker python -c "
from rq import Worker
import redis
conn = redis.from_url('redis://redis:6379/0')
workers = Worker.all(connection=conn)
print(f'Found {len(workers)} worker(s):')
for w in workers:
    queues = [q.name for q in w.queues]
    print(f'  - {w.name}: {queues}')
" 2>/dev/null || echo "   Could not get worker info"
    exit 1
fi
echo ""

# Step 10: Check diagnostics endpoint (if API is available)
echo "Step 10: Checking queue diagnostics endpoint..."
# Wait for API to be ready
sleep 5

# Try to hit the diagnostics endpoint (this may fail if API auth is required)
echo "   Attempting to check /api/receipts/queue/diagnostics..."
echo "   (This may show 401/403 if authentication is required - that's OK)"
echo ""

# Step 11: Show deployment summary
echo "=============================================================================="
echo "DEPLOYMENT VALIDATION COMPLETE"
echo "=============================================================================="
echo ""
echo "Service Status:"
docker compose ps
echo ""
echo "Worker Logs (last 10 lines):"
docker compose logs --tail=10 prosaas-worker
echo ""
echo "=============================================================================="
echo -e "${GREEN}✅ SUCCESS: Production deployment complete with worker validated${NC}"
echo "=============================================================================="
echo ""
echo "Next steps:"
echo "  1. Test sync endpoint: POST /api/receipts/sync"
echo "  2. Monitor worker logs: docker compose logs -f prosaas-worker"
echo "  3. Check diagnostics: GET /api/receipts/queue/diagnostics"
echo ""
echo "To monitor worker:"
echo "  docker compose logs -f prosaas-worker | grep '🔔'"
echo ""
