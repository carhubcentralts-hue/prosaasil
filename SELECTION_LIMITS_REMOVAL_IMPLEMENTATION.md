# Selection Limits Removal & Status Filtering Implementation

## Summary of Changes

This implementation removes the 3-lead selection limit and adds comprehensive status filtering support across all outbound call views.

## Changes Made

### 1. Backend API Changes (server/routes_outbound.py)

#### Removed 3-Lead Selection Limit
- **Line 222-223**: Removed hard-coded validation that rejected selections > 3 leads
- **Impact**: API now accepts unlimited lead selections
- **Auto-scaling**: Selections > 3 automatically use bulk queue mode with concurrency control

```python
# OLD CODE (REMOVED):
if len(lead_ids) > 3:
    return jsonify({"error": "ניתן לבחור עד שלושה לידים לשיחות יוצאות במקביל"}), 400

# NEW CODE:
# ✅ REMOVED: 3-lead limit restriction. Now supports unlimited selections.
# If more than 3 leads, the system automatically uses bulk queue mode.
```

#### Added Status Filtering to Import Leads API
- **Function**: `get_imported_leads()` (line 923+)
- **Added parameter**: `statuses[]` query parameter support
- **Implementation**: Multi-status filtering using SQLAlchemy `.in_()` clause
- **Example usage**: `GET /api/outbound/import-leads?statuses[]=new&statuses[]=contacted`

```python
# NEW CODE ADDED:
statuses_filter = request.args.getlist('statuses[]')  # ✅ Multi-status filter

# ✅ Status filter: Support multi-status filtering
if statuses_filter:
    query = query.filter(Lead.status.in_(statuses_filter))
```

### 2. Frontend Changes (client/src/pages/calls/OutboundCallsPage.tsx)

#### Updated Import Leads Query with Status Filter
- **Line 238-256**: Enhanced query to include status filtering
- **Query key**: Now includes `selectedStatuses` for proper cache invalidation
- **Implementation**: Appends `statuses[]` params to API request

```typescript
// NEW CODE:
const { data: importedLeadsData, isLoading: importedLoading, refetch: refetchImported } = useQuery<ImportedLeadsResponse>({
  queryKey: ['/api/outbound/import-leads', currentPage, importedSearchQuery, selectedStatuses],
  queryFn: async () => {
    const params = new URLSearchParams({
      page: String(currentPage),
      page_size: String(pageSize),
    });
    
    if (importedSearchQuery) {
      params.append('search', importedSearchQuery);
    }

    // ✅ Add multi-status filter for imported leads
    if (selectedStatuses.length > 0) {
      selectedStatuses.forEach(status => {
        params.append('statuses[]', status);
      });
    }

    return await http.get(`/api/outbound/import-leads?${params.toString()}`);
  },
  enabled: activeTab === 'imported',
  retry: 1,
});
```

### 3. Existing Features Verified

#### Selection State Management
- **System leads**: Uses `selectedLeads` Set
- **Imported leads**: Uses `selectedImportedLeads` Set
- **Separation**: Each tab maintains independent selection state
- **No limits**: Sets can grow to any size

#### Status Editing
- **Kanban View**: Drag-and-drop status changes (already implemented)
- **Imported Table View**: Inline status dropdown (already implemented)
- **API Endpoint**: `PATCH /api/leads/{id}/status` (already implemented)
- **Optimistic Updates**: UI updates immediately, with rollback on error

#### Status Source of Truth
- **API**: `/api/lead-statuses` provides all available statuses
- **UI Components**: All use statuses from API, not hardcoded
- **Consistency**: Colors, labels, and available options are uniform

## Testing

### Automated Tests
Created `test_selection_limits_removal.py` with three test suites:

1. **Selection Limit Tests**: Verify API accepts 1, 3, 10, 50, 100, 500 leads
2. **Status Filtering Tests**: Verify proper URL parameter construction
3. **State Management Tests**: Verify independent selection state per tab

**Results**: ✅ All tests passing

### Manual Testing Checklist

#### Task 1: Unlimited Selection
- [ ] Open Outbound Calls page → System tab
- [ ] Switch to Kanban view
- [ ] Click "Select All" in a column with 100+ leads
- [ ] Verify: All leads in column are selected (no 3-lead limit)
- [ ] Click "Start Calls" button
- [ ] Verify: Bulk queue mode activates for large selections

#### Task 2: Status Filtering in Import List
- [ ] Open Outbound Calls page → Import List tab
- [ ] Use status filter dropdown to select "new"
- [ ] Verify: Only leads with "new" status are shown
- [ ] Add "contacted" to filter (multi-select)
- [ ] Verify: Leads with either "new" OR "contacted" status shown
- [ ] Clear filter
- [ ] Verify: All leads shown again

#### Task 3: Status Editing
- [ ] Import List tab → Table view
- [ ] Click status dropdown for any lead
- [ ] Change status to "contacted"
- [ ] Verify: Status updates immediately (optimistic update)
- [ ] Refresh page
- [ ] Verify: Status change persisted
- [ ] Switch to Kanban view
- [ ] Drag a lead to different status column
- [ ] Verify: Status updates via drag-and-drop

#### Task 4: Unified Status Source
- [ ] Check System tab → Kanban view → Status columns match API
- [ ] Check Active tab → Kanban view → Same statuses
- [ ] Check Import tab → Status filter dropdown → Same statuses
- [ ] Check Import tab → Table view → Status dropdown → Same statuses
- [ ] Verify: All show same statuses with same labels/colors

## Architecture Notes

### Selection Scalability
- **Frontend**: Uses JavaScript `Set` for O(1) lookups and additions
- **Backend**: No artificial limits on array size
- **Bulk Mode**: Automatically engages for >3 selections
  - Creates `OutboundCallRun` with jobs queue
  - Respects concurrency limits (default: 3 simultaneous calls)
  - Provides progress tracking API

### Status Filtering Design
- **Multi-status support**: Users can filter by multiple statuses simultaneously
- **Query optimization**: Uses SQL `IN` clause for efficient filtering
- **Client-side caching**: React Query caches results by status filter combination
- **URL construction**: Follows standard array parameter format (`statuses[]=value`)

### Data Flow

```
┌─────────────────┐
│  User Action    │
│ (Select leads)  │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Frontend State  │
│  (Set<number>)  │
└────────┬────────┘
         │
         v
┌─────────────────┐
│  Start Calls    │
│  Array.from()   │
└────────┬────────┘
         │
         v
┌─────────────────┐      ┌──────────────┐
│ POST /api/      │─────>│ If > 3 leads │
│ outbound_calls/ │      │ Use bulk     │
│ start           │      │ queue mode   │
└─────────────────┘      └──────────────┘
```

## Migration Notes

### For Users
- No migration needed
- Existing selections work as before
- New unlimited selection feature available immediately
- Status filtering available in Import List tab

### For Developers
- No database migrations required
- No environment variable changes
- Frontend build required to deploy new code
- Backend restart required to apply API changes

## Performance Considerations

1. **Large selections**: Bulk queue mode prevents overwhelming Twilio API
2. **Status filtering**: Indexed queries on `status` column (verify index exists)
3. **Frontend rendering**: Table view limits display to 50 for performance
4. **Kanban view**: Renders all leads (consider virtualization for 1000+ leads)

## Future Enhancements

1. **Pagination for Kanban**: Add virtual scrolling for very large columns
2. **Bulk status updates**: Allow changing status of multiple selected leads
3. **Filter persistence**: Save status filters in localStorage
4. **Status colors**: Make customizable per business
5. **Advanced filters**: Combine status with date ranges, sources, etc.

## Related Files

### Backend
- `server/routes_outbound.py` - Main API routes
- `server/models_sql.py` - Database models (Lead, OutboundCallRun, etc.)
- `server/routes_leads.py` - Status update endpoint

### Frontend
- `client/src/pages/calls/OutboundCallsPage.tsx` - Main component
- `client/src/pages/calls/components/OutboundKanbanView.tsx` - Kanban layout
- `client/src/pages/calls/components/OutboundKanbanColumn.tsx` - Column with select all
- `client/src/pages/calls/components/OutboundLeadCard.tsx` - Individual lead card
- `client/src/shared/components/ui/MultiStatusSelect.tsx` - Status filter UI

### Tests
- `test_selection_limits_removal.py` - Automated test suite

## Troubleshooting

### Issue: "Select All" only selects visible leads
**Cause**: Looking at wrong implementation (table view has display limit)
**Solution**: Use Kanban view for true "select all" functionality

### Issue: Status filter not working in System/Active tabs
**Cause**: Status filter was specifically added for Import List tab in this PR
**Solution**: System/Active tabs already had status filtering - verify it's enabled

### Issue: Can't select more than 3 leads
**Cause**: Old code still cached or server not restarted
**Solution**: 
1. Clear browser cache
2. Hard refresh (Ctrl+Shift+R)
3. Restart backend server
4. Verify API change deployed

### Issue: Status changes don't persist
**Cause**: API endpoint not responding or CORS issue
**Solution**:
1. Check browser console for errors
2. Verify `PATCH /api/leads/{id}/status` endpoint accessible
3. Check authentication token valid

## Conclusion

This implementation successfully removes artificial selection limits and adds comprehensive status filtering, providing a more flexible and powerful outbound calling system. All changes are backward compatible and require no data migration.
