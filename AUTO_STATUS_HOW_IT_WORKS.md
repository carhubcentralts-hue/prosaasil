# Auto Status Update After Calls - How It Works

## ✅ FULLY IMPLEMENTED

The auto-status update feature is **already working** for both LeadsPage and OutboundCallsPage!

## How It Works

### 1. Call Completes (Inbound or Outbound)
- Call finishes
- Recording is processed
- AI generates summary of the call

### 2. Auto Status Service Analyzes Summary
Location: `server/services/lead_auto_status_service.py`

The service:
- Gets the business's custom statuses (multi-tenant aware)
- Analyzes the AI-generated call summary
- Uses intelligent keyword matching in Hebrew and English
- Only changes status if confident match found

### 3. Lead Status Updated Automatically
Location: `server/tasks_recording.py` lines 551-589

After every call:
```python
# Use new auto-status service
suggested_status = suggest_lead_status_from_call(
    tenant_id=call_log.business_id,  # Multi-tenant!
    lead_id=lead.id,
    call_direction=call_direction,  # inbound/outbound
    call_summary=summary,  # AI-generated summary
    call_transcript=final_transcript or transcription
)

if suggested_status:
    old_status = lead.status
    lead.status = suggested_status  # Auto-update!
    # Create activity log
    # Save to DB
```

### 4. Lead Fields Updated
- `lead.status` → New status based on call
- `lead.summary` → AI-generated call summary
- `lead.last_contact_at` → Timestamp of call
- Activity log created with "auto_inbound" or "auto_outbound"

### 5. Frontend Shows Updated Status
- LeadsPage automatically refreshes and shows new status
- OutboundCallsPage (with Kanban) will show lead in new column

## Intelligent Status Mapping

The service maps call outcomes to statuses **dynamically** based on what statuses exist for that business:

### Priority 1: Keyword Matching in Summary

```python
# Not interested / Not relevant
Keywords: "לא מעוניין", "לא רלוונטי", "להסיר", "תפסיקו"
→ Maps to: "not_relevant" (if exists)

# Interested / Wants info
Keywords: "מעוניין", "כן רוצה", "תשלח פרטים", "דברו איתי"
→ Maps to: "interested" (if exists)

# Follow up / Call back
Keywords: "תחזרו", "מאוחר יותר", "שבוע הבא"
→ Maps to: "follow_up" (if exists)

# No answer / Voicemail
Keywords: "לא ענה", "אין מענה", "תא קולי"
→ Maps to: "no_answer" (if exists)

# Appointment scheduled
Keywords: "קבענו פגישה", "נקבע", "appointment"
→ Maps to: "qualified" (if exists)

# Default fallback
If conversation happened but no specific match:
→ Maps to: "contacted" (if exists)
```

### Priority 2: Fallback Statuses

If the ideal status doesn't exist, the service uses fallbacks:
- not_relevant → lost
- interested → qualified  
- no_answer → attempting

### No Update If Uncertain

If the service cannot confidently determine the status, it **does not change anything**. This prevents incorrect status updates.

## Multi-Tenant Aware

The service ONLY uses statuses that exist for that specific business:

```python
def _get_valid_statuses(self, tenant_id: int) -> set:
    """Get set of valid status names for tenant"""
    statuses = LeadStatus.query.filter_by(
        business_id=tenant_id,  # Only this business!
        is_active=True
    ).all()
    return {s.name for s in statuses}
```

So if Business A has custom statuses and Business B has different ones, each lead gets updated with **their business's statuses only**.

## Examples

### Example 1: Inbound Call - Not Interested
```
Call Summary: "הלקוח אמר שהוא לא מעוניין בשירות ובקש שלא יתקשרו אליו יותר"

Auto Status Service:
1. Finds keyword "לא מעוניין"
2. Checks if "not_relevant" status exists for this business ✓
3. Updates: lead.status = "not_relevant"
4. Creates activity: "Status changed: new → not_relevant (source: auto_inbound)"
```

### Example 2: Outbound Call - Follow Up
```
Call Summary: "הלקוח מעוניין אבל ביקש שנחזור אליו בשבוע הבא"

Auto Status Service:
1. Finds keyword "בשבוע הבא" 
2. Checks if "follow_up" status exists for this business ✓
3. Updates: lead.status = "follow_up"
4. Creates activity: "Status changed: new → follow_up (source: auto_outbound)"
```

### Example 3: No Confident Match
```
Call Summary: "שיחה קצרה, הלקוח אמר שלום והתנתק"

Auto Status Service:
1. No strong keywords found
2. Returns None
3. Status NOT changed (stays as-is)
```

## Testing

To test this feature:

### Test 1: Inbound Call → Not Relevant
1. Call your business number
2. When AI answers, say: "לא מעוניין, תפסיקו להתקשר"
3. Hang up
4. Wait 30 seconds for processing
5. Go to LeadsPage
6. Find your lead → Status should be "לא רלוונטי" (not_relevant)

### Test 2: Outbound Call → Follow Up
1. Start outbound call to a lead
2. When they answer, say: "תחזור אלי בשבוע הבא"
3. Hang up
4. Wait 30 seconds
5. Go to LeadsPage
6. Lead status should be "חזרה" (follow_up)

### Test 3: Inbound Call → Interested
1. Call your business
2. Say: "כן אני מעוניין, תשלח לי פרטים"
3. Hang up
4. Wait 30 seconds
5. Lead status should be "מעוניין" (interested)

## Activity Log

Every auto-status change is logged in the lead_activities table:

```json
{
  "type": "status_change",
  "payload": {
    "from": "new",
    "to": "interested", 
    "source": "auto_inbound",
    "call_sid": "CA123..."
  }
}
```

This allows you to:
- Track why a status changed
- See which call caused the change
- Audit the AI's decisions
- Manually override if needed

## Configuration

Default statuses are created automatically for each business:
- new (חדש)
- attempting (בניסיון קשר)
- no_answer (לא ענה)
- contacted (נוצר קשר)
- interested (מעוניין)
- follow_up (חזרה)
- not_relevant (לא רלוונטי)
- qualified (מוכשר)
- won (זכיה)
- lost (אובדן)
- unqualified (לא מוכשר)

Businesses can customize these in the Status Management page.

## Summary

✅ **No frontend changes needed for LeadsPage**
✅ **Already works for both inbound and outbound calls**
✅ **Multi-tenant aware - uses business's custom statuses**
✅ **AI analyzes call summary intelligently**
✅ **Only updates when confident**
✅ **Creates audit trail in activity log**

The feature is **live and working**. Every call that generates a summary will automatically update the lead status if a confident match is found!
