# Manual Testing Guide for Page Permissions

## Overview
This guide explains how to manually test that page permissions are working correctly.

## Prerequisites
1. Running application with database
2. Admin access to modify business settings
3. Test user account

## Test Scenarios

### Scenario 1: Test Outbound Calls Page Permission

#### Setup
1. Log in as admin/owner
2. Navigate to Admin > Business Management
3. Select a business
4. Open "Page Permissions" section
5. **Disable** the "שיחות יוצאות" (Outbound Calls) page
6. Save changes

#### Test 1: Frontend Blocking
1. Log in as a user from that business
2. Try to navigate to `/app/outbound-calls`
3. **Expected Result**: Should be redirected to `/app/forbidden`
4. Should see a "Access Denied" message

#### Test 2: Backend Blocking
1. While still logged in, open browser DevTools (F12)
2. Go to Console tab
3. Run this command:
```javascript
fetch('/api/outbound_calls/templates', {
  credentials: 'include'
}).then(r => r.json()).then(console.log)
```
4. **Expected Result**: Should receive a 403 Forbidden response with error:
```json
{
  "error": "forbidden",
  "reason": "page_not_enabled",
  "message": "This page is not enabled for your business"
}
```

#### Cleanup
1. Re-enable the "שיחות יוצאות" page
2. Save changes
3. Verify user can now access the page

### Scenario 2: Test Multiple Pages

#### Setup
1. Disable multiple pages:
   - שיחות יוצאות (Outbound Calls)
   - לוח שנה (Calendar)
   - סטטיסטיקות (Statistics)
2. Save changes

#### Test
1. Try to access each disabled page
2. **Expected**: All should redirect to /app/forbidden
3. Try to access enabled pages
4. **Expected**: All should work normally

### Scenario 3: Role + Page Permissions

#### Test
1. Enable "שיחות יוצאות" page for business
2. Log in as an 'agent' role user
3. Try to access outbound calls
4. **Expected**: Should work (both role and page permissions allow it)

## Verification Checklist

- [ ] Backend routes have @require_page_access decorators
  - Check: `grep -c "@require_page_access" server/routes_outbound.py` should show a positive number (18 as of this implementation)
  - Verify multiple route files have decorators applied
  
- [ ] Frontend routes use PageGuard
  - Check: `grep -c "PageGuard" client/src/app/routes.tsx` should show a positive number (27+ as of this implementation)
  - Verify routes wrap components with PageGuard

- [ ] Disabled pages redirect to /app/forbidden
  
- [ ] API calls to disabled pages return 403 Forbidden

- [ ] Enabled pages work normally

- [ ] Role permissions still work (RoleGuard)

## Expected Behavior Summary

**When a page is DISABLED in business.enabled_pages:**
- ❌ Frontend: Redirect to /app/forbidden
- ❌ Backend: Return 403 Forbidden for all API calls
- ✅ Navigation menu should hide the page link (if properly integrated)

**When a page is ENABLED:**
- ✅ Frontend: Page loads normally (if user has required role)
- ✅ Backend: API calls work normally (if user has required role)
- ✅ RoleGuard still enforces role requirements

## Common Issues

### Issue: Page loads despite being disabled
**Cause**: PageGuard not applied to route
**Fix**: Check that route has `<PageGuard pageKey="...">` wrapper

### Issue: API returns 500 instead of 403
**Cause**: Decorator not applied or wrong page key
**Fix**: Check @require_page_access decorator and page key spelling

### Issue: System admin can't access business pages
**Cause**: Tenant context not set
**Fix**: System admin must select a business first
