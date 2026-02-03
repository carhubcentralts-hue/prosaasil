-- Migration: Add ON DELETE CASCADE to appointment_automation_runs
-- Purpose: Prevent NotNullViolation errors when deleting appointments
-- Date: 2026-02-03

-- Step 1: Drop existing foreign key constraint
ALTER TABLE appointment_automation_runs 
DROP CONSTRAINT IF EXISTS appointment_automation_runs_appointment_id_fkey;

-- Step 2: Re-add foreign key with ON DELETE CASCADE
ALTER TABLE appointment_automation_runs
ADD CONSTRAINT appointment_automation_runs_appointment_id_fkey
FOREIGN KEY (appointment_id)
REFERENCES appointments(id)
ON DELETE CASCADE;

-- Verification query (optional - run separately to check):
-- SELECT conname, confdeltype 
-- FROM pg_constraint 
-- WHERE conname = 'appointment_automation_runs_appointment_id_fkey';
-- Expected: confdeltype = 'c' (CASCADE)
