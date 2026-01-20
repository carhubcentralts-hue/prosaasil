-- ═══════════════════════════════════════════════════════════════════════
-- Migration: Add 'assets' to enabled_pages for all businesses
-- ═══════════════════════════════════════════════════════════════════════
-- This ensures that the Assets Library (מאגר) page is available to all businesses

-- Add 'assets' to enabled_pages for businesses that don't have it yet
-- Using simpler JSONB || operator for better performance
UPDATE business
SET enabled_pages = enabled_pages::jsonb || '["assets"]'::jsonb
WHERE enabled_pages IS NOT NULL
  AND NOT (enabled_pages::jsonb ? 'assets');

-- For businesses with NULL or empty enabled_pages, set to include assets and all default pages
UPDATE business
SET enabled_pages = '["dashboard","crm_leads","crm_customers","calls_inbound","calls_outbound","whatsapp_inbox","whatsapp_broadcast","emails","calendar","statistics","invoices","contracts","assets","settings","users"]'::jsonb
WHERE enabled_pages IS NULL
   OR enabled_pages::text = '[]'
   OR jsonb_array_length(enabled_pages::jsonb) = 0;

-- Verify the update
SELECT 
    id,
    name,
    enabled_pages::jsonb ? 'assets' AS has_assets,
    jsonb_array_length(enabled_pages::jsonb) AS total_pages
FROM business
LIMIT 10;
