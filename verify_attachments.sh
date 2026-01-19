#!/bin/bash
# Attachments System Verification Script
# בודק שמערכת ה-Attachments עובדת כראוי

echo "========================================="
echo "🔍 Attachments System Verification"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if docker is running
if ! docker ps > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running${NC}"
    exit 1
fi

echo "1️⃣ Checking if backend container is running..."
if docker ps | grep -q prosaas-backend; then
    echo -e "${GREEN}✅ Backend container is running${NC}"
else
    echo -e "${RED}❌ Backend container is not running${NC}"
    echo "Run: docker compose up -d"
    exit 1
fi
echo ""

echo "2️⃣ Checking migration execution..."
if docker logs prosaas-backend 2>&1 | grep -q "Migration 76 completed"; then
    echo -e "${GREEN}✅ Migration 76 (attachments) completed${NC}"
else
    echo -e "${YELLOW}⚠️  Migration 76 not found in logs${NC}"
    echo "This might be a first run. Check if migrations are enabled."
fi

if docker logs prosaas-backend 2>&1 | grep -q "Migration 77 completed"; then
    echo -e "${GREEN}✅ Migration 77 (contracts) completed${NC}"
else
    echo -e "${YELLOW}⚠️  Migration 77 not found in logs${NC}"
fi
echo ""

echo "3️⃣ Checking environment variables..."
if docker exec prosaas-backend env | grep -q "RUN_MIGRATIONS_ON_START=1"; then
    echo -e "${GREEN}✅ RUN_MIGRATIONS_ON_START is enabled${NC}"
else
    echo -e "${RED}❌ RUN_MIGRATIONS_ON_START is not set${NC}"
    echo "Add to docker-compose.yml: RUN_MIGRATIONS_ON_START: 1"
fi

if docker exec prosaas-backend env | grep -q "ATTACHMENT_SECRET"; then
    echo -e "${GREEN}✅ ATTACHMENT_SECRET is configured${NC}"
else
    echo -e "${YELLOW}⚠️  ATTACHMENT_SECRET is not set${NC}"
    echo "Attachments may not work without this!"
fi

# Check storage driver
STORAGE_DRIVER=$(docker exec prosaas-backend env | grep "ATTACHMENT_STORAGE_DRIVER" | cut -d= -f2)
if [ -n "$STORAGE_DRIVER" ]; then
    echo -e "${GREEN}✅ Storage driver: ${STORAGE_DRIVER}${NC}"
    
    if [ "$STORAGE_DRIVER" = "r2" ]; then
        echo "   Checking R2 configuration..."
        if docker exec prosaas-backend env | grep -q "R2_BUCKET_NAME"; then
            echo -e "   ${GREEN}✅ R2_BUCKET_NAME configured${NC}"
        else
            echo -e "   ${RED}❌ R2_BUCKET_NAME not set${NC}"
        fi
        if docker exec prosaas-backend env | grep -q "R2_ACCESS_KEY_ID"; then
            echo -e "   ${GREEN}✅ R2_ACCESS_KEY_ID configured${NC}"
        else
            echo -e "   ${RED}❌ R2_ACCESS_KEY_ID not set${NC}"
        fi
    fi
else
    echo -e "${YELLOW}⚠️  Storage driver not explicitly set (defaults to local)${NC}"
fi
echo ""

echo "4️⃣ Checking database tables..."
# Try to query the database
DB_CHECK=$(docker exec prosaas-backend python -c "
from server.app_factory import create_minimal_app
from server.db import db
app = create_minimal_app()
with app.app_context():
    try:
        result = db.session.execute(db.text('SELECT 1 FROM attachments LIMIT 1'))
        print('attachments_ok')
    except Exception as e:
        print(f'attachments_error: {e}')
    
    try:
        result = db.session.execute(db.text('SELECT 1 FROM contract_files LIMIT 1'))
        print('contract_files_ok')
    except Exception as e:
        print(f'contract_files_error: {e}')
" 2>&1)

if echo "$DB_CHECK" | grep -q "attachments_ok"; then
    echo -e "${GREEN}✅ attachments table exists${NC}"
else
    echo -e "${RED}❌ attachments table does not exist${NC}"
    echo "Run migrations: docker exec prosaas-backend python -m server.db_migrate"
fi

if echo "$DB_CHECK" | grep -q "contract_files_ok"; then
    echo -e "${GREEN}✅ contract_files table exists${NC}"
else
    echo -e "${RED}❌ contract_files table does not exist${NC}"
fi
echo ""

echo "5️⃣ Checking API endpoints..."
# Check if attachment API is accessible
ATTACHMENT_API=$(docker exec prosaas-backend python -c "
from server.app_factory import get_process_app
app = get_process_app()
with app.app_context():
    blueprints = [bp.name for bp in app.blueprints.values()]
    if 'attachments' in blueprints:
        print('attachments_bp_registered')
    else:
        print('attachments_bp_missing')
" 2>&1)

if echo "$ATTACHMENT_API" | grep -q "attachments_bp_registered"; then
    echo -e "${GREEN}✅ Attachments blueprint registered${NC}"
else
    echo -e "${RED}❌ Attachments blueprint not registered${NC}"
fi
echo ""

echo "6️⃣ Checking storage directory..."
if docker exec prosaas-backend test -d /app/storage/attachments; then
    echo -e "${GREEN}✅ Storage directory exists${NC}"
    
    # Check permissions
    PERMS=$(docker exec prosaas-backend stat -c "%a" /app/storage/attachments 2>&1)
    if [ "$PERMS" = "755" ] || [ "$PERMS" = "777" ]; then
        echo -e "${GREEN}✅ Storage directory is writable (${PERMS})${NC}"
    else
        echo -e "${YELLOW}⚠️  Storage directory permissions: ${PERMS}${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Storage directory does not exist (will be created on first upload)${NC}"
fi
echo ""

echo "========================================="
echo "📊 Summary"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. If migrations didn't run, restart containers:"
echo "   docker compose down && docker compose up -d --build"
echo ""
echo "2. Test functionality:"
echo "   - Create a contract and upload a file"
echo "   - Send an email with attachment"
echo "   - Create a broadcast with media"
echo ""
echo "3. Check logs if something fails:"
echo "   docker logs prosaas-backend | grep -i attachment"
echo ""
echo "For detailed guide, see: ATTACHMENTS_FIX_GUIDE.md"
echo ""
