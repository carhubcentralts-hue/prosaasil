-- Migration: Add 'scheduled_messages' to enabled_pages for existing businesses
-- This ensures all businesses that have WhatsApp enabled also get access to scheduled messages

-- Add 'scheduled_messages' to all businesses that have 'whatsapp_broadcast' enabled
-- (if they have broadcast, they should also have scheduled messages)
UPDATE business
SET enabled_pages = enabled_pages::jsonb || '["scheduled_messages"]'::jsonb
WHERE enabled_pages IS NOT NULL
  AND enabled_pages::jsonb ? 'whatsapp_broadcast'
  AND NOT (enabled_pages::jsonb ? 'scheduled_messages');

-- Verify the update
SELECT 
    id,
    name,
    enabled_pages
FROM business
WHERE enabled_pages::jsonb ? 'whatsapp_broadcast'
LIMIT 10;

-- Count businesses updated
SELECT 
    COUNT(*) as businesses_with_scheduled_messages
FROM business
WHERE enabled_pages::jsonb ? 'scheduled_messages';

-- Success message
SELECT '✅ Migration complete: scheduled_messages added to enabled_pages for WhatsApp-enabled businesses' AS status;
