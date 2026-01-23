#!/bin/bash
# ===========================================
# Verification Script for Nginx Health & Playwright Split
# ===========================================
# This script verifies the nginx healthcheck fix and image split changes
# Run after: docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

set -e

echo "=========================================="
echo "🔍 Verifying Nginx Health Check Fix"
echo "=========================================="

# Check if nginx is running
if docker compose ps nginx | grep -q "Up"; then
    echo "✅ nginx container is running"
else
    echo "❌ nginx container is not running"
    exit 1
fi

# Check nginx health status
NGINX_HEALTH=$(docker compose ps nginx --format json 2>/dev/null | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('Health', 'unknown'))" || echo "unknown")
echo "📊 nginx health status: $NGINX_HEALTH"

# Test health endpoint from inside nginx
echo ""
echo "Testing nginx health endpoint..."
if docker exec nginx wget -qO- http://localhost/health >/dev/null 2>&1; then
    echo "✅ nginx health endpoint responds correctly (using wget)"
else
    echo "❌ nginx health endpoint not responding"
    exit 1
fi

echo ""
echo "=========================================="
echo "🔍 Verifying Image Split"
echo "=========================================="

# Check docker images
echo ""
echo "📦 Docker images:"
docker images | grep -E "prosaasil|REPOSITORY" || true

echo ""
echo "Testing Playwright availability..."

# Test worker has Playwright
if docker exec worker python -c "from playwright.sync_api import sync_playwright; print('✅ Worker has Playwright')" 2>/dev/null; then
    echo "✅ Worker: Playwright available (expected)"
else
    echo "❌ Worker: Playwright not available (unexpected)"
fi

# Test API doesn't have Playwright (should fail gracefully)
if docker exec prosaas-api python -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
    echo "⚠️  API: Playwright available (unexpected - using heavy image?)"
else
    echo "✅ API: Playwright not available (expected - using light image)"
fi

# Test Calls doesn't have Playwright (should fail gracefully)
if docker exec prosaas-calls python -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
    echo "⚠️  Calls: Playwright available (unexpected - using heavy image?)"
else
    echo "✅ Calls: Playwright not available (expected - using light image)"
fi

echo ""
echo "=========================================="
echo "🔍 Verifying Service Health"
echo "=========================================="

# Check all services
echo ""
echo "📊 Service Status:"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "=========================================="
echo "✅ Verification Complete"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Monitor nginx for 60 seconds to ensure it stays healthy"
echo "2. Test receipt sync functionality (uses worker/Playwright)"
echo "3. Verify API and Calls endpoints work normally"
echo ""
echo "To monitor nginx health:"
echo "  watch -n 5 'docker compose ps nginx'"
echo ""
echo "To check logs:"
echo "  docker compose logs --tail=50 nginx"
echo "  docker compose logs --tail=50 worker"
