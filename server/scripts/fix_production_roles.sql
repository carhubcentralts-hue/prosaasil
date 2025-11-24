-- ========================================
-- FIX PRODUCTION ROLES - Manual Correction
-- ========================================
-- This script fixes the reversed roles in production DB
-- caused by the initial migration script that didn't
-- consider business_id when mapping roles.
--
-- Run this ONCE in production database console:
-- ========================================

BEGIN;

-- Show current state (before fix)
SELECT id, email, role, business_id 
FROM users 
WHERE email IN ('admin@admin.com', 'admin@shai-realestate')
ORDER BY email;

-- Fix: admin@admin.com should be system_admin (global admin with no business)
UPDATE users 
SET role = 'system_admin' 
WHERE email = 'admin@admin.com' 
  AND business_id IS NULL;

-- Fix: admin@shai-realestate should be owner (business owner with business_id)
UPDATE users 
SET role = 'owner' 
WHERE email = 'admin@shai-realestate' 
  AND business_id IS NOT NULL;

-- Show fixed state (after fix)
SELECT id, email, role, business_id 
FROM users 
WHERE email IN ('admin@admin.com', 'admin@shai-realestate')
ORDER BY email;

-- If everything looks correct, commit:
COMMIT;

-- If something is wrong, rollback:
-- ROLLBACK;
