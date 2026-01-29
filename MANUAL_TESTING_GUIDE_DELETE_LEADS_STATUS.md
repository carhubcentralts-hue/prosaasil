# Manual Testing Guide: Delete Leads Status Polling Fix

## Issue
Previously, when deleting leads in bulk, the UI would show an error toast:
```
שגיאה בבדיקת סטטוס המחיקה. אנא רענן את העמוד.
```
(Error checking deletion status. Please refresh the page.)

This happened even though the worker successfully completed the deletion.

## Root Cause
The UI was polling `/api/jobs/${jobId}` but this endpoint didn't exist, causing 404 errors.

## Fix
Added the missing `/api/jobs/<job_id>` endpoint that always returns 200 OK with valid JSON.

## How to Test

### Prerequisites
1. Have access to the application UI
2. Have at least 2-3 test leads in the system
3. Open browser DevTools (F12) → Network tab

### Test Steps

#### Test 1: Normal Delete Operation
1. Go to the Leads page
2. Select 2-3 leads using checkboxes
3. Click the "Delete" button
4. **Watch the Network tab**:
   - You should see `POST /api/leads/bulk-delete` → 202 Accepted
   - You should see multiple `GET /api/jobs/<job_id>` requests → 200 OK
   - Check the response body - it should have `"success": true` and `"status": "completed"`
5. **Expected Result**: 
   - ✅ No error toast appears
   - ✅ Success message shows
   - ✅ Leads are deleted
   - ✅ No 404 or 500 errors in Network tab

#### Test 2: Missing Job (Edge Case)
This tests what happens when the job is already deleted/cleaned up:

1. In DevTools Console, run:
   ```javascript
   fetch('/api/jobs/99999', {
     headers: { 'Authorization': 'Bearer ' + localStorage.getItem('token') }
   }).then(r => r.json()).then(console.log)
   ```
2. **Expected Response**:
   ```json
   {
     "success": true,
     "status": "unknown",
     "job_id": 99999,
     "job_type": "unknown",
     "message": "Job not found - may have been completed and cleaned up",
     "total": 0,
     "processed": 0,
     "succeeded": 0,
     "failed_count": 0,
     "percent": 0.0,
     "is_stuck": false
   }
   ```
3. **Expected Result**: 
   - ✅ Returns 200 OK (not 404)
   - ✅ No error in console
   - ✅ Status is "unknown"

#### Test 3: Worker Completes While Polling
1. Select many leads (10+) so deletion takes a few seconds
2. Click Delete and immediately watch the Network tab
3. You should see polling requests with different statuses:
   - `"status": "queued"` → job is waiting
   - `"status": "running"` → worker is processing
   - `"status": "completed"` → worker finished
4. **Expected Result**:
   - ✅ All polling requests return 200 OK
   - ✅ No error toast appears
   - ✅ UI shows progress correctly

### Visual Verification

**Before Fix (OLD BEHAVIOR):**
- ❌ Error toast appears: "שגיאה בבדיקת סטטוס המחיקה"
- ❌ Network tab shows 404 errors for `/api/jobs/<id>`
- ❌ User thinks deletion failed (even though it succeeded)

**After Fix (NEW BEHAVIOR):**
- ✅ No error toast
- ✅ Success message appears
- ✅ Network tab shows 200 OK for all requests
- ✅ UI shows "הושלם" (completed) status

## Troubleshooting

### If you still see errors:

1. **Check the endpoint exists**:
   ```bash
   grep -n "def get_job_status" server/routes_leads.py
   ```
   Should return: `1771:def get_job_status(job_id):`

2. **Check Flask is using the updated code**:
   - Restart the Flask server
   - Clear browser cache
   - Hard refresh (Ctrl+Shift+R)

3. **Check authentication**:
   - Make sure you're logged in
   - Check that the Authorization header is present in the request

4. **Check multi-tenant isolation**:
   - Make sure you have a valid business_id/tenant_id
   - Check that the job belongs to your tenant

## Success Criteria

✅ **The fix is working correctly if:**
1. Deleting leads shows no error toast
2. All `/api/jobs/<id>` requests return 200 OK
3. Worker completion shows success message
4. Even refreshing the page shows correct status

✅ **Acceptance Test Passed:**
```
✓ מפעיל "מחיקת לידים"
✓ הוורקר מסיים Job OK
✓ ה־UI מציג הושלם / נמחק בלי שום טוסט שגיאה
✓ גם אם עושים רענון דף — הסטטוס נשאר תקין
```
