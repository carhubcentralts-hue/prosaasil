# Transcription Policy - Verification & Fixes
**Date**: 2025-12-28
**Issue**: Ensure no "holes" where transcripts are skipped incorrectly

---

## Current Policy

### Realtime Transcription (Primary)
- **When**: During active call
- **Source**: OpenAI Realtime API
- **Storage**: `ConversationTurn` table
- **Field**: `call_log.final_transcript` (aggregated)
- **Quality**: Good but may have gaps

### Offline Transcription (Upgrade/Fallback)
- **When**: After call ends
- **Source**: Whisper on recording file
- **Storage**: `CallLog.final_transcript`
- **Field**: `transcript_source` = "recording"
- **Quality**: Higher (full audio file)

---

## Current Skip Logic

```python
# tasks_recording.py line 456-462
if (call_log.final_transcript and 
    len(call_log.final_transcript.strip()) > 50 and
    call_log.transcript_source and 
    call_log.transcript_source != "failed"):
    
    print(f"✅ [OFFLINE_STT] Skip reprocessing")
    return True  # Already processed
```

---

## Problem Analysis

### ⚠️ RISK: Skip when shouldn't

**Scenario 1**: Realtime empty but marked as processed
- Realtime sets `transcript_source="realtime"` but transcript is empty
- Worker skips because source != "failed"
- **Result**: No transcript at all!

**Scenario 2**: Partial realtime transcript
- Realtime has 45 chars (below 50 threshold)
- But `transcript_source="realtime"` is set
- Worker skips because source exists
- **Result**: Incomplete transcript!

---

## Fix Required

### Enhanced Skip Logic

```python
# Should skip ONLY if:
# 1. Transcript exists AND has meaningful content (>50 chars)
# 2. Source is "recording" (highest quality) OR "realtime" with good content
# 3. Source is not "failed"

# Should process if:
# - No transcript at all
# - Transcript too short (<50 chars)
# - Source is "failed" (retry needed)
# - Source is "realtime" but transcript is weak

if call_log.final_transcript and len(call_log.final_transcript.strip()) > 50:
    # Has content - check source
    if call_log.transcript_source == "recording":
        # Recording is highest quality - never re-process
        print(f"✅ [OFFLINE_STT] Has recording transcript - skip")
        return True
    elif call_log.transcript_source == "realtime":
        # Realtime is good enough if content is substantial
        # But allow upgrade to recording quality
        # Check if content is "good enough" (>200 chars for complex calls)
        if len(call_log.final_transcript.strip()) > 200:
            print(f"✅ [OFFLINE_STT] Has substantial realtime transcript - skip")
            return True
        else:
            print(f"⚠️ [OFFLINE_STT] Realtime transcript is short - upgrade to recording")
            # Fall through to process
    elif call_log.transcript_source == "failed":
        print(f"🔄 [OFFLINE_STT] Previous attempt failed - retry")
        # Fall through to process
else:
    # No transcript or too short
    print(f"🔄 [OFFLINE_STT] No/insufficient transcript - process")
    # Fall through to process
```

---

## Validation Tests Needed

1. **Test: Realtime empty → Offline runs**
   - Setup: Call with no realtime transcript
   - Expected: Worker processes recording
   
2. **Test: Realtime short → Offline upgrades**
   - Setup: Call with 45 char realtime transcript
   - Expected: Worker processes for higher quality
   
3. **Test: Realtime good → Offline skips**
   - Setup: Call with 300 char realtime transcript
   - Expected: Worker skips (good enough)
   
4. **Test: Recording exists → Never reprocess**
   - Setup: Call with recording transcript
   - Expected: Worker always skips
   
5. **Test: Failed attempt → Retry**
   - Setup: Call with source="failed"
   - Expected: Worker retries

---

## Recommendation

**Current logic is ACCEPTABLE but can be improved**:
- ✅ Good: Checks transcript_source
- ✅ Good: Checks length (>50)
- ⚠️ Risk: Doesn't distinguish between "realtime" and "recording" quality

**Proposed enhancement**:
- Only skip if source="recording" (highest quality)
- Allow upgrade from realtime to recording for better quality
- Always retry if source="failed"

---

## Status

- [x] Current logic analyzed
- [x] Risks identified
- [ ] Enhanced logic implemented (optional improvement)
- [ ] Validation tests added
