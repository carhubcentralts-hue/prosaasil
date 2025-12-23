# Export Leads by Status Feature

## Overview

This feature adds an export button to each status column in the Outbound Calls Kanban view, allowing users to export leads filtered by their current status to a CSV file.

## User Interface

### Location
The export button appears in the header of each status column in the Kanban view on the Outbound Calls page (`/app/outbound-calls`).

### Visual Design
- **Icon**: Download icon (⬇️)
- **Tooltip**: "ייצוא לידים בסטטוס '<status name>'"
- **Position**: Next to the "Select All" checkbox in the column header
- **States**:
  - Normal: Blue/gray download icon
  - Loading: Spinning loader icon
  - Disabled: Grayed out (when status has no leads)

### User Flow
1. User navigates to Outbound Calls page
2. Switches to Kanban view (if not already selected)
3. Clicks the download icon on any status column
4. CSV file automatically downloads with leads from that status
5. File opens in Excel with proper Hebrew text encoding

## Technical Implementation

### Backend API

#### Endpoint
```
GET /api/outbound/leads/export?status_id=<status_name>&format=csv
```

#### Authentication
- Requires authentication via `require_api_auth`
- Allowed roles: `system_admin`, `owner`, `admin`

#### Parameters
- `status_id` (required): The status name to filter by (e.g., "new", "contacted")
- `format` (optional): Export format, currently only "csv" is supported

#### Response
- Content-Type: `text/csv; charset=utf-8`
- Content-Disposition: `attachment; filename="outbound_leads_status_<statusName>_<YYYY-MM-DD>.csv"`
- Encoding: UTF-8 with BOM for Excel Hebrew compatibility

#### CSV Structure
The exported CSV contains the following columns:
1. `status_id` - The internal status identifier
2. `status_name` - The human-readable status label
3. `lead_id` - Unique lead identifier
4. `full_name` - Lead's full name
5. `phone` - Phone number (E.164 format)
6. `email` - Email address
7. `created_at` - Lead creation timestamp
8. `last_call_at` - Timestamp of most recent call
9. `last_call_status` - Status of most recent call
10. `source` - Lead source (e.g., "phone", "whatsapp", "imported_outbound")
11. `notes` - Any notes associated with the lead

#### Security Features
- **Tenant Isolation**: Only exports leads belonging to the authenticated user's tenant
- **Input Validation**: Status filter validated with regex pattern `^[a-zA-Z0-9_-]+$`
- **SQL Injection Prevention**: Uses parameterized queries with SQLAlchemy
- **Permission Checks**: Only owner/admin roles can access the endpoint

### Frontend Implementation

#### Component
`client/src/pages/calls/components/OutboundKanbanColumn.tsx`

#### Key Features
- **State Management**: `isExporting` state to track export progress
- **Error Handling**: Graceful error messages with fallback
- **File Download**: Uses browser's native download mechanism
- **Loading State**: Shows spinner while exporting
- **Disabled State**: Button disabled when status has no leads

#### Export Handler
```typescript
const handleExport = async () => {
  // Construct URL with parameters
  const url = `/api/outbound/leads/export?status_id=${status.name}&format=csv`;
  
  // Fetch CSV file
  const response = await fetch(url, { credentials: 'include' });
  
  // Download file
  const blob = await response.blob();
  const downloadUrl = window.URL.createObjectURL(blob);
  // ... trigger download
}
```

## Data Flow

```
User clicks Export button
    ↓
Frontend sends GET request with status_id
    ↓
Backend validates permissions and tenant
    ↓
Backend queries leads with matching status
    ↓
Backend joins with CallLog for last call info
    ↓
Backend generates CSV with UTF-8 BOM
    ↓
Backend returns CSV as download
    ↓
Frontend triggers browser download
    ↓
User receives CSV file
```

## Testing

### Unit Tests
Location: `tests/test_export_leads_by_status.py`

Tests include:
- CSV structure validation
- Filename format verification
- Status filter security validation
- UTF-8 BOM CSV generation

### Manual Testing Checklist
- [ ] Export from status with leads - success
- [ ] Export from empty status - disabled button
- [ ] Open CSV in Excel - Hebrew text displays correctly
- [ ] Verify filename follows format: `outbound_leads_status_<name>_<date>.csv`
- [ ] Verify all required columns are present
- [ ] Verify tenant isolation (no data leakage)
- [ ] Test with non-admin user - access denied
- [ ] Test with invalid status name - error message

## Excel Compatibility

The CSV export includes a UTF-8 BOM (Byte Order Mark) character at the beginning of the file. This ensures that Microsoft Excel correctly interprets Hebrew characters and other Unicode content.

### Technical Details
- BOM character: `\ufeff`
- Added to CSV content before download
- Recognized by Excel for proper encoding detection

## File Naming Convention

Filename format: `outbound_leads_status_<statusName>_<YYYY-MM-DD>.csv`

Examples:
- `outbound_leads_status_new_2025-12-23.csv`
- `outbound_leads_status_contacted_2025-12-23.csv`
- `outbound_leads_status_not_interested_2025-12-23.csv`

Special characters in status names are sanitized using regex: `[^a-zA-Z0-9_-]`

## Error Handling

### Backend Errors
- **Missing status_id**: Returns 400 with error message
- **Invalid status format**: Returns 400 (security validation)
- **Permission denied**: Returns 403
- **Database error**: Returns 500 with logged error
- **No tenant context**: Returns 403 (except system_admin)

### Frontend Errors
- **Network error**: Alert with error message
- **Server error**: Alert with server error message
- **Parsing error**: Alert with generic error message

## Performance Considerations

- **Database Query**: Single query with join to CallLog table
- **Memory**: CSV generated in StringIO (in-memory)
- **Scalability**: Suitable for up to several thousand leads per status
- **Optimization**: Uses ORDER BY created_at DESC for consistent ordering

## Future Enhancements

Potential improvements mentioned in the requirements:
1. **Excel Format**: Add native `.xlsx` export option
2. **Custom Columns**: Allow users to select which columns to export
3. **Date Range Filter**: Export leads within specific date range
4. **Scheduled Exports**: Automated periodic exports via email
5. **Export History**: Track export history and allow re-download

## Security Notes

### Input Validation
- Status filter: `^[a-zA-Z0-9_-]+$` (alphanumeric, underscore, dash only)
- Maximum length: 64 characters
- Prevents SQL injection and path traversal attacks

### Authentication & Authorization
- Endpoint requires valid session cookie
- Role-based access control (owner/admin only)
- Tenant isolation enforced at query level

### Data Privacy
- Only exports data for authenticated user's tenant
- No cross-tenant data leakage
- Respects user permissions

## Deployment Notes

### Requirements
- Python 3.8+
- Flask
- SQLAlchemy
- Existing Lead and LeadStatus models
- Existing CallLog model for last call information

### Configuration
No additional configuration required. The feature uses:
- Existing authentication system
- Existing database connection
- Existing tenant context from `g.get('tenant')`

### Database
No database migrations required. Uses existing tables:
- `leads`
- `lead_statuses`
- `call_logs`

## Support

For issues or questions about this feature:
1. Check error logs in backend console
2. Verify user has correct permissions (owner/admin)
3. Verify tenant context is set correctly
4. Check browser console for frontend errors
5. Test with simple status (e.g., "new") first

## Related Documentation
- [Outbound Calls Feature](OUTBOUND_CALLS_FEATURE.md)
- [Lead Status Management](LEAD_STATUS_MANAGEMENT.md)
- [Authentication & Authorization](AUTH_SYSTEM.md)
