-- ⚡ HOTFIX: Add enabled_pages column to business table
-- This script can be run immediately on production to fix the "column does not exist" error
-- Run this via psql or your database management tool

-- Step 1: Add the column with a default value
ALTER TABLE business 
ADD COLUMN IF NOT EXISTS enabled_pages JSON NOT NULL DEFAULT '[]';

-- Step 2: Set all existing businesses to have all pages enabled (backward compatibility)
-- This gives full access to all features for existing businesses
UPDATE business 
SET enabled_pages = '["dashboard", "crm_leads", "crm_customers", "calls_inbound", "calls_outbound", "whatsapp_inbox", "whatsapp_broadcast", "emails", "calendar", "statistics", "invoices", "contracts", "settings", "users"]'
WHERE CAST(enabled_pages AS TEXT) = '[]' 
   OR enabled_pages IS NULL;

-- Step 3: Verify the column was added
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'business' 
  AND column_name = 'enabled_pages';

-- Step 4: Verify businesses have pages set
SELECT 
    id,
    name,
    enabled_pages
FROM business
LIMIT 5;

-- Success message
SELECT '✅ HOTFIX APPLIED: enabled_pages column added and populated' AS status;
