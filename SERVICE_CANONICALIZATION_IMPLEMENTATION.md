# Service Canonicalization and Topic-to-Service Mapping - Implementation Summary

## Overview

This implementation adds a normalization layer for service categories and enables topic-based service_type mapping based on embedding classification results.

## Problem Solved

### Before:
- LLM extraction returned raw service mentions: "פריצת מנעול", "פריצת דלת", "החלפת צילינדר"
- Each variation created a different `lead.service_type` value
- Database had fragmented service categories
- Topic classification only set `detected_topic_id`, not `service_type`

### After:
- All locksmith services → normalized to "מנעולן"
- Consistent `service_type` values in database
- Topic classification can also set `service_type` based on confidence
- Two-layer approach: LLM extraction + Topic classification

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Call Ends                                 │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────┐
│              Whisper Transcription                               │
│              (final_transcript)                                  │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ├─────────────────┬──────────────────────────────┐
                  │                 │                              │
                  ▼                 ▼                              ▼
        ┌─────────────────┐ ┌──────────────┐         ┌─────────────────────┐
        │  LLM Extraction │ │   Summary    │         │ Topic Classification│
        │   (OpenAI)      │ │  Generation  │         │   (Embeddings)      │
        └────────┬────────┘ └──────────────┘         └──────────┬──────────┘
                 │                                                 │
                 │ extracted_service="פריצת מנעול"                │ topic="locksmith"
                 │                                                 │ confidence=0.89
                 ▼                                                 │
        ┌─────────────────────────────┐                          │
        │  canonicalize_service()     │                          │
        │  "פריצת מנעול" → "מנעולן"   │                          │
        └────────┬────────────────────┘                          │
                 │                                                 │
                 │ canonical_service="מנעולן"                     │
                 │                                                 │
                 ├─────────────────────────────────────────────────┤
                 │                                                 │
                 ▼                                                 ▼
        ┌──────────────────────────────────────────────────────────┐
        │            Update lead.service_type                       │
        │                                                           │
        │  Priority:                                                │
        │  1. Topic mapping (if enabled & confidence ≥ 0.75)        │
        │  2. Canonicalized LLM extraction                          │
        └───────────────────────────────────────────────────────────┘
```

## Components

### 1. Service Canonicalization Map

**File**: `server/services/lead_extraction_service.py`

```python
SERVICE_CANONICALIZATION_MAP = {
    # Locksmith services → "מנעולן"
    "פריצת מנעול": "מנעולן",
    "פריצת דלת": "מנעולן",
    "החלפת צילינדר": "מנעולן",
    "תיקון מנעול": "מנעולן",
    "תיקון מנעול חכם": "מנעולן",
    "פורץ מנעולים": "מנעולן",
    
    # Electrician services → "חשמלאי"
    "תיקון חשמל": "חשמלאי",
    "התקנת גוף תאורה": "חשמלאי",
    
    # Plumber services → "שרברב"
    "תיקון צינור": "שרברב",
    "פתיחת סתימה": "שרברב",
    "אינסטלטור": "שרברב",
    
    # Cleaning services → "נקיון"
    "ניקיון דירה": "נקיון",
    "ניקיון משרדים": "נקיון",
}
```

### 2. Canonicalization Function

```python
def canonicalize_service(service_category: str, business_id: int = None) -> str:
    """
    Normalize service category to canonical form.
    
    Examples:
    - "פריצת מנעול" → "מנעולן"
    - "תיקון חשמל" → "חשמלאי"
    
    Returns:
    - Canonical service if mapping exists
    - Original value if no mapping found (allows new services)
    """
```

**Matching Logic**:
1. Exact match (case-insensitive)
2. Partial match (substring search)
3. No match → return original

### 3. Database Schema

#### BusinessTopic (New Field)
```sql
ALTER TABLE business_topics 
ADD COLUMN canonical_service_type VARCHAR(255);
```

**Usage**: Maps topic to service_type
- Topic "locksmith_emergency" → `canonical_service_type = "מנעולן"`
- Topic "electrical_fault" → `canonical_service_type = "חשמלאי"`

#### BusinessAISettings (New Fields)
```sql
ALTER TABLE business_ai_settings 
ADD COLUMN map_topic_to_service_type BOOLEAN DEFAULT FALSE,
ADD COLUMN service_type_min_confidence FLOAT DEFAULT 0.75;
```

**Settings**:
- `map_topic_to_service_type`: Enable topic-to-service mapping
- `service_type_min_confidence`: Minimum confidence threshold (default 0.75)

### 4. Integration Points

#### A. LLM Extraction Path

**File**: `server/tasks_recording.py` (lines 828-835)

```python
if update_service:
    # 🔥 Canonicalize service category before saving
    from server.services.lead_extraction_service import canonicalize_service
    canonical_service = canonicalize_service(extracted_service, call_log.business_id)
    lead.service_type = canonical_service
    log.info(f"[OFFLINE_EXTRACT] ✅ Updated lead {lead.id} service_type: '{extracted_service}' → '{canonical_service}'")
```

#### B. Topic Classification Path

**File**: `server/tasks_recording.py` (lines 728-752)

```python
# After tagging lead with detected_topic_id
if ai_settings.map_topic_to_service_type and confidence >= ai_settings.service_type_min_confidence:
    topic = BusinessTopic.query.get(topic_id)
    if topic and topic.canonical_service_type:
        # Only update if empty or high confidence
        if not lead.service_type or confidence >= 0.85:
            old_service_type = lead.service_type
            lead.service_type = topic.canonical_service_type
            print(f"[TOPIC_CLASSIFY] ✅ Mapped topic '{topic.name}' to service_type: '{old_service_type}' → '{topic.canonical_service_type}'")
```

## Configuration

### Enable Topic-to-Service Mapping

```sql
-- For a specific business
UPDATE business_ai_settings 
SET map_topic_to_service_type = TRUE,
    service_type_min_confidence = 0.75  -- Adjust threshold as needed
WHERE business_id = 1;
```

### Configure Topic Mappings

```sql
-- Set canonical service type for topics
UPDATE business_topics 
SET canonical_service_type = 'מנעולן' 
WHERE business_id = 1 
  AND name IN ('פורץ מנעולים', 'locksmith_emergency', 'door_break_in');

UPDATE business_topics 
SET canonical_service_type = 'חשמלאי' 
WHERE business_id = 1 
  AND name IN ('electrical_issue', 'power_fault');
```

## Decision Logic

### When is service_type updated?

#### From LLM Extraction:
1. Lead has no `service_type` → Always update with canonicalized value
2. Lead has `service_type` + extraction confidence > 0.8 → Overwrite with canonicalized value

#### From Topic Classification:
1. **Mapping enabled** (`map_topic_to_service_type = TRUE`)
2. **Confidence threshold met** (confidence ≥ `service_type_min_confidence`)
3. **Topic has mapping** (`canonical_service_type` is not NULL)
4. **Lead condition**: Either empty OR confidence ≥ 0.85

### Priority Order:
1. **Topic mapping** (if enabled and confidence ≥ threshold)
2. **Canonicalized LLM extraction** (if extraction succeeded)
3. **Existing value** (if no updates triggered)

## Logging

### Canonicalization Logs
```
[CANONICALIZE] 'פריצת מנעול' → 'מנעולן' (exact match)
[CANONICALIZE] 'תיקון מנעול חכם' → 'מנעולן' (partial match: 'תיקון מנעול')
[CANONICALIZE] 'שירות חדש' → no mapping found, keeping original
```

### Topic Mapping Logs
```
[TOPIC_CLASSIFY] ✅ Detected topic: 'פורץ מנעולים' (confidence=0.89, method=embedding)
[TOPIC_CLASSIFY] ✅ Tagged lead 123 with topic 45
[TOPIC_CLASSIFY] ✅ Mapped topic 'פורץ מנעולים' to service_type: 'None' → 'מנעולן' (confidence=0.890)
```

### Extraction Logs
```
[OFFLINE_EXTRACT] Lead 123 service_type is empty, will update
[OFFLINE_EXTRACT] ✅ Updated lead 123 service_type: 'פריצת מנעול' → 'מנעולן'
```

## Testing

### 1. Test Canonicalization
```python
from server.services.lead_extraction_service import canonicalize_service

# Test exact match
assert canonicalize_service("פריצת מנעול") == "מנעולן"

# Test partial match
assert canonicalize_service("צריך תיקון מנעול דחוף") == "מנעולן"

# Test no match (preserves original)
assert canonicalize_service("שירות מיוחד") == "שירות מיוחד"
```

### 2. Test Topic Mapping
```sql
-- Enable for test business
UPDATE business_ai_settings 
SET map_topic_to_service_type = TRUE,
    embedding_enabled = TRUE,
    service_type_min_confidence = 0.75
WHERE business_id = 1;

-- Configure topic
UPDATE business_topics 
SET canonical_service_type = 'מנעולן' 
WHERE business_id = 1 AND name = 'locksmith_test';
```

Then make a call and check logs for:
```
[TOPIC_CLASSIFY] ✅ Mapped topic 'locksmith_test' to service_type: 'None' → 'מנעולן'
```

### 3. Verify Database
```sql
-- Check leads have canonical service types
SELECT id, service_type, detected_topic_id, detected_topic_confidence
FROM leads
WHERE service_type = 'מנעולן'
ORDER BY id DESC
LIMIT 10;

-- Check topic mappings
SELECT id, name, canonical_service_type, is_active
FROM business_topics
WHERE business_id = 1 AND canonical_service_type IS NOT NULL;
```

## Migration

**Migration 43** adds the new fields:
```sql
ALTER TABLE business_topics 
ADD COLUMN canonical_service_type VARCHAR(255);

ALTER TABLE business_ai_settings 
ADD COLUMN map_topic_to_service_type BOOLEAN DEFAULT FALSE,
ADD COLUMN service_type_min_confidence FLOAT DEFAULT 0.75;
```

**Run migration**:
```bash
python -m server.db_migrate
```

## Transcript and Summary Display

### No Changes Required! ✅

The transcript and summary display logic was **not modified** and continues to work correctly:

1. **API Response** (`server/routes_calls.py`):
   - Prefers `final_transcript` (from recording) over `transcription` (realtime)
   - Returns both fields to UI

2. **Webhook** (`server/tasks_recording.py` line 525):
   - Uses `final_transcript or transcription or ""`
   - Prioritizes offline high-quality transcript

3. **Database Storage**:
   - `call_log.final_transcript` - Whisper transcription from recording
   - `call_log.transcription` - Realtime Google STT (fallback)
   - `call_log.summary` - AI-generated summary

### Verification
```python
# Check that final_transcript is saved
SELECT call_sid, 
       LENGTH(final_transcript) as transcript_len,
       LENGTH(summary) as summary_len,
       transcript_source
FROM call_log
WHERE final_transcript IS NOT NULL
ORDER BY created_at DESC
LIMIT 5;
```

Expected logs after call processing:
```
[OFFLINE_STT] ✅ Saved final_transcript (1234 chars) for CAxxxxx
[OFFLINE_STT] ✅ Extracted: service='פריצת מנעול', city='תל אביב', confidence=0.92
[OFFLINE_EXTRACT] ✅ Updated lead 123 service_type: 'פריצת מנעול' → 'מנעולן'
[TOPIC_CLASSIFY] ✅ Detected topic: 'locksmith_emergency' (confidence=0.89, method=embedding)
[TOPIC_CLASSIFY] ✅ Mapped topic 'locksmith_emergency' to service_type: 'מנעולן' → 'מנעולן'
```

## Benefits

1. **Consistent Data**: All locksmith services normalized to "מנעולן"
2. **Flexible**: New services without mappings are preserved
3. **Configurable**: Per-business settings
4. **Two Sources**: Both LLM extraction and embeddings can set service_type
5. **Safe**: Confidence thresholds prevent incorrect overrides
6. **Debuggable**: Comprehensive logging at every step
7. **No Breaking Changes**: Transcript/summary display unchanged

## Future Enhancements

1. **UI for Mapping Management**: Admin interface to configure mappings
2. **Business-Specific Mappings**: Override global mappings per business
3. **Analytics**: Report on service distribution before/after canonicalization
4. **Auto-Learning**: Suggest new mappings based on frequency
