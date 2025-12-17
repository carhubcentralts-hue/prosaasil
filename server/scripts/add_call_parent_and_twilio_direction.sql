-- ========================================
-- FIX: Add parent_call_sid and twilio_direction to call_log
-- ========================================
-- This script adds the parent_call_sid and twilio_direction columns to prevent
-- duplicate call logs and properly track call direction from Twilio.
-- 
-- Usage:
--   psql $DATABASE_URL -f add_call_parent_and_twilio_direction.sql
-- ========================================

-- Start transaction for safety
BEGIN;

-- Step 1: Add parent_call_sid column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' 
          AND table_name = 'call_log' 
          AND column_name = 'parent_call_sid'
    ) THEN
        ALTER TABLE public.call_log 
        ADD COLUMN parent_call_sid VARCHAR(64);
        
        RAISE NOTICE 'Added column: call_log.parent_call_sid';
    ELSE
        RAISE NOTICE 'Column already exists: call_log.parent_call_sid';
    END IF;
END $$;

-- Step 2: Add twilio_direction column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' 
          AND table_name = 'call_log' 
          AND column_name = 'twilio_direction'
    ) THEN
        ALTER TABLE public.call_log 
        ADD COLUMN twilio_direction VARCHAR(32);
        
        RAISE NOTICE 'Added column: call_log.twilio_direction';
    ELSE
        RAISE NOTICE 'Column already exists: call_log.twilio_direction';
    END IF;
END $$;

-- Step 3: Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_call_log_parent_call_sid 
ON public.call_log (parent_call_sid);

CREATE INDEX IF NOT EXISTS idx_call_log_twilio_direction 
ON public.call_log (twilio_direction);

-- Step 4: Verification
DO $$
DECLARE
    total_calls INTEGER;
    calls_with_parent INTEGER;
    calls_with_twilio_dir INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_calls FROM call_log;
    SELECT COUNT(*) INTO calls_with_parent FROM call_log WHERE parent_call_sid IS NOT NULL;
    SELECT COUNT(*) INTO calls_with_twilio_dir FROM call_log WHERE twilio_direction IS NOT NULL;
    
    RAISE NOTICE '========================================';
    RAISE NOTICE 'VERIFICATION RESULTS:';
    RAISE NOTICE '  Total calls: %', total_calls;
    RAISE NOTICE '  Calls with parent_call_sid: %', calls_with_parent;
    RAISE NOTICE '  Calls with twilio_direction: %', calls_with_twilio_dir;
    RAISE NOTICE '========================================';
END $$;

-- Commit the transaction
COMMIT;

-- Final verification query (run manually to double-check)
SELECT 
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'public' 
  AND table_name = 'call_log' 
  AND column_name IN ('parent_call_sid', 'twilio_direction')
ORDER BY column_name;
