# Leads/Calls UX Improvements - Implementation Summary

## Overview
This implementation adds Inbound/Outbound call segmentation and improves the UX for leads and calls management according to the requirements.

## Changes Made

### Backend Changes

#### 1. Database Schema (`server/models_sql.py`)
- **Added Field**: `last_call_direction` (VARCHAR(16), indexed) to `Lead` model
- **Purpose**: Track the direction of the last call for each lead to enable filtering

#### 2. API Updates (`server/routes_leads.py`)
- **Added Filters to `/api/leads`**:
  - `direction` parameter: Filter leads by call direction (inbound/outbound/all)
  - `outbound_list_id` parameter: Filter leads by outbound list
- **Updated Response**: Include `last_call_direction` in API response

#### 3. Call Processing (`server/tasks_recording.py`)
- **Auto-Update Logic**: When a call is saved, the `last_call_direction` field is automatically updated for the associated lead
- **Location**: Line 602 in `save_call_to_db` function

### Frontend Changes

#### 1. Navigation (`client/src/app/layout/MainLayout.tsx`)
- **Menu Update**: Renamed "שיחות" → "שיחות נכנסות"
- **Kept**: "שיחות יוצאות" menu item (already existed)

#### 2. Routing (`client/src/app/routes.tsx`)
- **Updated Route**: `/app/calls` now uses `InboundCallsPage` instead of `CallsPage`
- **Import**: Added lazy loading for `InboundCallsPage`

#### 3. New Page: Inbound Calls (`client/src/pages/calls/InboundCallsPage.tsx`)
- **Purpose**: Lead-centric view of inbound calls (not raw call logs)
- **Features**:
  - Displays leads filtered by `direction=inbound`
  - Shows lead cards with: name, phone, status badge, summary, timestamp
  - Sorted by `last_contact_at` DESC
  - Click on lead card navigates to `/app/leads/:id`
  - Search functionality
  - Pagination (25 leads per page)
- **UI**: Clean card-based interface with green phone icon theme

#### 4. Leads Page Updates (`client/src/pages/Leads/LeadsPage.tsx`)
- **Added Filters**:
  - **Direction Filter**: "כל השיחות | נכנסות | יוצאות"
  - **Outbound List Filter**: Dropdown showing all imported lead lists
- **Filter Logic**: Filters work in combination (direction + outbound_list + status + source + search)
- **Auto-Load**: Outbound lists are fetched on component mount from `/api/outbound/import-lists`

#### 5. Outbound Calls Page Updates (`client/src/pages/calls/OutboundCallsPage.tsx`)
- **Lead Navigation**:
  - Kanban cards are clickable → navigate to `/app/leads/:id`
  - Table view rows are clickable → navigate to `/app/leads/:id`
  - Checkboxes work independently (stop propagation)
- **Select All**:
  - Added "Select All" checkbox in imported leads table header
  - Selects up to max allowed (min of 3 and available slots)
  - Works with pagination
- **UI Consistency**: All lead displays show consistent information

## File Changes Summary

### Backend (Python)
1. `server/models_sql.py` - Added `last_call_direction` field to Lead model
2. `server/routes_leads.py` - Added direction and outbound_list_id filters, updated API response
3. `server/tasks_recording.py` - Auto-update `last_call_direction` when saving calls

### Frontend (TypeScript/React)
1. `client/src/app/layout/MainLayout.tsx` - Menu label update
2. `client/src/app/routes.tsx` - Route update to use InboundCallsPage
3. `client/src/pages/calls/InboundCallsPage.tsx` - **NEW FILE** - Inbound calls page
4. `client/src/pages/Leads/LeadsPage.tsx` - Added direction and outbound list filters
5. `client/src/pages/calls/OutboundCallsPage.tsx` - Navigation and select all improvements

## Testing Checklist

### Inbound Calls Page
- [ ] Navigate to "שיחות נכנסות" in menu
- [ ] Verify only leads with `last_call_direction=inbound` are shown
- [ ] Verify leads are sorted by most recent contact first
- [ ] Click on a lead card → should navigate to lead detail page
- [ ] Search for a lead by name or phone
- [ ] Test pagination if more than 25 leads

### Leads Page Filters
- [ ] Open Leads page
- [ ] Select "נכנסות" from direction filter → should show only inbound leads
- [ ] Select "יוצאות" from direction filter → should show only outbound leads
- [ ] Select a specific outbound list → should filter accordingly
- [ ] Combine filters (direction + list + status) → should work together
- [ ] Clear filters → should show all leads

### Outbound Calls Page
- [ ] Navigate to "שיחות יוצאות"
- [ ] In Kanban view, click on a lead card → should navigate to lead detail page
- [ ] In Table view (if using existing leads tab), click on a lead → should navigate
- [ ] In Imported Leads tab, click "Select All" checkbox
- [ ] Verify max 3 leads are selected (or available slots)
- [ ] Click on an imported lead row → should navigate to lead detail page
- [ ] Verify checkbox clicks don't trigger navigation

### Data Flow
- [ ] Make a new inbound call → lead should get `last_call_direction=inbound`
- [ ] Make a new outbound call → lead should get `last_call_direction=outbound`
- [ ] Filter by direction in Leads page → should reflect recent updates

## API Endpoints Modified

### GET /api/leads
**New Query Parameters:**
- `direction` - Filter by call direction (inbound|outbound|all)
- `outbound_list_id` - Filter by outbound list ID

**Updated Response:**
- Now includes `last_call_direction` field for each lead

### GET /api/outbound/import-lists
**Used By:** Leads page to populate outbound list filter dropdown

## Database Migration Note

The `last_call_direction` field is added to the Lead model with `nullable=True` and `index=True`.

**Migration Handling:**
- New calls will automatically populate this field
- Existing leads will have `NULL` until they receive a new call
- NULL values are treated as "all" in filters (won't exclude any leads)

## UI/UX Improvements

### Consistency Across Pages
1. **Lead Cards**: All pages now show leads with consistent format:
   - Name + Status badge
   - Phone number
   - Summary (if available)
   - Relative timestamp

2. **Navigation**: Clicking on a lead from any page leads to the same detail page (`/app/leads/:id`)

3. **Filtering**: Similar filter UI patterns across pages

### User Flow
1. **Inbound Calls**: User sees incoming call leads → clicks to view detail → can update status
2. **Outbound Calls**: User views leads in Kanban → drag to change status → click to see full details
3. **Leads Management**: User can filter by call direction and list → comprehensive view of all leads

## Notes for Deployment

1. **Database**: The new `last_call_direction` column should be added via migration
2. **Backward Compatibility**: Code handles NULL values gracefully
3. **Performance**: Field is indexed for fast filtering
4. **No Breaking Changes**: All existing functionality preserved
