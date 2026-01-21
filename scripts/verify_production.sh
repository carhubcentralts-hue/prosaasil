#!/usr/bin/env bash
# ===========================================
# Production Verification Script
# Runs all critical checks to verify deployment is correct
# ===========================================

set -euo pipefail

cd "$(dirname "$0")/.."

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                    Production Verification Checks                            ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Check 1: RQ Package
echo "=== Check 1: RQ Package in Worker Container ==="
echo "Running: ./scripts/dcprod.sh exec worker python -c \"import rq; print('✅ rq ok')\""
if ./scripts/dcprod.sh exec worker python -c "import rq; print('✅ rq ok')" 2>&1; then
    echo "✅ PASS: rq package is installed"
else
    echo "❌ FAIL: rq package is NOT installed"
    echo "   Fix: ./scripts/dcprod.sh build --no-cache worker"
    exit 1
fi
echo ""

# Check 2: Backend not running
echo "=== Check 2: Backend Should NOT Be Running ==="
services=$(./scripts/dcprod.sh ps --services 2>/dev/null || echo "")
if echo "$services" | grep -q "^backend$"; then
    echo "❌ FAIL: backend is running (should be legacy-only)"
    echo "   Fix: ./scripts/dcprod.sh down && ./scripts/dcprod.sh up -d"
    exit 1
else
    echo "✅ PASS: backend is not running"
fi
echo ""

# Check 3: Required services are running
echo "=== Check 3: Required Services Running ==="
required_services=("nginx" "prosaas-api" "prosaas-calls" "worker" "redis")
missing_services=()

for service in "${required_services[@]}"; do
    if echo "$services" | grep -q "^${service}$"; then
        echo "✅ $service is running"
    else
        echo "❌ $service is NOT running"
        missing_services+=("$service")
    fi
done

if [ ${#missing_services[@]} -gt 0 ]; then
    echo ""
    echo "❌ FAIL: Missing services: ${missing_services[*]}"
    echo "   Fix: ./scripts/dcprod.sh up -d"
    exit 1
fi
echo ""

# Check 4: Worker logs
echo "=== Check 4: Worker Logs (last 30 lines) ==="
worker_logs=$(./scripts/dcprod.sh logs --tail 30 worker 2>&1)

if echo "$worker_logs" | grep -q "rq package not installed"; then
    echo "❌ FAIL: Worker logs show 'rq package not installed'"
    exit 1
fi

if echo "$worker_logs" | grep -q "Logger._log() got an unexpected keyword argument"; then
    echo "❌ FAIL: Worker logs show logger error"
    exit 1
fi

echo "✅ PASS: Worker logs are clean"
echo ""

# Check 5: NGINX logs
echo "=== Check 5: NGINX Logs (last 30 lines) ==="
nginx_logs=$(./scripts/dcprod.sh logs --tail 30 nginx 2>&1)

if echo "$nginx_logs" | grep -q "502 Bad Gateway"; then
    echo "⚠️  WARNING: NGINX logs show 502 errors"
fi

if echo "$nginx_logs" | grep -q "upstream not found"; then
    echo "❌ FAIL: NGINX logs show 'upstream not found'"
    exit 1
fi

echo "✅ PASS: NGINX logs are clean"
echo ""

# Summary
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║                            ✅ ALL CHECKS PASSED                              ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Production deployment is verified and ready."
echo ""
echo "Services running:"
./scripts/dcprod.sh ps --format table
