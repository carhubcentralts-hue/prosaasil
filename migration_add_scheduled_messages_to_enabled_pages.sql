-- Migration: Add 'scheduled_messages' to enabled_pages for existing businesses
-- This ensures all businesses that have WhatsApp enabled also get access to scheduled messages

-- Add 'scheduled_messages' to all businesses that have 'whatsapp_broadcast' enabled
-- (if they have broadcast, they should also have scheduled messages)
UPDATE business
SET enabled_pages = (
    SELECT json_agg(DISTINCT elem)
    FROM (
        SELECT jsonb_array_elements_text(COALESCE(enabled_pages::jsonb, '[]'::jsonb)) AS elem
        UNION
        SELECT 'scheduled_messages'
    ) combined
)::json
WHERE enabled_pages IS NOT NULL
  AND enabled_pages::text LIKE '%whatsapp_broadcast%'
  AND enabled_pages::text NOT LIKE '%scheduled_messages%';

-- Verify the update
SELECT 
    id,
    name,
    enabled_pages
FROM business
WHERE enabled_pages::text LIKE '%whatsapp_broadcast%'
LIMIT 10;

-- Count businesses updated
SELECT 
    COUNT(*) as businesses_with_scheduled_messages
FROM business
WHERE enabled_pages::text LIKE '%scheduled_messages%';

-- Success message
SELECT '✅ Migration complete: scheduled_messages added to enabled_pages for WhatsApp-enabled businesses' AS status;
