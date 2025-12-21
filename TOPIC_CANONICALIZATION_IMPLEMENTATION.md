# Topic Canonicalization Implementation Summary

## Overview
This implementation ensures that topic classification and service mapping work with normalized text and always use canonical values throughout the pipeline, from topic detection to webhook delivery.

## Problem Statement
When text contains variations like "פריצת מנעול", "התקנת מנול", or "מנול", the system should:
1. Detect the topic using synonyms (before embeddings)
2. Map to the canonical service_type from the topic
3. Send the canonical value in webhooks (not the raw extraction)

## Changes Made

### 1. Unified Text Normalization (`server/services/topic_classifier.py`)

**New Function**: `_normalize_text_for_matching(text: str) -> str`

Purpose: Single source of truth for text normalization in topic classification.

Behavior:
- Removes Hebrew niqqud (vowel marks: U+0591-U+05C7)
- Removes punctuation and special characters
- Normalizes whitespace
- Converts to lowercase (casefold)

Example:
```python
"התקנת מנול." → "התקנת מנול"
"פריצת מנעול!" → "פריצת מנעול"
```

### 2. Layer 1 Synonym Matching Enhancement

**Before**: 
- Used simple `.lower()` and exact string matching
- Missed variations with nikud/punctuation

**After**:
- Uses `_normalize_text_for_matching()` on both text and synonyms
- Uses `contains` check (not exact match)
- Example: synonym "מנול" now catches:
  - "התקנת מנול."
  - "מנול בבית"
  - "צריך מנול"

**Code Location**: `_keyword_match()` method in TopicClassifier

### 3. Topic→Service Canonicalization (`server/tasks_recording.py`)

**Enhancement**: Apply final canonicalization when mapping topic to service_type

**Before**:
```python
lead.service_type = topic.canonical_service_type
```

**After**:
```python
canonical_value = canonicalize_service(topic.canonical_service_type, business_id)
lead.service_type = canonical_value
```

**Impact**: Ensures absolute consistency even if topic.canonical_service_type has slight variations

**Code Location**: Line ~810 in post-call processing

### 4. Webhook Canonical Value Priority (`server/tasks_recording.py`)

**Enhancement**: Always send canonical value in webhooks

**Priority Order**:
1. `lead.service_type` (after canonicalization) - PRIMARY
2. `topic.canonical_service_type` (if lead.service_type is empty) - FALLBACK
3. Never send raw extraction if canonical exists

**Code Location**: Line ~540-558 in webhook preparation

**Webhook Payload Fields**:
- `service_category`: Raw extraction (for backward compatibility)
- `service_category_canonical`: ✅ Canonical value
- `service_type_canonical`: ✅ Canonical value (alias)

## Flow Diagram

```
User says: "התקנת מנול"
         ↓
[Layer 1] Normalize text → "התקנת מנול"
         ↓
[Layer 1] Check synonyms (normalized) → MATCH! synonym="מנול"
         ↓
[Topic Selected] topic_id=X, topic_name="מנעולן"
         ↓
[Map to Service] topic.canonical_service_type="מנעולן"
         ↓
[Canonicalize] canonicalize_service("מנעולן") → "מנעולן"
         ↓
[Update Lead] lead.service_type = "מנעולן"
         ↓
[Webhook] service_category_canonical = "מנעולן" ✅
```

## Testing

### Manual Test Case

**Input**: Call with text "התקנת מנול" or "פריצת מנעול"

**Expected Results**:
1. ✅ Topic detected via Layer 1 (synonym match)
2. ✅ `lead.service_type` = "מנעולן"
3. ✅ Webhook `service_category_canonical` = "מנעולן"
4. ✅ No raw value like "פריצת מנעול" in webhook

**Verification**:
```bash
# Check logs for:
🎯 SYNONYM MATCH: 'מנול' (normalized: 'מנול') → topic: מנעולן
[TOPIC→SERVICE] Mapped topic X to service_type 'מנעולן'
[WEBHOOK] Using canonical service_type from lead: 'מנעולן'
```

### Edge Cases Handled

1. **Synonym with punctuation**: "מנול." → normalized to "מנול" → MATCH ✅
2. **Synonym with nikud**: "מָנוֹל" → normalized to "מנול" → MATCH ✅
3. **Empty lead.service_type**: Falls back to topic.canonical_service_type ✅
4. **No canonical mapping**: Keeps original value (no breaking change) ✅

## Configuration

**No new configuration needed!** The system uses existing data:
- `BusinessTopic.synonyms` (already in DB)
- `BusinessTopic.canonical_service_type` (already in DB)
- `SERVICE_CANONICALIZATION_MAP` (existing mapping)

## Backward Compatibility

- ✅ Existing synonyms continue to work
- ✅ Embedding-based matching (Layer 2) unchanged
- ✅ Webhooks include both raw and canonical values
- ✅ No breaking changes to existing integrations

## Performance Impact

- ✅ Layer 1 (keyword/synonym) remains free and instant
- ✅ Text normalization is lightweight (regex + string ops)
- ✅ No additional DB queries
- ✅ Canonical mapping uses existing function

## Files Modified

1. **`server/services/topic_classifier.py`**
   - Added `_normalize_text_for_matching()` function
   - Updated `_keyword_match()` to use normalized text
   - Added `canonical_service_type` to topic data structure

2. **`server/tasks_recording.py`**
   - Updated topic→service mapping to apply `canonicalize_service()`
   - Enhanced webhook preparation with fallback logic
   - Added debug logging for canonical values

## Success Criteria

✅ Text normalization removes niqqud/punctuation consistently
✅ Synonyms match even with variations ("מנול" catches "התקנת מנול.")
✅ Topic→Service mapping applies final canonicalization
✅ Webhook always sends canonical value (never raw if canonical exists)
✅ No hardcoded values added
✅ Uses existing DB data (synonyms, canonical_service_type)

## Deployment Notes

1. **No migration needed** - uses existing DB schema
2. **No configuration changes** - works with existing settings
3. **Safe to deploy** - backward compatible
4. **Monitoring**: Watch for `[TOPIC→SERVICE]` and `[WEBHOOK]` logs

## Related Documentation

- Service Canonicalization: `SERVICE_CANONICALIZATION_MAP` in `lead_extraction_service.py`
- Topic Classification: `topic_classifier.py` 
- Webhook Service: `generic_webhook_service.py`
