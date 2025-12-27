# Navigation Arrow Fix for OutboundCallsPage Recent Tab

## Problem Description
Navigation arrows were inconsistent when entering lead details from the "שיחות אחרונות" (Recent Calls) tab in the Outbound Calls page, especially from pages beyond page 1 (e.g., page 2, 3, etc.).

**User Report (Hebrew):**
> יש לי בעיה בui עפ הניווט של החצים! לפעמים הוט עובד ולפעמים הוא לא ! למשל אפ אני נכנס מדף מספר 3 בשיחות אחרונות בדף שיחות יוצאות אז לא נותן לנווט , לפעמים כן נוצן מדף 2 לפעמים לא, שיקלוט מאיפה נכננסתי לליד ושיתן תמיד לנווט! שלא יהיה בעייה שלא מנוןט! וינוןט טוב!

**Translation:**
"I have a problem in the UI with arrow navigation! Sometimes it works and sometimes it doesn't! For example, if I enter from page number 3 in recent conversations to outgoing conversations page, navigation doesn't work. Sometimes it works from page 2, sometimes not. It should detect where I entered from and always allow navigation! There shouldn't be a navigation problem! And it should navigate well!"

## Root Cause
The `leadNavigation.ts` service was using the wrong API endpoint to fetch navigation data:

1. **OutboundCallsPage "recent" tab** displays data from `/api/outbound/recent-calls`
   - Returns: `{ items: [...], total, page, page_size }`
   - Filters: Direction=outbound, plus any user-applied filters

2. **Navigation service** was fetching from `/api/calls`
   - Returns: `{ calls: [...], total }`
   - Different filtering logic, potentially different results

This mismatch caused the navigation arrows to:
- Get a different list of leads than what the user was viewing
- Fail to find the current lead in the navigation list
- Show as disabled even when there were previous/next leads

## Solution
Updated `leadNavigation.ts` to use the **same endpoint** as the page being viewed:

### Changes in `client/src/services/leadNavigation.ts`:

1. **Endpoint Selection (lines 251-262)**
   ```typescript
   case 'recent':
     // Use the same endpoint as OutboundCallsPage
     endpoint = '/api/outbound/recent-calls';
     params.set('page', '1');
     params.set('page_size', '1000');  // Fetch all for navigation
     params.delete('direction');  // Already filtered by endpoint
     params.delete('pageSize');
     break;
   ```

2. **Response Parsing (lines 293-298)**
   ```typescript
   else if (context.from === 'outbound_calls' && context.tab === 'recent') {
     // Use /api/outbound/recent-calls response format
     const items = response?.items || [];
     leadIds = items
       .filter((item: any) => item.lead_id)
       .map((item: any) => item.lead_id);
   }
   ```

## Benefits
1. **Consistency**: Navigation uses the exact same data source as the page
2. **Reliability**: Works from any page number (1, 2, 3, etc.)
3. **Correct Filtering**: Respects all filters applied by the user
4. **Cache Effectiveness**: Cache keys include page number, so each page has its own cached navigation list

## Testing Checklist
- [ ] Navigate to OutboundCallsPage → Recent Calls tab → Page 1
- [ ] Click on a lead → Verify arrows work
- [ ] Navigate to Page 2 → Click on a lead → Verify arrows work
- [ ] Navigate to Page 3 → Click on a lead → Verify arrows work
- [ ] Apply search filter → Navigate to lead → Verify arrows work with filtered results
- [ ] Click up/down arrows → Verify smooth navigation between leads
- [ ] Click back arrow → Verify returns to correct page with filters preserved

## Files Changed
- `client/src/services/leadNavigation.ts` - Fixed endpoint selection and response parsing

## Related Files
- `client/src/pages/calls/OutboundCallsPage.tsx` - Source of navigation context
- `client/src/shared/components/LeadNavigationArrows.tsx` - UI component that uses navigation service
- `server/routes_outbound.py` - Backend endpoint `/api/outbound/recent-calls`
