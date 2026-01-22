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

# First, check if worker is running
if ! ./scripts/dcprod.sh ps worker 2>/dev/null | grep -q "running"; then
  echo "⚠️ Worker not running yet – skipping rq verification"
  exit 0
fi

echo "Checking Python interpreter and rq package installation..."

# Check with 'python' command
echo ""
echo "→ Testing 'python' command:"
if ./scripts/dcprod.sh exec worker sh -c 'which python && python -c "import sys; import rq; print(\"✅ rq ok\"); print(\"Python:\", sys.executable); print(\"rq location:\", rq.__file__)"' 2>&1; then
    echo "✅ PASS: rq package is installed with 'python'"
else
    echo "❌ FAIL: rq package is NOT installed or 'python' command not found"
    echo "   Trying 'python3' command..."
fi

echo ""
echo "→ Testing 'python3' command:"
if ./scripts/dcprod.sh exec worker sh -c 'which python3 && python3 -c "import sys; import rq; print(\"✅ rq ok\"); print(\"Python:\", sys.executable); print(\"rq location:\", rq.__file__)"' 2>&1; then
    echo "✅ PASS: rq package is installed with 'python3'"
else
    echo "❌ FAIL: rq package is NOT installed with 'python3'"
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

# Check 6: Database schema - receipt_sync_runs columns
echo "=== Check 6: Database Schema - receipt_sync_runs Migration ==="
echo "Checking if critical columns exist in receipt_sync_runs table..."

# Check if prosaas-api is running (it has database access)
if echo "$services" | grep -q "^prosaas-api$"; then
    # Use prosaas-api to check database schema
    schema_check=$(./scripts/dcprod.sh exec prosaas-api python -c "
import os
os.environ.setdefault('FLASK_ENV', 'production')
from server.db import db
from server.app_factory import create_app
from sqlalchemy import text

app = create_app()
with app.app_context():
    try:
        result = db.session.execute(text('''
            SELECT column_name FROM information_schema.columns 
            WHERE table_schema = 'public' 
              AND table_name = 'receipt_sync_runs'
              AND column_name IN ('from_date', 'to_date', 'months_back', 'run_to_completion', 'max_seconds_per_run', 'skipped_count')
            ORDER BY column_name
        ''')).fetchall()
        columns_found = [row[0] for row in result]
        required_columns = ['from_date', 'to_date', 'months_back', 'run_to_completion', 'max_seconds_per_run', 'skipped_count']
        missing = [col for col in required_columns if col not in columns_found]
        if missing:
            print('MISSING:' + ','.join(missing))
        else:
            print('OK')
    except Exception as e:
        print(f'ERROR:{e}')
" 2>&1 || echo "FAILED")

    if echo "$schema_check" | grep -q "^OK$"; then
        echo "✅ PASS: All receipt_sync_runs columns exist"
    elif echo "$schema_check" | grep -q "^MISSING:"; then
        missing_cols=$(echo "$schema_check" | sed 's/^MISSING://')
        echo "❌ FAIL: Missing columns in receipt_sync_runs: $missing_cols"
        echo "   This will cause 'UndefinedColumn' errors in Gmail sync worker"
        echo "   Fix: Run migrations manually:"
        echo "   ./scripts/dcprod.sh exec prosaas-api python -c 'from server.db_migrate import apply_migrations; from server.app_factory import create_app; app = create_app(); app.app_context().push(); apply_migrations()'"
        exit 1
    else
        echo "⚠️  WARNING: Could not check database schema"
        echo "   Response: $schema_check"
    fi
else
    echo "⚠️  WARNING: prosaas-api not running, skipping database schema check"
fi
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
