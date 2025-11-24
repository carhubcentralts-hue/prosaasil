-- ========================================
-- FIX: Make admin@admin.com a global system_admin
-- ========================================
-- This script fixes the production database to ensure admin@admin.com
-- is a global system administrator (business_id = NULL) instead of
-- being tied to a specific business.
--
-- Run this ONCE on the production database via:
-- Replit > Database tab > Production > Console
-- Then paste and execute this SQL
-- ========================================

-- Step 1: Update admin@admin.com to be global system_admin
UPDATE users 
SET 
    business_id = NULL,
    role = 'system_admin',
    is_active = true
WHERE email = 'admin@admin.com';

-- Step 2: Verify the change
SELECT 
    id, 
    email, 
    role, 
    business_id,
    is_active,
    created_at
FROM users 
WHERE email = 'admin@admin.com';

-- Expected result: business_id should be NULL
-- ========================================
