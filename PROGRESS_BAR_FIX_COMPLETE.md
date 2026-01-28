# Fix: Stuck Progress Bars - Complete Solution

## 🎯 Problem

Progress bars were getting "stuck" and showing different states between different businesses, even persisting after deployments. This occurred because:

1. **Frontend cached progress in localStorage** - Each browser stored its own progress state
2. **No stale run detection** - Backend didn't mark old/crashed runs as failed
3. **Workers could crash** - Leaving runs in "running" state forever
4. **Each business saw different UI** - Due to different browser caches

## ✅ Solution Implemented

### 1. Frontend: Removed Progress Caching

**File:** `client/src/hooks/useLongTaskPersistence.ts`

**Change:** localStorage now ONLY stores the taskId reference, NOT the progress/status data.

**Before:**
```typescript
interface TaskState {
  taskId: number;
  taskType: string;
  status: string;  // ❌ Cached in localStorage
  timestamp: number;
}
```

**After:**
```typescript
interface TaskState {
  taskId: number;
  taskType: string;
  // ✅ NO status field - always fetch from server
  timestamp: number;
}
```

**Why:** This ensures progress is ALWAYS fetched fresh from the server, preventing stale cached data.

---

### 2. Frontend: Added Heartbeat Staleness Detection

**File:** `client/src/shared/components/ui/LongTaskStatusCard.tsx`

**Change:** Component now checks heartbeat age and shows warning for stuck runs.

```typescript
// Detect stale runs (no update for 5+ minutes)
const STALE_THRESHOLD_MS = 5 * 60 * 1000;
const isStale = () => {
  if (['completed', 'failed', 'cancelled'].includes(status)) return false;
  const timestamp = heartbeatAt || updatedAt;
  if (!timestamp) return false;
  const age = Date.now() - new Date(timestamp).getTime();
  return age > STALE_THRESHOLD_MS;
};
```

**UI Change:** Shows warning badge and message in Hebrew:
- "תקוע - אין עדכון" (Stuck - No update)
- "המשימה לא התעדכנה מזה 5 דקות" (Task hasn't updated for 5 minutes)

---

### 3. Backend: Auto-Mark Stale Runs as Failed

**Files:** 
- `server/routes_receipts.py` - Receipt sync runs
- `server/routes_whatsapp.py` - Broadcast runs

**Change:** Status endpoints now automatically detect and mark stale runs as failed.

```python
# Receipt Sync - routes_receipts.py
STALE_THRESHOLD_SECONDS = 5 * 60  # 5 minutes

if sync_run.status == 'running':
    seconds_since_heartbeat = int((now - last_activity).total_seconds())
    
    if seconds_since_heartbeat > STALE_THRESHOLD_SECONDS:
        is_stale = True
        logger.warning(f"⚠️ STALE RUN DETECTED: sync_run_id={sync_run.id}")
        
        # Auto-mark as failed
        sync_run.status = 'failed'
        sync_run.finished_at = now
        sync_run.error_message = f'Run marked as failed due to no heartbeat for {seconds_since_heartbeat}s'
        db.session.commit()
```

**Why:** This prevents stuck progress bars by automatically cleaning up crashed/abandoned runs.

---

### 4. Backend: Admin Reset Endpoint

**File:** `server/routes_admin.py`

**Endpoint:** `POST /api/admin/business/<business_id>/reset-progress`

**Purpose:** Allows admins to manually reset all stuck progress for a business.

**What it does:**
1. Marks all running `ReceiptSyncRun` as failed
2. Marks all running `WhatsAppBroadcast` as failed
3. Marks all running `RecordingRun` as failed

**Usage:**
```bash
curl -X POST /api/admin/business/123/reset-progress \
  -H "Authorization: Bearer <token>"
```

**Response:**
```json
{
  "success": true,
  "message": "Successfully reset 3 stuck runs",
  "reset_count": 3
}
```

---

### 5. Build: Verified Cache Busting

**File:** `client/vite.config.js`

**Status:** ✅ Already configured correctly
- Vite automatically adds content hashes to built files
- Example: `app.a1b2c3d4.js`, `chunk.e5f6g7h8.js`

**File:** `docker/nginx/frontend-static.conf`

**Status:** ✅ Already configured correctly

```nginx
# Cache static assets with hash (1 year)
location /assets {
    expires 1y;
    add_header Cache-Control "public,immutable";
}

# Never cache index.html
location = /index.html {
    add_header Cache-Control "no-store, no-cache, must-revalidate" always;
}
```

**Why:** This ensures users always get the latest code after deployment.

---

## 🧪 Testing

All tests pass:
```bash
$ python test_progress_bar_fixes.py
✅ localStorage caching removed from useLongTaskPersistence
✅ LongTaskStatusCard has heartbeat staleness detection
✅ Receipt sync routes auto-mark stale runs as failed
✅ Broadcast routes auto-mark stale broadcasts as failed
✅ Admin reset endpoint exists and handles all run types
✅ Nginx cache headers properly configured
```

---

## 📋 Deployment Checklist

- [x] Frontend changes committed
- [x] Backend changes committed
- [x] Tests written and passing
- [x] No breaking changes to API
- [x] Backward compatible (old cached data ignored gracefully)
- [x] Admin endpoint requires proper authentication
- [x] Logging added for debugging

---

## 🔍 How to Verify After Deployment

### Test 1: Cross-Business Consistency
1. Open business A in Chrome
2. Open business B in Firefox
3. Start a broadcast in business A
4. Verify business B does NOT see business A's progress
5. Refresh both browsers - progress should be identical

### Test 2: Stale Run Cleanup
1. Simulate a stuck run (stop worker mid-task)
2. Wait 5 minutes
3. Refresh the UI
4. Progress bar should automatically disappear or show as failed

### Test 3: Fresh Progress After Deploy
1. Deploy new version
2. Clear browser cache
3. Check progress bars
4. All should show fresh data from server (no old cached data)

---

## 🚨 Troubleshooting

### Problem: Progress still stuck after 5 minutes
**Solution:** Use admin reset endpoint:
```bash
POST /api/admin/business/<id>/reset-progress
```

### Problem: Different progress between users
**Cause:** User has very old browser cache
**Solution:** Hard refresh (Ctrl+Shift+R) or clear cache

### Problem: Progress disappears immediately
**Cause:** Run is legitimately stale (worker crashed)
**Solution:** Check worker logs and restart the task

---

## 📊 Acceptance Criteria - All Met ✅

1. ✅ Progress bar always derived from server, not localStorage
2. ✅ Progress bar doesn't get stuck due to old runs/jobs
3. ✅ Progress bar identical between businesses
4. ✅ Progress bar not dependent on browser/Cloudflare cache
5. ✅ Stale runs automatically detected and marked as failed
6. ✅ Admin can manually reset stuck progress
7. ✅ UI shows warning when run is stale
8. ✅ Build uses hashed assets for proper cache busting

---

## 🎓 Key Architectural Changes

### Before:
```
User Browser → localStorage (cached progress) → UI
                     ↓
                 Server (unused)
```

### After:
```
User Browser → Server (always fresh) → UI
                     ↑
            Stale detection (5min)
```

**Result:** Single source of truth (server), automatic cleanup, consistent UX.
