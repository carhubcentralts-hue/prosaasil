# Testing Guide: Leads/Calls UX Improvements

## Overview
This guide will help you manually test all the new features and improvements made to the Leads and Calls management system.

## Pre-Testing Setup

### 1. Ensure System is Running
```bash
# Start the backend server
python run_server.py

# Start the frontend (in another terminal)
cd client
npm install  # if not already done
npm run dev
```

### 2. Login
- Access the system at the frontend URL
- Login with valid credentials (owner, admin, or agent role)

## Test Scenarios

### Scenario 1: Inbound Calls Page

#### Navigate to Page
1. Click on "שיחות נכנסות" in the sidebar menu
2. **Expected**: Should see a page with green phone icon theme

#### Verify Lead Display
3. **Expected**: Only leads with inbound calls should be displayed
4. Each lead card should show:
   - Lead name (or "לקוח אלמוני" if no name)
   - Phone number
   - Status badge
   - Summary text (if available)
   - Relative timestamp (e.g., "לפני 2 שעות")

#### Test Search
5. Type a phone number or name in the search box
6. **Expected**: List filters in real-time
7. Clear search
8. **Expected**: All inbound leads appear again

#### Test Navigation
9. Click on any lead card
10. **Expected**: Navigate to `/app/leads/:id` (lead detail page)
11. Press back button
12. **Expected**: Return to inbound calls page

#### Test Pagination
13. If there are more than 25 leads:
    - **Expected**: See pagination controls at bottom
    - Click "הבא" (next)
    - **Expected**: Shows next page of leads
    - Click "הקודם" (previous)
    - **Expected**: Returns to first page

---

### Scenario 2: Leads Page Filters

#### Navigate to Leads Page
1. Click on "לידים" in the sidebar
2. **Expected**: See the leads page with multiple filters

#### Test Direction Filter
3. Locate the "מקור שיחה" dropdown (should show "כל השיחות" by default)
4. Select "נכנסות"
5. **Expected**: Only leads with `last_call_direction=inbound` displayed
6. Select "יוצאות"
7. **Expected**: Only leads with `last_call_direction=outbound` displayed
8. Select "כל השיחות"
9. **Expected**: All leads displayed again

#### Test Outbound List Filter
10. If you have imported any outbound lead lists:
    - Locate the "רשימת יבוא" dropdown
    - **Expected**: See list of imported lists
    - Select a specific list
    - **Expected**: Only leads from that list are shown

#### Test Combined Filters
11. Set direction to "יוצאות"
12. Select a specific outbound list
13. Select a specific status
14. **Expected**: Leads matching ALL criteria are shown
15. Clear all filters
16. **Expected**: All leads appear

#### Test Search with Filters
17. Apply a direction filter
18. Type in the search box
19. **Expected**: Search works within filtered results

---

### Scenario 3: Outbound Calls Page - Kanban View

#### Navigate to Page
1. Click on "שיחות יוצאות" in sidebar
2. Ensure you're on the "לידים קיימים" tab
3. Switch to Kanban view (if not default)

#### Test Lead Navigation
4. Click on any lead card in the Kanban board
5. **Expected**: Navigate to lead detail page
6. Press back
7. **Expected**: Return to outbound calls page

#### Test Drag and Drop
8. Drag a lead card to a different status column
9. **Expected**: Lead status updates
10. Click on the moved lead
11. **Expected**: Detail page shows the updated status

#### Test Selection
12. Click the checkbox on a lead card
13. **Expected**: Card gets blue border/highlight
14. Click another lead card's checkbox
15. **Expected**: Both cards are selected
16. Try to select a 4th card (max is 3)
17. **Expected**: Cannot select more than 3

---

### Scenario 4: Outbound Calls Page - Imported Leads

#### Navigate to Imported Leads
1. Click on "רשימת ייבוא לשיחות יוצאות" tab
2. **Expected**: See table of imported leads (if any)

#### Test Row Click Navigation
3. Click anywhere on a lead row (not on checkbox or delete button)
4. **Expected**: Navigate to lead detail page
5. Press back

#### Test Checkbox Independence
6. Click on a checkbox
7. **Expected**: Checkbox checks but doesn't navigate
8. Click on row area (not checkbox)
9. **Expected**: Navigate to lead detail

#### Test Select All
10. Click the "Select All" checkbox in table header
11. **Expected**: Up to 3 leads are selected (or available slots)
12. Click "Select All" again
13. **Expected**: All selections are cleared

#### Test Bulk Delete
14. Select 2-3 leads using checkboxes
15. Click "מחק נבחרים" button
16. **Expected**: Confirmation or immediate deletion
17. **Expected**: Selected leads are removed from list

---

### Scenario 5: Data Flow & Auto-Update

#### Test Inbound Call Flow
1. Make or simulate an inbound call to the system
2. After call completes, go to "שיחות נכנסות"
3. **Expected**: New lead appears with inbound direction

#### Test Outbound Call Flow
4. From "שיחות יוצאות", start an outbound call to a lead
5. After call completes, go to "לידים" page
6. Filter by "יוצאות"
7. **Expected**: The called lead appears in results

#### Test Filter Persistence
8. Apply direction filter on Leads page
9. Navigate to a lead detail page
10. Press back
11. **Expected**: Filter is still applied (or cleared - check implementation)

---

## Expected Behaviors Summary

### Inbound Calls Page
- ✅ Shows only inbound leads
- ✅ Lead cards are clickable → navigate to detail
- ✅ Search works
- ✅ Pagination works (if needed)
- ✅ Shows "אין שיחות נכנסות" if no inbound leads

### Leads Page
- ✅ Direction filter works (all/inbound/outbound)
- ✅ Outbound list filter works
- ✅ Filters combine properly
- ✅ Search works with filters
- ✅ All existing functionality preserved

### Outbound Calls Page
- ✅ Kanban cards navigate to lead detail
- ✅ Table rows navigate to lead detail
- ✅ Checkboxes work independently
- ✅ Select All respects max limit (3)
- ✅ Drag-and-drop still works
- ✅ Status updates reflect immediately

## Troubleshooting

### "אין שיחות נכנסות" shows but there are calls
- Check if calls have been processed and saved to database
- Verify `last_call_direction` field is being populated
- Check if leads exist at all (might need to process recordings)

### Filters not working
- Clear browser cache
- Check browser console for errors
- Verify API endpoints return correct data

### Navigation not working
- Check browser console for routing errors
- Verify lead IDs are valid
- Ensure lead detail route is registered

### Select All selects wrong number
- Verify "available slots" calculation
- Check if there are active calls limiting slots
- Should max out at 3 per business limits

## Success Criteria

All tests should pass with:
- ✅ No console errors
- ✅ Smooth navigation between pages
- ✅ Filters working correctly
- ✅ Data displaying accurately
- ✅ Clicks navigating as expected
- ✅ UI responding to user actions

## Reporting Issues

If you find any issues during testing:

1. **Note the exact steps** to reproduce
2. **Check browser console** for errors
3. **Take screenshots** if UI looks wrong
4. **Document expected vs actual** behavior

## Post-Testing

Once all scenarios pass:
- ✅ System is ready for production deployment
- ✅ Documentation is complete
- ✅ All acceptance criteria met
