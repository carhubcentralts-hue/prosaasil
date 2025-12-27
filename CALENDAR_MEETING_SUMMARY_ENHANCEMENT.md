# Calendar Meeting Summary Enhancement - Migration Guide

## Overview
This enhancement adds dynamic conversation summary and lead linking to appointments in the calendar page.

## Problem Solved
The calendar page previously only displayed full transcripts. This enhancement adds:
- **Dynamic conversation summary**: Shows intent, sentiment, next action, and extracted information
- **Lead navigation**: Direct link to the lead from the appointment
- **Phone number display**: Automatically extracted from the call
- **Better organization**: Dynamic summary shown first, transcript collapsible

## Database Changes

### New Columns in `appointments` Table:
1. **`dynamic_summary` (TEXT)**: Stores JSON with conversation analysis:
   - `summary`: Short summary text
   - `intent`: Customer's intent
   - `next_action`: Suggested next action
   - `sentiment`: Conversation sentiment
   - `urgency_level`: Urgency assessment
   - `extracted_info`: Key information extracted from conversation

2. **`lead_id` (INTEGER)**: Foreign key to `leads` table
   - Enables navigation from appointment to lead
   - Links appointments to CRM leads

3. **`from_phone` (VARCHAR)**: Extracted phone number from call

## Migration Instructions

### Running the Migration

```bash
# From the project root directory
python migration_add_appointment_dynamic_summary.py
```

The migration will:
- Add `dynamic_summary` TEXT column to appointments table
- Add `lead_id` column with foreign key to leads table
- Create index on `lead_id` for performance
- Skip if columns already exist (idempotent)

### Manual Migration (if needed)

If the automated migration script doesn't work, run this SQL:

```sql
-- Add dynamic_summary column
ALTER TABLE appointments 
ADD COLUMN IF NOT EXISTS dynamic_summary TEXT;

-- Add lead_id column with foreign key
ALTER TABLE appointments 
ADD COLUMN IF NOT EXISTS lead_id INTEGER REFERENCES leads(id);

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_appointments_lead_id ON appointments(lead_id);
```

## Backend Changes

### Files Modified:
1. **`server/models_sql.py`**: Added fields to Appointment model
2. **`server/routes_calendar.py`**: Updated API responses to include new fields
3. **`server/auto_meeting.py`**: Populate dynamic_summary when creating appointments
4. **`server/media_ws_ai.py`**: Populate dynamic_summary when finalizing calls

### API Response Changes

The appointments API now returns:
```json
{
  "id": 123,
  "lead_id": 456,
  "dynamic_summary": "{\"summary\":\"...\", \"intent\":\"...\", ...}",
  "from_phone": "+972501234567",
  "call_summary": "Short AI summary",
  "call_transcript": "Full conversation text",
  ...
}
```

## Frontend Changes

### CalendarPage.tsx Updates:
1. **Dynamic Summary Display**: Rich UI showing analysis with icons and badges
2. **Lead Navigation Button**: "צפה בליד" button to navigate to CRM
3. **Phone Number Display**: Shows the caller's number
4. **Collapsible Transcript**: Transcript is now in a collapsible `<details>` element
5. **Priority Order**: Dynamic summary → Call summary → Transcript

### Visual Design:
- Purple gradient for dynamic summary (most important)
- Blue gradient for call summary
- Green gradient for transcript
- Badges for sentiment and urgency
- Grid layout for intent and next action

## Testing

### Test Scenarios:

1. **New Appointment with Call**:
   - Make a call that creates an appointment
   - Verify dynamic summary appears
   - Check lead navigation button
   - Confirm phone number displays

2. **Existing Appointments**:
   - Old appointments without dynamic_summary should still display normally
   - No errors for missing fields

3. **Lead Navigation**:
   - Click "צפה בליד" button
   - Should navigate to CRM page with lead highlighted

4. **Responsive Design**:
   - Test on mobile (320px)
   - Test on tablet (768px)
   - Test on desktop (1024px+)

## Rollback

If needed, remove the columns:

```sql
ALTER TABLE appointments DROP COLUMN IF EXISTS dynamic_summary;
ALTER TABLE appointments DROP COLUMN IF EXISTS lead_id;
DROP INDEX IF EXISTS idx_appointments_lead_id;
```

## Production Deployment Checklist

- [ ] Run migration script in staging environment
- [ ] Verify appointments display correctly
- [ ] Test lead navigation
- [ ] Test with various appointment types
- [ ] Deploy backend changes
- [ ] Deploy frontend changes
- [ ] Run migration in production
- [ ] Verify production appointments work
- [ ] Monitor error logs for any issues

## Support

If you encounter issues:
1. Check database connection and permissions
2. Verify Python dependencies are installed
3. Check server logs for error messages
4. Verify existing appointments still work
5. Test with a new appointment from a call
