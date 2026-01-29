# Migration Guide: Add Scheduled Messages Page

## Overview
This migration adds the `scheduled_messages` page to the page registry and enables it for existing businesses.

## Problem
The "תזמון הודעות WhatsApp" (WhatsApp Message Scheduling) page was implemented but:
- ❌ Not registered in `page_registry.py`
- ❌ Not visible in sidebar (missing pageKey)
- ❌ Not manageable through page permissions system
- ❌ Not protected by PageGuard

## Solution

### 1. Code Changes (Already Applied)
- ✅ Added `scheduled_messages` to `server/security/page_registry.py`
- ✅ Added PageGuard to route in `client/src/app/routes.tsx`
- ✅ Added `@require_page_access('scheduled_messages')` to all API endpoints in `server/routes_scheduled_messages.py`
- ✅ Page is already in sidebar with `pageKey: 'scheduled_messages'` in `MainLayout.tsx`

### 2. Database Migration (Run on Production)

**File:** `migration_add_scheduled_messages_to_enabled_pages.sql`

**What it does:**
- Adds `scheduled_messages` to `enabled_pages` for all businesses that have `whatsapp_broadcast` enabled
- New businesses automatically get it via DEFAULT_ENABLED_PAGES

**Run this on production:**
```bash
psql -d your_database -f migration_add_scheduled_messages_to_enabled_pages.sql
```

Or manually in your database admin:
```sql
UPDATE business
SET enabled_pages = enabled_pages::jsonb || '["scheduled_messages"]'::jsonb
WHERE enabled_pages IS NOT NULL
  AND enabled_pages::jsonb ? 'whatsapp_broadcast'
  AND NOT (enabled_pages::jsonb ? 'scheduled_messages');
```

### 3. Verification

After deploying:

1. **Check Page Registry:**
   ```python
   from server.security.page_registry import PAGE_REGISTRY
   print('scheduled_messages' in PAGE_REGISTRY)  # Should be True
   ```

2. **Check Sidebar:**
   - Login as admin
   - Verify "תזמון הודעות" appears in sidebar under WhatsApp section

3. **Check Permissions Manager:**
   - Login as admin
   - Go to Settings → Manage Page Permissions
   - Verify "תזמון הודעות WhatsApp" appears in the list

4. **Test Access Control:**
   - Create a user with only basic permissions
   - Verify they cannot access the scheduled messages page
   - Enable the page for their business
   - Verify they can now access it

## Rollback
If needed, remove from enabled_pages:
```sql
UPDATE business
SET enabled_pages = (
    SELECT json_agg(elem)
    FROM jsonb_array_elements_text(enabled_pages::jsonb) elem
    WHERE elem != 'scheduled_messages'
)::json
WHERE enabled_pages::text LIKE '%scheduled_messages%';
```

## Notes
- The page requires `admin` role minimum (owner and system_admin also have access)
- The page is in the "whatsapp" category
- API endpoints are protected with `@require_page_access('scheduled_messages')`
