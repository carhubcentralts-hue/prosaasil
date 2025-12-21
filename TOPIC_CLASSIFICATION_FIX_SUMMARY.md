# Topic Classification Skip Logic Fix - Summary

## Problem Statement

The topic classification system had a bug where it was checking `detected_topic_source` to determine if a call or lead had already been classified. This caused issues because:

1. **`detected_topic_source` can exist without actual classification**: The field could be set to "embedding" (default value) during:
   - Database migrations
   - Schema initialization
   - Previous runs where fields were partially set

2. **False positive skips**: When `detected_topic_source` existed but `detected_topic_id` was NULL, the system incorrectly assumed the item was already classified and skipped re-classification.

3. **Missing classifications**: This resulted in calls and leads that should have been classified being skipped, preventing proper topic detection based on transcripts and embeddings.

## Solution

The fix changes the skip logic to check `detected_topic_id` instead of `detected_topic_source`:

### ✅ Correct Logic
```python
# Skip ONLY if there's an actual topic result
if call_log.detected_topic_id is not None:
    # Already classified - skip
    pass
else:
    # Not classified - run classification
    classify()
```

### ❌ Old (Incorrect) Logic
```python
# This was wrong - detected_topic_source can exist without a result
if call_log.detected_topic_source:
    # Incorrectly skips even when no topic was detected
    pass
```

## Changes Made

### 1. Fixed CallLog Skip Logic (`server/tasks_recording.py`)

**Location**: Line ~684 in `save_call_to_db` function

**Before:**
```python
if call_log.detected_topic_source:
    print(f"[TOPIC_CLASSIFY] ⏭️ Call {call_sid} already classified (source={call_log.detected_topic_source}) - skipping")
    log.info(f"[TOPIC_CLASSIFY] Skipping - already classified")
```

**After:**
```python
if call_log.detected_topic_id is not None:
    print(f"[TOPIC_CLASSIFY] ⏭️ Call {call_sid} already classified (topic_id={call_log.detected_topic_id}) - skipping")
    log.info(f"[TOPIC_CLASSIFY] Skipping - already classified with topic_id={call_log.detected_topic_id}")
```

### 2. Fixed Lead Skip Logic (`server/tasks_recording.py`)

**Location**: Line ~721 in `save_call_to_db` function

**Before:**
```python
if lead and not lead.detected_topic_source:  # Idempotency for lead too
    lead.detected_topic_id = topic_id
    lead.detected_topic_confidence = confidence
    lead.detected_topic_source = method
```

**After:**
```python
if lead and lead.detected_topic_id is None:  # Idempotency for lead too
    lead.detected_topic_id = topic_id
    lead.detected_topic_confidence = confidence
    lead.detected_topic_source = method
```

### 3. Added Lead Reclassify Endpoint (`server/routes_ai_topics.py`)

**New endpoint**: `POST /api/leads/<lead_id>/reclassify-topic`

Features:
- Resets all three topic fields: `detected_topic_id`, `detected_topic_confidence`, `detected_topic_source`
- Uses the most recent call's transcript for classification
- Respects `auto_tag_leads` setting
- Returns classification result with confidence scores

### 4. Updated Tests (`test_amd_topic_fixes.py`)

Enhanced test validation to:
- Verify the correct skip logic checks `detected_topic_id`
- Ensure no old logic checking `detected_topic_source` for skip conditions
- Validate both CallLog and Lead use the correct logic

## Benefits

✅ **Proper idempotency**: Only skips classification when a topic has actually been detected  
✅ **Re-classification works**: Items with `detected_topic_source` but no `detected_topic_id` will be properly classified  
✅ **Uses embeddings correctly**: Ensures transcripts are analyzed using embeddings for topic detection  
✅ **Independent reclassification**: Separate endpoints for CallLog and Lead allow targeted re-classification  
✅ **Proper field reset**: Reclassify endpoints reset all three fields before re-running classification  

## Testing

### Unit Tests
Run the test suite to verify the fix:
```bash
python test_amd_topic_fixes.py
```

Expected results:
- Test 6 (Post-Call Classification Integration) should pass
- Verifies correct idempotency logic
- Confirms no old skip logic remains

### Manual Testing

#### 1. Test CallLog Reclassification
```bash
curl -X POST http://localhost:5000/api/call_logs/123/reclassify-topic \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

Expected behavior:
- Resets `detected_topic_id`, `detected_topic_confidence`, `detected_topic_source` to NULL
- Re-runs classification using the call's transcript
- Returns new classification result

#### 2. Test Lead Reclassification
```bash
curl -X POST http://localhost:5000/api/leads/456/reclassify-topic \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

Expected behavior:
- Resets lead's topic fields to NULL
- Uses the most recent call's transcript for classification
- Returns new classification result

#### 3. Test Skip Logic
To verify the skip logic:
1. Create a call with classification (has `detected_topic_id`)
2. Trigger recording processing again
3. Check logs - should see: "already classified (topic_id=X) - skipping"
4. Verify classification is NOT run again

## Database Schema

The three topic-related fields on CallLog and Lead models:

```python
detected_topic_id = db.Column(db.Integer, db.ForeignKey("business_topics.id"), nullable=True)
detected_topic_confidence = db.Column(db.Float, nullable=True)  # 0.0-1.0
detected_topic_source = db.Column(db.String(32), default="embedding")
```

**Key insight**: 
- `detected_topic_source` has a default value, so it can be non-NULL even without classification
- `detected_topic_id` is NULL by default and only set when a topic is actually detected
- Therefore, `detected_topic_id IS NOT NULL` is the correct check for "already classified"

## Migration Path

No database migration needed! This is purely a logic fix.

However, if you have existing records with:
- `detected_topic_source = "embedding"`
- `detected_topic_id = NULL`

They will now be properly re-classified on the next recording processing run.

## API Endpoints Summary

### Call Reclassification
- **URL**: `POST /api/call_logs/<call_log_id>/reclassify-topic`
- **Auth**: Requires owner/admin
- **Response**: Classification result with topic_id, topic_name, confidence, method

### Lead Reclassification
- **URL**: `POST /api/leads/<lead_id>/reclassify-topic`
- **Auth**: Requires owner/admin
- **Response**: Classification result with topic_id, topic_name, confidence, method

Both endpoints:
1. Reset all three topic fields to NULL
2. Run classification using transcript (final_transcript preferred, falls back to transcription)
3. Update the record if classification succeeds and auto-tagging is enabled
4. Return the classification result

## Verification Checklist

- [x] Skip logic checks `detected_topic_id` for CallLog
- [x] Skip logic checks `detected_topic_id` for Lead
- [x] Reclassify endpoint resets all three fields for CallLog
- [x] Reclassify endpoint resets all three fields for Lead
- [x] New lead reclassify endpoint added
- [x] Tests updated to verify correct logic
- [x] No syntax errors in modified files
- [ ] Manual testing of reclassify endpoints (requires running server)
- [ ] Production verification after deployment

## Related Files

- `server/tasks_recording.py` - Main classification logic and skip checks
- `server/routes_ai_topics.py` - Reclassify endpoints
- `server/services/topic_classifier.py` - Topic classification service (unchanged)
- `test_amd_topic_fixes.py` - Test validation

## Notes

This fix ensures that topic classification is performed correctly and that the system properly uses embeddings from transcripts to detect and assign topics. The skip logic now correctly identifies when a topic has actually been detected versus when the fields are just initialized with default values.
