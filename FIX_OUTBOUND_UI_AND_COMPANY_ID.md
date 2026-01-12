# Fix Outbound UI State Persistence & Add Company ID Field

## Summary

This PR addresses two requirements from the problem statement:

### 1. Fixed Outbound UI State Persistence Bug (Visual Bug) ✅

**Problem:** After deploy/refresh, the outbound UI incorrectly showed "תור פעיל / שיחות נכשלות" even when no active queue existed on the server. This was caused by React Query caching data with a 5-minute `staleTime`.

**Root Cause:** 
- React Query default `staleTime: 5 * 60 * 1000` (5 minutes) in `queryClient.ts`
- Outbound UI queries were using cached data instead of fetching fresh from server
- No cache invalidation on mount or unmount

**Solution:**
- Added `staleTime: 0` and `gcTime: 0` to outbound counts query to force fresh data fetch
- Reset all UI state (`activeRunId`, `queueStatus`, etc.) on component mount
- Invalidate React Query cache before fetching fresh server data
- Clear queries on queue stop and component unmount

**Changes in `/client/src/pages/calls/OutboundCallsPage.tsx`:**
```typescript
// ✅ FIX: Force fresh data, no cache
const { data: counts, ... } = useQuery<CallCounts>({
  queryKey: ['/api/outbound_calls/counts'],
  refetchInterval: 10000,
  retry: 1,
  staleTime: 0,  // ✅ Always fetch fresh
  gcTime: 0,     // ✅ Don't keep in cache
});

// ✅ FIX: Reset UI state on mount, then fetch from server
useEffect(() => {
  // 1. Reset all UI state to initial values
  setActiveRunId(null);
  setQueueStatus(null);
  setShowResults(false);
  setCallResults([]);
  
  // 2. Invalidate cached queries
  queryClient.invalidateQueries({ queryKey: ['/api/outbound_calls/counts'] });
  queryClient.invalidateQueries({ queryKey: ['/api/outbound/bulk/active'] });
  
  // 3. Fetch fresh from server
  checkActiveRun();
}, []);
```

### 2. Added Company ID Field (ח.פ) ✅

**Requirement:** Add Israeli company registration number (ח.פ) field to Business settings.

**Backend Changes:**

1. **Database Migration** (`/server/db_migrate.py`):
   - Added Migration 64 to add `company_id` column to `business` table
   - Column type: `VARCHAR(50)`, nullable

2. **Model Update** (`/server/models_sql.py`):
   ```python
   company_id = db.Column(db.String(50), nullable=True)  # Israeli company registration number (ח.פ)
   ```

3. **API Endpoints** (`/server/routes_business_management.py`):
   - GET `/api/business/current` now returns `company_id`
   - PUT `/api/business/current/settings` accepts and validates `company_id`:
     - Strips non-digit characters
     - Validates length (8-9 digits)
     - Allows clearing the field (set to null)

**Frontend Changes:**

1. **Interface Update** (`/client/src/pages/settings/SettingsPage.tsx`):
   ```typescript
   interface BusinessSettings {
     business_name: string;
     company_id?: string;  // ✅ Israeli company registration number
     phone_number: string;
     // ...
   }
   ```

2. **UI Input Field** (in Business Settings section):
   ```tsx
   <div>
     <label className="block text-sm font-medium text-gray-700 mb-1">
       ח.פ (מספר עוסק)
     </label>
     <input
       type="text"
       value={businessSettings.company_id || ''}
       onChange={(e) => {
         // Clean input - only digits
         const cleaned = e.target.value.replace(/\D/g, '');
         setBusinessSettings({...businessSettings, company_id: cleaned});
       }}
       placeholder="לדוגמה: 515123456"
       className="w-full px-3 py-2 border border-gray-300 rounded-md"
       dir="ltr"
       maxLength={9}
     />
     <p className="mt-1 text-xs text-gray-500">
       מספר ח.פ או ע.מ (8-9 ספרות) - שדה אופציונלי
     </p>
   </div>
   ```

3. **Data Loading & Saving**:
   - Load `company_id` from server on mount
   - Save `company_id` with other business settings
   - Added to `useQuery` and `useEffect` hooks

## Files Changed

1. `/client/src/pages/calls/OutboundCallsPage.tsx` - Fixed UI state persistence
2. `/client/src/pages/settings/SettingsPage.tsx` - Added company_id UI field
3. `/server/db_migrate.py` - Added Migration 64 for company_id column
4. `/server/models_sql.py` - Added company_id to Business model
5. `/server/routes_business_management.py` - Added company_id to API endpoints

## Testing Required

### Automated Testing:
- ✅ Code compiles without TypeScript errors
- ⏳ Run migration: `python -m server.db_migrate`
- ⏳ Verify database schema has `company_id` column

### Manual Testing:

**Test 1: Outbound UI State Reset**
1. Navigate to Outbound Calls page
2. Start a bulk call queue
3. Refresh the page
4. ✅ **Expected:** UI shows clean state, then loads active queue from server
5. ✅ **Expected:** No stale "תור פעיל" indicator if no active queue exists

**Test 2: Company ID Field**
1. Navigate to Settings → פרטי עסק
2. Find "ח.פ (מספר עוסק)" field
3. Enter a valid Israeli company ID (e.g., "515123456")
4. Click Save
5. Refresh the page
6. ✅ **Expected:** Company ID is displayed correctly after refresh
7. Try entering invalid input (letters, special chars)
8. ✅ **Expected:** Only digits are accepted (cleaned automatically)
9. Try entering more than 9 digits
10. ✅ **Expected:** Input limited to 9 characters
11. Clear the field and save
12. ✅ **Expected:** Field can be cleared (saved as null)

### Acceptance Criteria:

**Issue 1 - Outbound UI:**
- [x] Removed any localStorage/persist for outbound UI state
- [x] Removed React Query cache persistence for outbound status  
- [x] Ensured OutboundCallsPage resets all UI state on mount
- [x] Verified all outbound status comes from server only
- ⏳ After refresh, outbound page shows clean UI then fetches from server
- ⏳ After deploy, no "תור פעיל" if no active_run in server

**Issue 2 - Company ID:**
- [x] Added company_id field to Business model
- [x] Created database migration
- [x] Updated GET `/api/business/current` to return company_id
- [x] Updated PUT `/api/business/current/settings` to accept company_id
- [x] Added validation (8-9 digits, digits only)
- [x] Added company_id input field to Settings UI
- [x] Added Hebrew label and placeholder
- ⏳ Can view/edit/save company_id
- ⏳ Company_id persists after refresh

## Deployment Notes

1. **Run database migration** before deploying:
   ```bash
   python -m server.db_migrate
   ```

2. **Verify migration** was successful:
   ```sql
   SELECT column_name, data_type 
   FROM information_schema.columns 
   WHERE table_name = 'business' AND column_name = 'company_id';
   ```

3. **No breaking changes** - All changes are backward compatible:
   - company_id is nullable and optional
   - Frontend gracefully handles missing company_id
   - Outbound UI fixes don't break existing functionality

## Security Considerations

- ✅ Company ID validation on backend (8-9 digits only)
- ✅ Input sanitization (remove non-digits)
- ✅ No sensitive data exposed
- ✅ Proper authorization checks (existing auth middleware)
