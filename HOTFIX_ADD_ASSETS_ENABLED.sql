-- ═══════════════════════════════════════════════════════════════════════
-- Migration: Add 'assets' to enabled_pages for all businesses
-- ═══════════════════════════════════════════════════════════════════════
-- This ensures that the Assets Library (מאגר) page is available to all businesses

-- Add 'assets' to enabled_pages for businesses that don't have it yet
UPDATE business
SET enabled_pages = (
    SELECT COALESCE(
        jsonb_agg(DISTINCT elem ORDER BY elem),
        '[]'::jsonb
    )
    FROM (
        SELECT jsonb_array_elements_text(
            COALESCE(enabled_pages::jsonb, '[]'::jsonb)
        ) AS elem
        UNION
        SELECT 'assets'
    ) pages
)
WHERE enabled_pages IS NOT NULL
  AND NOT (enabled_pages::jsonb ? 'assets');

-- For businesses with NULL or empty enabled_pages, set to include assets and all default pages
UPDATE business
SET enabled_pages = jsonb_build_array(
    'dashboard',
    'crm_leads',
    'crm_customers',
    'calls_inbound',
    'calls_outbound',
    'whatsapp_inbox',
    'whatsapp_broadcast',
    'emails',
    'calendar',
    'statistics',
    'invoices',
    'contracts',
    'assets',
    'settings',
    'users'
)
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
