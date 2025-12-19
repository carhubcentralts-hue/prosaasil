# Realtime API Hebrew Call Quality Improvements

## סיכום התיקונים - Hebrew Summary

תיקונים שבוצעו על פי ההנחיה הממוקדת לשיפור איכות שיחות בעברית:

### 1. ✅ הגדרת Realtime API נכונה
**מה תוקן:**
- `turn_detection.type = "server_vad"` - שימוש ב-VAD של OpenAI
- `turn_detection.create_response = true` - יצירה אוטומטית של תגובות
- ערכים יציבים: threshold=0.50, prefix_padding_ms=300, silence_duration_ms=500
- הוספת `input_audio_noise_reduction = "speech"` (ניסיוני)

**מיקום:** `server/services/openai_realtime_client.py:365-372`

### 2. ✅ Barge-in יציב
**מה תוקן:**
- הוספת דגל `ai_response_active=True` מיד ב-`response.created`
- ביטול רק כאשר: `active_response_id קיים AND (ai_response_active OR is_ai_speaking)`
- ניקוי נכון של כל הדגלים ב-`response.done` ו-`response.cancelled`
- **הסרת** לוגיקת הגנת ברכה מיוחדת - הברכה היא פשוט התגובה הראשונה

**מיקום:** 
- `server/media_ws_ai.py:3774-3786` - הגדרת ai_response_active
- `server/media_ws_ai.py:3618-3670` - לוגיקת barge-in מחודשת

### 3. ✅ תמלול יציב
**מה נבדק:**
- `is_valid_transcript()` כבר מקבל הכל מלבד ריק
- `should_accept_realtime_utterance()` כבר מקבל הכל
- ביטויים קצרים (כן/לא/מה/מי/רגע/הלו) עוברים ללא סינון

**מיקום:** `server/media_ws_ai.py:1219-1269`

### 4. ✅ לוגים אבחנתיים לצנרת TX
**מה נוסף:**
- לוג של `audio.delta` עם כמות בייטים ו-response_id
- לוג מלא כאשר `frames_sent==0` עם snapshot של:
  - streamSid
  - tx_queue_size
  - realtime_audio_out_queue_size
  - active_response_id
  - ai_response_active
  - is_ai_speaking
  - status
  - duration_ms

**מיקום:** 
- `server/media_ws_ai.py:3776-3782` - לוג audio.delta
- `server/media_ws_ai.py:3302-3322` - לוג frames_sent==0

### 5. ✅ ניתוק שיחה אמיתי
**מה נבדק:**
- `_check_goodbye_phrases()` - זיהוי ביטויי פרידה
- `_trigger_auto_hangup()` - קריאה ל-Twilio REST API
- `client.calls(call_sid).update(status='completed')` - ניתוק אמיתי

**מיקום:** `server/media_ws_ai.py:9682`

---

## English Summary

### Changes Made Per Requirements (הנחיה ממוקדת לסוכן)

#### 1. ✅ Realtime Session Configuration (Requirement 2)
**What was fixed:**
- Added `create_response: true` to turn_detection config
- Stable VAD thresholds: threshold=0.50 (not aggressive), silence_duration_ms=500 (stable in light noise), prefix_padding_ms=300
- Added experimental `input_audio_noise_reduction` for server-side noise reduction

**File:** `server/services/openai_realtime_client.py`

**Code change:**
```python
"turn_detection": {
    "type": "server_vad",
    "threshold": vad_threshold,  # 0.50 - stable, not aggressive
    "prefix_padding_ms": prefix_padding_ms,  # 300ms
    "silence_duration_ms": silence_duration_ms,  # 500ms - stable in light noise
    "create_response": True  # ✅ CRITICAL: Auto-create response on turn end
}
```

#### 2. ✅ Barge-In Stability (Requirement 4)
**What was fixed:**
- Added `ai_response_active` flag set on `response.created` (not audio.delta)
- Barge-in cancels only when: `active_response_id` exists AND (`ai_response_active` OR `is_ai_speaking`)
- Proper state cleanup on `response.done` and `response.cancelled`
- **Removed** special greeting protection logic - greeting is just first response

**Files:** `server/media_ws_ai.py`

**Key changes:**
1. Set `ai_response_active=True` on `response.created`:
```python
if response_id:
    self.active_response_id = response_id
    self.response_pending_event.clear()
    self.ai_response_active = True  # ✅ NEW: Enable cancellation immediately
```

2. Updated barge-in condition:
```python
has_active_response = bool(self.active_response_id)
ai_can_be_cancelled = getattr(self, 'ai_response_active', False) or self.is_ai_speaking_event.is_set()

if has_active_response and ai_can_be_cancelled and self.realtime_client:
    # Cancel, clear, flush
```

3. Clear all flags on response.done:
```python
self.active_response_id = None
self.is_ai_speaking_event.clear()
self.speaking = False
if hasattr(self, 'ai_response_active'):
    self.ai_response_active = False
```

#### 3. ✅ Transcription Quality (Requirement 3)
**What was verified:**
- `is_valid_transcript()` already accepts all non-empty transcripts
- `should_accept_realtime_utterance()` already has "NO FILTERS" mode
- Short Hebrew phrases (כן/לא/מה/מי/רגע/הלו) pass without filtering
- Only completely empty text is rejected

**File:** `server/media_ws_ai.py:1219-1269`

**No changes needed** - already correct per requirements.

#### 4. ✅ TX Pipeline Diagnostics (Requirement 5)
**What was added:**
- Log every `response.audio.delta` with bytes count and response_id
- Comprehensive diagnostic snapshot when `frames_sent==0`:
  - streamSid existence
  - tx_queue size
  - realtime_audio_out_queue size
  - active_response_id
  - ai_response_active flag
  - is_ai_speaking state
  - response status
  - response duration

**File:** `server/media_ws_ai.py`

**Code additions:**
```python
# On audio.delta:
_orig_print(f"📥 [AUDIO_DELTA] response_id={response_id[:20]}..., bytes={len(audio_bytes)}, base64_len={len(audio_b64)}", flush=True)

# On response.done with frames_sent==0:
if frames_sent == 0:
    _orig_print(f"⚠️ [TX_DIAG] frames_sent=0 for response {resp_id[:20]}...", flush=True)
    _orig_print(f"   SNAPSHOT:", flush=True)
    _orig_print(f"   - streamSid: {self.stream_sid}", flush=True)
    # ... full diagnostic output
```

#### 5. ✅ Call Hangup (Requirement 6)
**What was verified:**
- Goodbye detection works via `_check_goodbye_phrases()`
- Polite response sent via AI instruction
- **Actual Twilio hangup** via REST API: `client.calls(call_sid).update(status='completed')`
- State reset prevents re-initialization

**File:** `server/media_ws_ai.py:9682`

**No changes needed** - already implements actual hangup via Twilio REST API.

---

## Testing Checklist (Requirement 7)

### 7.1 ✅ No `response_cancel_not_active` errors
**Expected behavior:**
- `ai_response_active` flag set on `response.created` prevents cancelling inactive responses
- Should see log: `⚠️ [BARGE-IN] response_cancel_not_active (should be rare now)`

**How to verify:**
```bash
# Check logs for response_cancel_not_active errors
grep -i "response_cancel_not_active" /path/to/logs
# Should be rare or zero after fix
```

### 7.2 ✅ Barge-in sequence
**Expected sequence in logs:**
1. `🎤 [SPEECH_STARTED] User started speaking`
2. `✅ [BARGE-IN] Cancelled response {response_id}...`
3. `🧹 [BARGE-IN] Sent Twilio clear event`
4. `🧹 [BARGE-IN FLUSH] Cleared X frames total`

**How to verify:**
```bash
# Check for complete barge-in sequence
grep -A 5 "SPEECH_STARTED" /path/to/logs | grep -E "(Cancelled response|Twilio clear|FLUSH)"
```

### 7.3 ✅ Greeting frames_sent > 0
**Expected behavior:**
- First `response.audio.delta` logs bytes received
- TX loop logs frames sent
- `response.done` shows `frames_sent > 0`

**How to verify:**
```bash
# Check greeting audio pipeline
grep -E "(AUDIO_DELTA|TX_RESPONSE)" /path/to/logs | head -20
# Should see audio.delta followed by TX_RESPONSE with frames_sent > 0
```

### 7.4 ✅ Short phrases pass
**Expected behavior:**
- Transcriptions like "כן", "לא", "מה", "מי", "רגע", "הלו" generate AI responses
- No rejection logs for short valid Hebrew phrases

**How to verify:**
```bash
# Check for transcription acceptance
grep -E "(כן|לא|מה|מי|רגע|הלו)" /path/to/logs
# Should see these trigger AI responses, not rejections
```

### 7.5 ✅ Session config
**Expected log:**
```
✅ Session configured: voice=coral, format=g711_ulaw, vad_threshold=0.5, transcription=gpt-4o-transcribe
```

**How to verify:**
```bash
grep "Session configured" /path/to/logs
# Should show vad_threshold=0.5, create_response in turn_detection
```

### 7.6 ✅ Actual hangup
**Expected behavior:**
- Goodbye detected: `👋 [BUILD 170.5] User said goodbye`
- Twilio API call: `✅ [BUILD 163] Call {call_sid}... hung up successfully`
- Call ends via `status='completed'` update

**How to verify:**
```bash
# Check hangup sequence
grep -E "(User said goodbye|hung up successfully)" /path/to/logs
# Should see Twilio API call completing the call
```

---

## Configuration Values

### Realtime VAD (per הנחיה)
```python
SERVER_VAD_THRESHOLD = 0.50         # Stable, not aggressive
SERVER_VAD_SILENCE_MS = 500         # Stable for light noise
SERVER_VAD_PREFIX_PADDING_MS = 300  # Standard padding
```

**File:** `server/config/calls.py:62-64`

### What Changed vs. What Stayed
**Changed:**
- silence_duration_ms: 450ms → 500ms (more stable in light noise)

**Stayed same:**
- threshold: 0.50 (already correct)
- prefix_padding_ms: 300ms (already correct, changed from 350ms back to 300ms)

---

## Critical Notes

### What Was NOT Changed (Already Correct)
1. **Greeting via prompt** - Already sent via system prompt, not special UI layer
2. **TX loop timing** - Already starts before first response
3. **streamSid validation** - Already checked before enqueue
4. **Short phrase acceptance** - Already implemented via `is_valid_transcript()`
5. **Hangup implementation** - Already uses Twilio REST API `update(status='completed')`

### What Was Removed
1. **Greeting protection logic** - Removed special case handling during greeting
2. **is_playing_greeting checks in barge-in** - Greeting treated as normal response

### What Was Added
1. **ai_response_active flag** - Tracks response lifecycle for barge-in
2. **TX diagnostic logging** - Full snapshot on frames_sent==0
3. **create_response: true** - Automatic response generation
4. **input_audio_noise_reduction** - Experimental server-side noise reduction

---

## Files Modified

1. **server/config/calls.py**
   - Updated VAD comment and silence_duration_ms value
   
2. **server/services/openai_realtime_client.py**
   - Added `create_response: true` to turn_detection
   - Added `input_audio_noise_reduction` (experimental)

3. **server/media_ws_ai.py**
   - Added `ai_response_active` flag management
   - Updated barge-in cancellation logic
   - Removed greeting-specific protection from speech_started
   - Added TX diagnostic logging
   - Enhanced frames_sent==0 diagnostic output

---

## Summary

All requirements from the הנחיה ממוקדת לסוכן have been implemented:

✅ **Requirement 1** - No greeting UI layer (verified already correct)  
✅ **Requirement 2** - Realtime session config (server_vad + create_response + stable VAD)  
✅ **Requirement 3** - Transcription quality (verified already correct)  
✅ **Requirement 4** - Stable barge-in (ai_response_active flag)  
✅ **Requirement 5** - TX pipeline diagnostics  
✅ **Requirement 6** - Actual call hangup (verified already correct)  
✅ **Requirement 7** - Testing checklist provided above

The implementation is **minimal and surgical** - only the necessary changes were made, leveraging existing correct code where possible.
