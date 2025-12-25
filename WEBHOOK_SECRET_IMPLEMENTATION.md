# WhatsApp Webhook Secret Implementation Summary

## Overview
This feature adds secure webhook secret management for n8n integration, allowing businesses to authenticate webhook requests from external services.

## Changes Made

### 1. Database Changes (Migration 47)
**File:** `server/db_migrate.py`
- Added migration to create `webhook_secret` column in `business` table
- Column type: `VARCHAR(128)` with `UNIQUE` constraint
- Nullable to support businesses without webhooks
- Idempotent migration (safe to run multiple times)

**File:** `server/models_sql.py`
- Added `webhook_secret` field to `Business` model
- Format: `wh_n8n_<48_hex_chars>` (e.g., `wh_n8n_a1b2c3d4...`)

### 2. Backend API Endpoints
**File:** `server/routes_webhook_secret.py` (NEW)

#### GET `/api/business/settings/webhook-secret`
- **Auth:** Requires business admin or system admin
- **Returns:** 
  ```json
  {
    "ok": true,
    "webhook_secret_masked": "wh_n8n_****...b7",
    "has_secret": true
  }
  ```
- **Security:** Never returns full secret (always masked)

#### POST `/api/business/settings/webhook-secret/rotate`
- **Auth:** Requires business admin or system admin
- **Action:** Generates new secret using `secrets.token_hex(24)`
- **Returns:**
  ```json
  {
    "ok": true,
    "webhook_secret": "wh_n8n_<FULL_SECRET>",
    "webhook_secret_masked": "wh_n8n_****...b7"
  }
  ```
- **Security:** Full secret returned ONLY once (one-time reveal)
- **Uniqueness:** Validates secret is unique across all businesses

**File:** `server/app_factory.py`
- Registered `webhook_secret_bp` blueprint

### 3. Frontend UI Changes
**File:** `client/src/pages/settings/SettingsPage.tsx`

#### New State Management
- `webhookSecretMasked`: Stores masked secret for display
- `webhookSecretFull`: Stores full secret (one-time reveal only)
- `hasWebhookSecret`: Boolean flag for UI state
- `showRotateModal`: Controls confirmation modal visibility

#### UI Components Added
1. **Secret Display Section**
   - Shows masked secret or "לא מוגדר" (Not set)
   - Read-only input field with monospace font
   - Copy button (only visible when full secret is available)

2. **Generate/Rotate Button**
   - Text changes based on state: "צור Secret" or "סובב Secret"
   - Opens confirmation modal before action

3. **Confirmation Modal**
   - Title: "צור Webhook Secret?" or "סובב Webhook Secret?"
   - Warning: "פעולה זו תשבור workflows קיימים ב-n8n"
   - Actions: "ביטול" (Cancel) and "צור"/"סובב" (Create/Rotate)

4. **One-Time Reveal Warning**
   - Yellow alert box showing: "⚠️ זוהי התצוגה היחידה של ה-Secret המלא!"
   - Instructs user to copy immediately

5. **Usage Instructions**
   - Step-by-step guide for n8n integration
   - Header name: `X-Webhook-Secret`
   - Location in Settings: Integrations tab → WhatsApp / Webhooks section

### 4. Call Disconnect Fix
**File:** `server/media_ws_ai.py`

#### Problem Fixed
- AI was disconnecting mid-sentence when saying "ביי" or "להתראות"
- Detection happened in `response.audio_transcript.done` event
- Old code immediately executed hangup, cutting off audio

#### Solution Implemented
- Modified `response.audio_transcript.done` handler to ONLY MARK for hangup
- Removed immediate `maybe_execute_hangup()` call
- Hangup execution now happens ONLY in `response.audio.done` event
- `delayed_hangup()` function already waits for:
  1. OpenAI audio queue to drain (max 5 seconds)
  2. Twilio TX queue to drain (max 10 seconds)
  3. Extra 2-second buffer for network latency
- Result: AI completes entire farewell sentence before disconnect

## Security Considerations

### Secret Generation
- Uses Python's `secrets.token_hex(24)` (cryptographically secure)
- 24 bytes = 48 hex characters + `wh_n8n_` prefix
- Total length: 55 characters
- Unique constraint prevents collisions

### Secret Masking
- Format: `wh_n8n_****...b7` (shows first 7 chars + last 2 chars)
- GET endpoint NEVER returns full secret
- Full secret only shown immediately after rotation (in POST response)
- No full secret stored in logs (only masked version)

### Authentication
- Both endpoints require authentication via `@require_api_auth`
- Allowed roles: `system_admin`, `owner`, `admin`, `manager`
- Tenant isolation enforced via business context

## Testing Checklist

### Backend Tests
- [ ] Test GET endpoint without secret (returns has_secret=false)
- [ ] Test GET endpoint with secret (returns masked)
- [ ] Test POST endpoint generates unique secret
- [ ] Test POST endpoint prevents duplicate secrets
- [ ] Test authentication (401 for unauthorized)
- [ ] Test tenant isolation (403 for wrong business)
- [ ] Test migration runs successfully
- [ ] Test migration is idempotent

### Frontend Tests
- [ ] UI shows "לא מוגדר" when no secret exists
- [ ] "צור Secret" button visible when no secret
- [ ] Confirmation modal opens on button click
- [ ] POST request sent on confirmation
- [ ] Full secret displayed after creation
- [ ] Copy button works correctly
- [ ] One-time reveal warning shows
- [ ] After refresh, only masked secret visible
- [ ] "סובב Secret" button visible when secret exists
- [ ] Rotation confirmation shows warning about breaking workflows

### Call Disconnect Tests
- [ ] AI completes "תודה רבה וביי" before disconnect
- [ ] AI completes "להתראות ויום טוב" before disconnect
- [ ] No mid-sentence cut-off on farewells
- [ ] Hangup still works correctly
- [ ] No duplicate hangup attempts
- [ ] User can still interrupt AI before goodbye completes

## n8n Integration Example

```
HTTP Request Node Configuration:
- URL: <webhook_url from settings>
- Method: POST
- Headers:
  * X-Webhook-Secret: wh_n8n_a1b2c3d4e5f6...
- Body: { "your": "data" }
```

## Files Modified
1. `server/models_sql.py` - Added webhook_secret field
2. `server/db_migrate.py` - Added Migration 47
3. `server/routes_webhook_secret.py` - NEW file with API endpoints
4. `server/app_factory.py` - Registered webhook_secret_bp
5. `client/src/pages/settings/SettingsPage.tsx` - Added UI components
6. `server/media_ws_ai.py` - Fixed call disconnect logic

## Migration Command
```bash
python -m server.db_migrate
```

## Deployment Notes
1. Run database migration before deploying
2. No environment variables required
3. Feature is fully self-contained
4. Backward compatible (businesses without webhooks unaffected)
5. No data migration needed (column starts as NULL)
