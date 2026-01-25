# Push Notification System Fix - Deployment Guide

## Overview

This fix addresses three critical issues in the push notification system:
1. **410 Gone errors** from expired subscriptions causing repeated failures
2. **Toggle ON/OFF** not persisting (immediately reverting to ON)
3. **"Send test notification"** not providing meaningful error messages

## Changes Summary

### Key Concepts

The fix introduces a separation between:
- `push_enabled`: User's preference (wants notifications) - stored in DB
- `has_active_subscription`: Device capability (browser registered) - stored in DB
- `enabled`: Computed state = `push_enabled AND has_active_subscription`

This ensures:
- User can turn OFF notifications and it stays OFF
- Expired subscriptions (410 Gone) are automatically cleaned up
- Test notifications provide actionable feedback

### Files Changed

**Backend:**
- `migration_add_push_enabled.py` - New migration to add push_enabled field
- `server/models_sql.py` - Added push_enabled to User model
- `server/routes_push.py` - Updated endpoints, added toggle endpoint
- `server/services/push/webpush_sender.py` - Enhanced 410 Gone detection
- `server/services/notifications/dispatcher.py` - Improved logging

**Frontend:**
- `client/src/services/push.ts` - Updated types and added togglePushEnabled()
- `client/src/pages/settings/SettingsPage.tsx` - Fixed toggle behavior and error messages

**Testing:**
- `test_push_notification_fixes.py` - Validation tests

## Deployment Steps

### 1. Database Migration

Run the migration to add the `push_enabled` field to the users table:

```bash
python migration_add_push_enabled.py
```

This will:
- Add `push_enabled BOOLEAN NOT NULL DEFAULT TRUE` to the users table
- Default all existing users to `push_enabled=TRUE` (opt-out model)
- Check if the column already exists (idempotent)

### 2. Backend Deployment

Deploy the updated backend files:
- Restart the Flask/backend server after deploying the code changes
- No additional environment variables needed
- Existing VAPID keys continue to work

### 3. Frontend Deployment

Deploy the updated frontend:
- Build and deploy the updated React frontend
- Clear browser cache if needed
- No localStorage changes required

### 4. Verification

After deployment, verify the fixes:

#### Test 410 Gone Cleanup
1. If you have expired subscriptions, trigger a test notification
2. Check logs for: `[PUSH] 410 Gone -> marking subscription id=X user=Y for removal`
3. Verify subscription is deactivated in database

#### Test Toggle Persistence
1. Open Settings → Notifications tab
2. Toggle push notifications OFF
3. Refresh the page
4. Verify toggle remains OFF (badge shows "לא פעיל")

#### Test Error Messages
1. With toggle OFF, click "שלח התראת בדיקה"
2. Should show: "התראות מבוטלות. אנא הפעל אותן תחילה."
3. Toggle ON without subscribing, click test
4. Should show: "לא נמצאו מכשירים פעילים. אנא אשר התראות בדפדפן."

## API Changes

### GET /api/push/status

**New response fields:**
- `push_enabled` (boolean) - User's preference
- `enabled` (boolean) - Computed: push_enabled AND has_active_subscription

**Backwards compatible fields** (maintained for existing clients):
- `configured`, `subscriptionCount` - same as before

### POST /api/push/toggle (NEW)

**Request:**
```json
{
  "enabled": true
}
```

**Response:**
```json
{
  "success": true,
  "push_enabled": true,
  "active_subscriptions_count": 0,
  "enabled": false,
  "message": "התראות הופעלו"
}
```

### POST /api/push/test

**Enhanced error responses:**
- `"error": "push_disabled"` - User turned off notifications
- `"error": "no_active_subscription"` - No device subscriptions
- `"error": "subscription_expired_need_resubscribe"` - All subscriptions expired (410)

## Monitoring

### Logs to Watch

Look for these log messages in production:

**Normal operation:**
```
[PUSH] Dispatching push to 2 subscription(s) for user 123
[PUSH] Push dispatch complete: 2/2 successful
```

**Expired subscriptions (410 Gone):**
```
[PUSH] WebPush subscription expired/gone (HTTP 410) -> will deactivate
[PUSH] 410 Gone -> marking subscription id=456 user=123 for removal
[PUSH] Push dispatch complete: 1/2 successful, removed_expired=1
```

**User toggling:**
```
Disabled push for user 123 - deactivated subscriptions
Enabled push preference for user 123
```

### Metrics to Track

1. **410 Gone rate**: Track `removed_expired` count in logs
2. **User preferences**: Query `SELECT COUNT(*) FROM users WHERE push_enabled = TRUE`
3. **Active subscriptions**: Query `SELECT COUNT(*) FROM push_subscriptions WHERE is_active = TRUE`

## Rollback Plan

If issues occur:

1. **Database rollback:**
```sql
ALTER TABLE users DROP COLUMN IF EXISTS push_enabled;
```

2. **Code rollback:**
- Revert to previous version
- Restart services
- Old API still works (frontend falls back gracefully)

## Security Considerations

- ✅ CodeQL analysis passed with 0 alerts
- ✅ No new dependencies added
- ✅ User data (push_enabled) is per-user, properly isolated by business_id
- ✅ All endpoints require authentication (@require_api_auth)
- ✅ Input validation on toggle endpoint

## Known Limitations

1. Migration must be run before deploying code (or code will fail for users without push_enabled field)
2. Existing subscriptions with is_active=False won't be automatically cleaned up (manual cleanup if desired)
3. Frontend assumes push.ts and SettingsPage.tsx are deployed together

## Support

If users report issues:

1. **Toggle not persisting**: Check database for push_enabled field, verify migration ran
2. **Test notification failing**: Check logs for specific error code, verify VAPID keys configured
3. **Subscriptions not cleaning up**: Check logs for 410 Gone messages, verify database writes succeed

## Success Criteria

✅ Toggle ON/OFF persists across page refreshes
✅ 410 Gone errors automatically clean up subscriptions
✅ Test notifications show clear, actionable Hebrew error messages
✅ Logs show [PUSH] formatted messages with useful context
✅ No regressions in existing push notification functionality
