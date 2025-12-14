-- ========================================
-- PRODUCTION FIX: Add last_call_direction Column
-- ========================================
-- This script adds the missing last_call_direction column to the leads table
-- and backfills it from the call_log table.
-- 
-- Usage:
--   psql $DATABASE_URL -f add_last_call_direction.sql
-- 
-- Or via docker:
--   docker exec -i <postgres-container> psql -U user -d dbname < add_last_call_direction.sql
-- ========================================

-- Start transaction for safety
BEGIN;

-- Step 1: Add the column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' 
          AND table_name = 'leads' 
          AND column_name = 'last_call_direction'
    ) THEN
        ALTER TABLE public.leads 
        ADD COLUMN last_call_direction VARCHAR(16);
        
        RAISE NOTICE 'Added column: leads.last_call_direction';
    ELSE
        RAISE NOTICE 'Column already exists: leads.last_call_direction';
    END IF;
END $$;

-- Step 2: Create index for performance
CREATE INDEX IF NOT EXISTS idx_leads_last_call_direction 
ON public.leads (last_call_direction);

-- Step 3: Backfill from call_log table
-- Only update leads that don't have a direction set (NULL or empty)
-- Use the FIRST call's direction (earliest created_at), not the latest
DO $$
DECLARE
    rows_updated INTEGER;
BEGIN
    WITH first_calls AS (
        SELECT DISTINCT ON (cl.lead_id) 
            cl.lead_id,
            cl.direction,
            cl.created_at
        FROM call_log cl
        WHERE cl.lead_id IS NOT NULL 
          AND cl.direction IS NOT NULL
          AND cl.direction IN ('inbound', 'outbound')
        ORDER BY cl.lead_id, cl.created_at ASC  -- ASC = first call
    )
    UPDATE leads l
    SET last_call_direction = fc.direction
    FROM first_calls fc
    WHERE l.id = fc.lead_id
      AND (l.last_call_direction IS NULL OR l.last_call_direction = '');
    
    GET DIAGNOSTICS rows_updated = ROW_COUNT;
    RAISE NOTICE 'Backfilled last_call_direction for % leads', rows_updated;
END $$;

-- Step 4: Verification
DO $$
DECLARE
    total_leads INTEGER;
    leads_with_direction INTEGER;
    inbound_count INTEGER;
    outbound_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_leads FROM leads;
    SELECT COUNT(*) INTO leads_with_direction FROM leads WHERE last_call_direction IS NOT NULL;
    SELECT COUNT(*) INTO inbound_count FROM leads WHERE last_call_direction = 'inbound';
    SELECT COUNT(*) INTO outbound_count FROM leads WHERE last_call_direction = 'outbound';
    
    RAISE NOTICE '========================================';
    RAISE NOTICE 'VERIFICATION RESULTS:';
    RAISE NOTICE '  Total leads: %', total_leads;
    RAISE NOTICE '  Leads with direction: %', leads_with_direction;
    RAISE NOTICE '  Inbound leads: %', inbound_count;
    RAISE NOTICE '  Outbound leads: %', outbound_count;
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
  AND table_name = 'leads' 
  AND column_name = 'last_call_direction';
