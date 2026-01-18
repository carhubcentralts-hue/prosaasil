#!/bin/bash
# 🚨 EMERGENCY FIX SCRIPT - Run this to fix enabled_pages error immediately
# This script connects to your PostgreSQL database and adds the missing column

echo "🚨 EMERGENCY HOTFIX - Adding enabled_pages column"
echo "=================================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running in Docker environment
if docker ps | grep -q prosaas-postgres; then
    echo "✅ Found prosaas-postgres container"
    echo ""
    
    # Get database credentials from docker-compose or env
    echo "${YELLOW}Attempting to connect to PostgreSQL...${NC}"
    echo ""
    
    # Run the SQL fix
    docker exec -i prosaas-postgres psql -U postgres -d postgres <<EOF
-- Add the missing column
ALTER TABLE business 
ADD COLUMN IF NOT EXISTS enabled_pages JSON NOT NULL DEFAULT '[]';

-- Set all businesses to have all pages enabled
UPDATE business 
SET enabled_pages = '["dashboard", "crm_leads", "crm_customers", "calls_inbound", "calls_outbound", "whatsapp_inbox", "whatsapp_broadcast", "emails", "calendar", "statistics", "invoices", "contracts", "settings", "users"]'::json
WHERE CAST(enabled_pages AS TEXT) = '[]' 
   OR enabled_pages IS NULL;

-- Verify it worked
SELECT 'VERIFICATION: ' || column_name || ' (' || data_type || ')' as result
FROM information_schema.columns 
WHERE table_name = 'business' AND column_name = 'enabled_pages';

-- Show sample data
SELECT 'SAMPLE DATA: Business ' || id || ' - ' || name || ' has ' || 
       json_array_length(CAST(enabled_pages AS json)) || ' pages enabled' as result
FROM business
LIMIT 3;

-- Success message
SELECT '✅ HOTFIX COMPLETED SUCCESSFULLY' as status;
EOF
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "${GREEN}=================================================="
        echo "✅ HOTFIX APPLIED SUCCESSFULLY!"
        echo "==================================================${NC}"
        echo ""
        echo "Next steps:"
        echo "1. Refresh your browser (Ctrl+Shift+R)"
        echo "2. Admin dashboard should now load"
        echo "3. Appointments should work"
        echo ""
        echo "${GREEN}No container restart needed!${NC}"
    else
        echo ""
        echo "${RED}❌ HOTFIX FAILED${NC}"
        echo ""
        echo "Please run the SQL manually:"
        echo "1. docker exec -it prosaas-postgres psql -U postgres -d postgres"
        echo "2. Copy SQL from HOTFIX_ADD_ENABLED_PAGES.sql"
        echo "3. Paste and execute"
    fi
else
    echo "${RED}❌ prosaas-postgres container not found${NC}"
    echo ""
    echo "Manual fix required:"
    echo "1. Connect to your PostgreSQL database"
    echo "2. Run the SQL from HOTFIX_ADD_ENABLED_PAGES.sql"
    echo ""
    echo "Or deploy the fix:"
    echo "git pull"
    echo "docker compose down"
    echo "docker compose up -d --build"
fi

echo ""
