# Manual Testing Guide: Lead Notes Context

## Overview
This feature ensures the AI receives lead notes from previous interactions during calls and saves new notes after calls end.

## Setup Test Data

### 1. Create a lead with existing notes

```sql
-- Find or create a test lead
SELECT id, full_name, phone_e164, tenant_id FROM leads WHERE phone_e164 = '+972504294724' LIMIT 1;

-- Add test notes to the lead (replace LEAD_ID and TENANT_ID with actual values)
INSERT INTO lead_notes (lead_id, tenant_id, note_type, content, created_at, created_by)
VALUES 
  (3, 4, 'manual', 'לקוח ביקש תיקון בלמים בביקור הקודם. העדיף טכנאי אלי.', NOW(), 1),
  (3, 4, 'manual', 'הלקוח התלונן על רעשים במנוע. נקבע תור לבדיקה.', NOW(), 1),
  (3, 4, 'call_summary', 'שיחה קודמת: לקוח שאל על מחיר טיפול שנתי. הבהרנו שהמחיר 500 שקל.', NOW(), NULL);

-- Verify notes were created
SELECT id, note_type, LEFT(content, 80) as content_preview, created_at 
FROM lead_notes 
WHERE lead_id = 3 
ORDER BY created_at DESC;
```

## Test Scenarios

### Scenario 1: Verify Notes Are Loaded at Call Start

**Expected Behavior:**
- When call starts, system fetches last 3 notes for the lead
- Notes are injected into AI context via NAME_ANCHOR
- AI receives context about previous interactions

**How to Test:**
1. Call the number associated with the lead (e.g., +972504294724)
2. Monitor backend logs for:
   ```
   ✅ [NOTES] Fetched 3 notes from Lead (lead_id=3)
   📝 [NOTES] Preview: לקוח ביקש תיקון בלמים...
   ```
3. During the call, ask the AI: "מה אתה יודע עלי?" or "מה היו הבעיות שלי בעבר?"
4. **EXPECTED**: AI should reference previous issues (בלמים, רעשים במנוע, טיפול שנתי)

**Success Criteria:**
- ✅ Logs show notes were fetched
- ✅ AI mentions previous context in responses
- ✅ AI doesn't hallucinate - only mentions real notes

### Scenario 2: Verify Notes Are Saved After Call

**Expected Behavior:**
- After call ends, system creates a new LeadNote with call transcript
- Note type is 'call_summary'
- Note is linked to the call_log via call_id

**How to Test:**
1. Complete a call with the test lead
2. After call ends, check backend logs for:
   ```
   ✅ [FINALIZE] Created lead note for lead_id=3 from call CA...
   ```
3. Query database to verify note was created:
   ```sql
   SELECT id, note_type, LEFT(content, 100) as content_preview, call_id, created_at 
   FROM lead_notes 
   WHERE lead_id = 3 
   ORDER BY created_at DESC 
   LIMIT 1;
   ```

**Success Criteria:**
- ✅ Log shows note was created
- ✅ Database has new note with `note_type='call_summary'`
- ✅ Note content includes call transcript (first 500 chars)
- ✅ Note is linked to correct call_id
- ✅ created_by is NULL (AI-generated)

### Scenario 3: Verify Notes Context in Sequential Calls

**Expected Behavior:**
- Make two calls to same lead
- Second call should see notes from first call
- AI maintains continuity across calls

**How to Test:**
1. **First Call**: Discuss a specific issue (e.g., "יש לי בעיה עם הבלמים")
2. Wait for call to end and note to be saved
3. **Second Call**: Ask "על מה דיברנו בשיחה הקודמת?"
4. **EXPECTED**: AI should reference the brake issue from first call

**Success Criteria:**
- ✅ First call creates note in database
- ✅ Second call loads that note
- ✅ AI references previous conversation accurately
- ✅ Conversation feels continuous, not disconnected

## Debugging

### Check if notes are in database
```sql
SELECT 
  l.full_name,
  ln.note_type,
  LEFT(ln.content, 100) as content_preview,
  ln.created_at,
  ln.call_id
FROM lead_notes ln
JOIN leads l ON ln.lead_id = l.id
WHERE l.phone_e164 = '+972504294724'
ORDER BY ln.created_at DESC;
```

### Check if notes were fetched during call
Search logs for:
```
✅ [NOTES] Fetched
📝 [NOTES] Preview
✅ [NAME_ANCHOR] Injected
Previous notes:
```

### Check if notes were saved after call
Search logs for:
```
✅ [FINALIZE] Created lead note
```

## Expected Log Flow

```
[Call Start]
✅ [NAME_ANCHOR DEBUG] Resolved from DB (inbound)
✅ [GENDER] Fetched from Lead: 'male' (lead_id=3)
✅ [NOTES] Fetched 3 notes from Lead (lead_id=3)
📝 [NOTES] Preview: לקוח ביקש תיקון בלמים...
✅ [NAME_ANCHOR] Injected: enabled=True, name='שי', hash=...
   -> Context: "Customer name available: שי. Use it naturally. Previous notes: לקוח ביקש תיקון בלמים... | הלקוח התלונן על רעשים... | שיחה קודמת: לקוח שאל..."

[Call End]
✅ [FINALIZE] Call metadata saved (realtime only): CA...
✅ [FINALIZE] Created lead note for lead_id=3 from call CA...
```

## Troubleshooting

### Issue: Notes not fetched
**Symptoms:** No "✅ [NOTES]" logs
**Causes:**
- Lead doesn't exist in database
- Lead has no notes
- Phone number normalization issue

**Fix:** Verify lead exists and has notes using SQL queries above

### Issue: Notes not saved
**Symptoms:** No "✅ [FINALIZE] Created lead note" log
**Causes:**
- Call ended too quickly (< 20 chars of conversation)
- lead_id not linked to call_log
- Database error

**Fix:** Check call_log.lead_id is set correctly

### Issue: AI doesn't use notes
**Symptoms:** Notes are fetched but AI ignores them
**Causes:**
- Notes not in NAME_ANCHOR message
- AI prompt doesn't instruct to use context
- Notes truncated too aggressively

**Fix:** Verify NAME_ANCHOR includes "Previous notes:" in logs

## Success Metrics

After deployment, monitor these metrics:
- % of calls with notes loaded (should be > 50% for returning customers)
- % of calls with notes saved (should be ~100%)
- Average notes per lead (should increase over time)
- AI response quality (fewer repeated questions for returning customers)
