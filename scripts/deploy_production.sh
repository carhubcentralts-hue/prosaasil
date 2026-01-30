#!/usr/bin/env bash
# ==========================================
# ProSaaS Production Deployment Script
# Single source of truth for production deployments
# ==========================================
#
# This script ensures proper deployment order:
# 1. Stop services to release database connections
# 2. Run migrations (and wait for completion)
# 3. Then start all other services
#
# It also handles:
# - Proper error handling at each step
# - Clear logging of what's happening
# - Verification that migrations succeeded
# - Idempotent operations (safe to run multiple times)
#
# Usage:
#   ./scripts/deploy_production.sh                # Full deploy with build
#   ./scripts/deploy_production.sh --rebuild      # Force rebuild all images
#   ./scripts/deploy_production.sh --migrate-only # Only run migrations
#   ./scripts/deploy_production.sh --kill-idle-tx # Kill idle transactions before migrations
#
# ==========================================

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BASE_COMPOSE="docker-compose.yml"
PROD_COMPOSE="docker-compose.prod.yml"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT"

# Parse arguments
REBUILD=false
MIGRATE_ONLY=false
KILL_IDLE_TX=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --rebuild)
            REBUILD=true
            shift
            ;;
        --migrate-only)
            MIGRATE_ONLY=true
            shift
            ;;
        --kill-idle-tx)
            KILL_IDLE_TX=true
            shift
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            echo "Usage: $0 [--rebuild] [--migrate-only] [--kill-idle-tx]"
            exit 1
            ;;
    esac
done

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Check that compose files exist
if [[ ! -f "$BASE_COMPOSE" || ! -f "$PROD_COMPOSE" ]]; then
    log_error "Docker compose files not found"
    log_error "  Expected: $BASE_COMPOSE and $PROD_COMPOSE"
    exit 1
fi

log_header "ProSaaS Production Deployment"
log_info "Using:"
log_info "  - $BASE_COMPOSE"
log_info "  - $PROD_COMPOSE"
log_info "  - Project root: $PROJECT_ROOT"

# Check if .env file exists
if [[ ! -f ".env" ]]; then
    log_warning ".env file not found - using environment variables"
else
    log_success ".env file found"
fi

# Step 1: Build images if requested
if [[ "$REBUILD" == true ]]; then
    log_header "Step 1: Building Docker Images"
    log_info "Rebuilding all images..."
    
    docker compose \
        -f "$BASE_COMPOSE" \
        -f "$PROD_COMPOSE" \
        build --no-cache
    
    log_success "All images rebuilt"
else
    log_header "Step 1: Checking Docker Images"
    log_info "Pulling/building images as needed..."
    
    docker compose \
        -f "$BASE_COMPOSE" \
        -f "$PROD_COMPOSE" \
        build
    
    log_success "Images ready"
fi

# Step 2: Stop services to avoid locks during migrations
log_header "Step 2: Stopping Services Before Migration"
log_info "Stopping all services that connect to the database..."

# Stop ALL services that might hold database connections and block migrations
# This prevents "idle in transaction" locks that cause DDL to timeout
# 
# Services stopped:
# - prosaas-api: Main API service (holds DB connections)
# - prosaas-calls: Calls/WebSocket service (holds DB connections)
# - worker: Background job worker (holds DB connections)
# - scheduler: Scheduled task service (holds DB connections)
# - baileys: WhatsApp service (may hold DB connections)
# - n8n: Workflow automation (may hold DB connections if using same DB)
#
# Services NOT stopped:
# - nginx: Reverse proxy (no DB connection)
# - redis: Queue backend (no DB connection)
# - frontend: Static files (no DB connection)
# - postgres/db: The database itself (if running locally)
docker compose \
    -f "$BASE_COMPOSE" \
    -f "$PROD_COMPOSE" \
    stop prosaas-api prosaas-calls worker scheduler baileys n8n 2>/dev/null || true

log_success "Stop command executed"

# Verify services are actually stopped
log_info "Verifying all database-connected services are stopped..."

# Get list of running services
RUNNING_SERVICES=$(docker compose \
    -f "$BASE_COMPOSE" \
    -f "$PROD_COMPOSE" \
    ps --services --filter "status=running" 2>/dev/null || echo "")

# List of services that MUST be stopped (connect to database)
DB_SERVICES="prosaas-api prosaas-calls worker scheduler baileys n8n"

# Check if any DB-connected service is still running
STILL_RUNNING=""
for service in $DB_SERVICES; do
    if echo "$RUNNING_SERVICES" | grep -q "^${service}$"; then
        STILL_RUNNING="$STILL_RUNNING $service"
    fi
done

if [ -n "$STILL_RUNNING" ]; then
    log_error "Some database-connected services are still running:$STILL_RUNNING"
    log_error "These services must be stopped before migrations to prevent locks"
    log_info "Attempting force stop..."
    
    # Try force stop
    docker compose \
        -f "$BASE_COMPOSE" \
        -f "$PROD_COMPOSE" \
        stop -t 10 $STILL_RUNNING 2>/dev/null || true
    
    # Check again
    sleep 2
    RUNNING_SERVICES=$(docker compose \
        -f "$BASE_COMPOSE" \
        -f "$PROD_COMPOSE" \
        ps --services --filter "status=running" 2>/dev/null || echo "")
    
    STILL_RUNNING=""
    for service in $DB_SERVICES; do
        if echo "$RUNNING_SERVICES" | grep -q "^${service}$"; then
            STILL_RUNNING="$STILL_RUNNING $service"
        fi
    done
    
    if [ -n "$STILL_RUNNING" ]; then
        log_error "Failed to stop services:$STILL_RUNNING"
        log_error "Cannot proceed safely with migrations"
        exit 1
    fi
fi

log_success "✅ All database-connected services confirmed stopped"
log_info "Running services status:"
docker compose \
    -f "$BASE_COMPOSE" \
    -f "$PROD_COMPOSE" \
    ps --format "table {{.Name}}\t{{.Status}}\t{{.Service}}" 2>/dev/null || true

# Step 2.5: Check active database connections
log_header "Step 2.5: Checking Active Database Connections"
log_info "Checking for active connections to the database..."

# Run connection check using the migrate container
# This will use DATABASE_URL_DIRECT from the environment
if docker compose \
    -f "$BASE_COMPOSE" \
    -f "$PROD_COMPOSE" \
    run --rm migrate \
    python -c "
import os
import sys
from sqlalchemy import create_engine, text

try:
    # Import centralized database_url module
    sys.path.insert(0, '/app')
    from server.database_url import get_database_url
    
    # Get direct database URL
    db_url = get_database_url(connection_type='direct')
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        result = conn.execute(text('''
            SELECT 
                pid,
                usename,
                application_name,
                state,
                left(query, 80) as query
            FROM pg_stat_activity
            WHERE datname = current_database()
            AND pid != pg_backend_pid()
            ORDER BY state, query_start DESC
        '''))
        
        rows = result.fetchall()
        if rows:
            print('\n📊 Active database connections:')
            print('=' * 80)
            for row in rows:
                print(f'  PID: {row[0]} | User: {row[1]} | App: {row[2]} | State: {row[3]}')
                print(f'    Query: {row[4] if row[4] else \"(idle)\"}')
                print('-' * 80)
            print(f'\nTotal connections: {len(rows)}')
        else:
            print('✅ No active database connections (besides this check)')
            
except Exception as e:
    print(f'⚠️  Could not check database connections: {e}')
    print('   This is not critical - continuing with deployment')
" 2>/dev/null || log_warning "Could not check database connections"; then
    log_success "Database connection check completed"
else
    log_warning "Database connection check failed (non-critical)"
fi

# Optional: Kill idle transactions if requested
if [[ "$KILL_IDLE_TX" == true ]]; then
    log_info "Killing idle transactions (--kill-idle-tx flag set)..."
    
    # Run the kill idle transactions script inside a container with database access
    docker compose \
        -f "$BASE_COMPOSE" \
        -f "$PROD_COMPOSE" \
        run --rm migrate python scripts/kill_idle_transactions.py || true
    
    log_success "Idle transactions cleared"
fi

# Step 3: Run migrations
log_header "Step 3: Running Database Migrations"
log_info "Starting migration service..."

# Stop any existing migrate container
docker compose \
    -f "$BASE_COMPOSE" \
    -f "$PROD_COMPOSE" \
    rm -f -s migrate 2>/dev/null || true

# Run migrations (this will create and run the migrate service)
log_info "Executing migrations..."
docker compose \
    -f "$BASE_COMPOSE" \
    -f "$PROD_COMPOSE" \
    run --rm migrate

# Check if migrations succeeded
MIGRATE_EXIT_CODE=$?
if [ $MIGRATE_EXIT_CODE -ne 0 ]; then
    log_error "Migrations failed with exit code $MIGRATE_EXIT_CODE"
    log_error "Cannot proceed with deployment"
    exit 1
fi

log_success "Migrations completed successfully"

# Step 3.5: Build indexes (separate from migrations)
log_header "Step 3.5: Building Performance Indexes"
log_info "Running index builder (non-blocking)..."

# Stop any existing indexer container
docker compose \
    -f "$BASE_COMPOSE" \
    -f "$PROD_COMPOSE" \
    rm -f -s indexer 2>/dev/null || true

# Run index builder
# ⚠️ IMPORTANT: Index builder NEVER fails deployment
# It exits 0 even if some indexes fail, allowing deployment to continue
log_info "Executing index builder..."
docker compose \
    -f "$BASE_COMPOSE" \
    -f "$PROD_COMPOSE" \
    run --rm indexer

# Index builder always exits 0, so we don't check exit code
# Just log that it completed
log_success "Index builder completed (check logs above for any warnings)"

# Step 3.6: Run data backfill (separate from migrations)
log_header "Step 3.6: Running Data Backfill Operations"
log_info "Running backfill tool (non-blocking)..."

# Stop any existing backfill container
docker compose \
    -f "$BASE_COMPOSE" \
    -f "$PROD_COMPOSE" \
    rm -f -s backfill 2>/dev/null || true

# Run backfill tool
# ⚠️ IMPORTANT: Backfill tool NEVER fails deployment
# It exits 0 even if incomplete, allowing deployment to continue
# Backfill is idempotent and will continue on next deployment if needed
log_info "Executing backfill tool..."
docker compose \
    -f "$BASE_COMPOSE" \
    -f "$PROD_COMPOSE" \
    run --rm backfill

# Backfill tool always exits 0, so we don't check exit code
# Just log that it completed
log_success "Backfill tool completed (check logs above for any warnings)"

# If migrate-only flag is set, stop here
if [[ "$MIGRATE_ONLY" == true ]]; then
    log_header "Migration-Only Mode"
    log_success "Migrations completed. Not starting services."
    exit 0
fi

# Step 4: Start all services
log_header "Step 4: Starting All Services"
log_info "Starting services in correct dependency order..."

# Start services (docker compose will handle dependencies)
docker compose \
    -f "$BASE_COMPOSE" \
    -f "$PROD_COMPOSE" \
    up -d \
    --remove-orphans

log_success "All services started"

# Step 5: Verify services are healthy
log_header "Step 5: Verifying Service Health"
log_info "Waiting for services to become healthy..."

# Wait a bit for services to start
sleep 5

# Check service status
log_info "Service status:"
docker compose \
    -f "$BASE_COMPOSE" \
    -f "$PROD_COMPOSE" \
    ps

# List running services
RUNNING_SERVICES=$(docker compose \
    -f "$BASE_COMPOSE" \
    -f "$PROD_COMPOSE" \
    ps --services --filter "status=running")

if [ -z "$RUNNING_SERVICES" ]; then
    log_error "No services are running!"
    log_error "Check logs with: docker compose -f $BASE_COMPOSE -f $PROD_COMPOSE logs"
    exit 1
fi

log_success "Services are running:"
echo "$RUNNING_SERVICES" | while read -r service; do
    log_info "  • $service"
done

# Step 6: Show next steps
log_header "Deployment Complete!"
log_success "ProSaaS is now running in production mode"
echo ""
log_info "Useful commands:"
log_info "  • View logs:        ./scripts/dcprod.sh logs -f [service]"
log_info "  • Check status:     ./scripts/dcprod.sh ps"
log_info "  • Restart service:  ./scripts/dcprod.sh restart [service]"
log_info "  • Stop all:         ./scripts/dcprod.sh down"
echo ""
log_info "To run migrations again:"
log_info "  • docker compose -f $BASE_COMPOSE -f $PROD_COMPOSE run --rm migrate"
echo ""
