# Calendar Status Management Feature

## Overview
Added the ability to edit and save appointment statuses per business in the calendar management interface.

## Problem Solved
Previously, users could only use the default hardcoded appointment statuses (scheduled, confirmed, paid, unpaid, cancelled). There was no UI to customize these statuses per business, even though the backend API endpoints existed.

## Solution Implemented

### Frontend Changes (client/src/pages/Calendar/CalendarPage.tsx)

#### 1. New Imports
- `Settings` - Icon for settings button
- `ChevronDown`, `ChevronUp` - Icons for collapsible section
- `Check` - Icon for update button

#### 2. New State Variables
```typescript
const [showStatusSettings, setShowStatusSettings] = useState(false);
const [editingStatus, setEditingStatus] = useState<AppointmentStatusConfig | null>(null);
const [statusFormData, setStatusFormData] = useState({
  key: '',
  label: '',
  color: 'gray'
});
const [savingStatuses, setSavingStatuses] = useState(false);
```

#### 3. New Functions

**handleSaveStatuses()**
- Saves all statuses to the backend via `PUT /api/calendar/config/appointment-statuses`
- Shows success/error messages to user
- Refreshes statuses from server after save

**handleAddStatus()**
- Validates input fields
- Checks for duplicate keys
- Adds new status to local state
- Clears form

**handleEditStatus(status)**
- Sets the status being edited
- Populates form with current values

**handleUpdateStatus()**
- Updates the edited status in local state
- Clears editing state

**handleDeleteStatus(key)**
- Confirms deletion with user
- Removes status from local state

**handleCancelStatusEdit()**
- Cancels editing and clears form

**getColorClasses(color)**
- Maps color names to Tailwind CSS classes
- Supports 10 colors: gray, red, yellow, green, blue, indigo, purple, pink, orange, teal

#### 4. New UI Section

Added to the "ניהול לוחות" (Management) tab, after the calendar list:

- **Collapsible Settings Panel**
  - Header button with Settings icon
  - Shows/hides settings with chevron icon
  - Blue gradient background

- **Current Statuses List**
  - Shows all existing statuses with their colors
  - Edit button for each status
  - Delete button for each status
  - Displays status key in parentheses

- **Add/Edit Form**
  - Key field (English, no spaces) - disabled when editing
  - Label field (Hebrew display name)
  - Color dropdown (10 colors)
  - Live preview of status badge
  - Add/Update button depending on mode
  - Cancel button when editing

- **Save Changes Button**
  - Saves all changes to backend
  - Shows loading state while saving
  - Displays note about per-business saving

## Backend API Endpoints (Already Existed)

### GET /api/calendar/config/appointment-statuses
Returns the appointment statuses for the current business.

**Response:**
```json
{
  "appointment_statuses": [
    {
      "key": "scheduled",
      "label": "מתוכנן",
      "color": "yellow"
    },
    ...
  ]
}
```

### PUT /api/calendar/config/appointment-statuses
Updates appointment statuses for the current business.

**Request:**
```json
{
  "appointment_statuses": [
    {
      "key": "scheduled",
      "label": "מתוכנן",
      "color": "yellow"
    },
    ...
  ]
}
```

**Response:**
```json
{
  "message": "Appointment statuses updated successfully"
}
```

## User Workflow

1. Navigate to Calendar page (לוח שנה)
2. Click on "ניהול לוחות" (Management) tab
3. Scroll down to find "ניהול סטטוסי פגישות" section
4. Click the settings button to expand the panel
5. View existing statuses
6. To add a new status:
   - Fill in the key (English, no spaces)
   - Fill in the label (Hebrew display name)
   - Select a color
   - Preview the badge
   - Click "הוסף סטטוס" (Add Status)
7. To edit a status:
   - Click the edit button on any status
   - Modify the label and/or color
   - Preview the changes
   - Click "עדכן סטטוס" (Update Status)
8. To delete a status:
   - Click the delete button on any status
   - Confirm the deletion
9. Click "שמור שינויים" (Save Changes) to persist all changes

## Status Color Options

The following colors are available:
- אפור (gray)
- אדום (red)
- צהוב (yellow)
- ירוק (green)
- כחול (blue)
- אינדיגו (indigo)
- סגול (purple)
- ורוד (pink)
- כתום (orange)
- טורקיז (teal)

## Security & Permissions

- Backend endpoint requires authentication (`require_api_auth`)
- Only users with roles: `system_admin`, `owner`, or `admin` can update statuses
- Requires calendar page access (`require_page_access('calendar')`)
- Statuses are saved per business (tenant_id)

## Testing Recommendations

1. **Add Status Test**
   - Add a new status with Hebrew label
   - Verify it appears in the list
   - Save and refresh page
   - Verify status persists

2. **Edit Status Test**
   - Edit an existing status label
   - Change its color
   - Verify preview updates
   - Save and verify changes persist

3. **Delete Status Test**
   - Delete a custom status
   - Verify it's removed from list
   - Save and verify deletion persists

4. **Validation Tests**
   - Try to add status without key/label (should show alert)
   - Try to add duplicate key (should show alert)
   - Try to save empty status list (should show alert)

5. **Per-Business Test**
   - Configure statuses for Business A
   - Switch to Business B
   - Verify Business B has its own statuses (or defaults)

## Future Enhancements

- Drag and drop to reorder statuses
- Default status marking
- Status usage statistics
- Bulk import/export of statuses
- Status templates
- Confirmation modal instead of browser alert
- Toast notifications instead of alerts
- Undo functionality
