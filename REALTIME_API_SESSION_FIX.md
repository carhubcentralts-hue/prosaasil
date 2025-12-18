# OpenAI Realtime API Session Configuration Fix

## Problem Summary

The "vacuum cleaner" audio noise on Twilio calls was caused by a misconfiguration in the OpenAI Realtime API session setup.

### Root Cause

**Line 385 in `server/services/openai_realtime_client.py`:**
```python
# ❌ WRONG - String format (caused session.update to fail)
session_config["input_audio_noise_reduction"] = "speech"
```

This caused the following error from OpenAI:
```
Invalid type for 'session.input_audio_noise_reduction': expected an object, but got a string instead.
```

### Impact

When `session.update` fails:
1. ❌ Session uses **default settings** (not configured settings)
2. ❌ `output_audio_format` = **PCM16** (instead of G.711 μ-law)
3. ❌ Twilio receives PCM16 but expects G.711 → **"vacuum cleaner" noise**
4. ❌ `instructions` not applied → **AI speaks English** (not Hebrew)
5. ❌ Voice settings not applied → wrong voice

## Solution

### 1. Fix `input_audio_noise_reduction` Format

**File:** `server/services/openai_realtime_client.py`

```python
# ✅ CORRECT - Object format with "type" field
session_config["input_audio_noise_reduction"] = {"type": "near_field"}
```

Per OpenAI Realtime API specification, `input_audio_noise_reduction` must be an **object** with a `type` field:
- `"near_field"` - Optimized for phone calls and close microphones
- `"far_field"` - Optimized for distant speakers (not relevant for phone calls)

### 2. Add Session Configuration Validation

**File:** `server/media_ws_ai.py`

Added event handling to validate `session.updated` confirmation:

```python
# Validate session.updated received
if event_type == "session.updated":
    _orig_print(f"✅ [SESSION] session.updated received - configuration applied successfully!", flush=True)
    
    # Validate audio formats
    session_data = event.get("session", {})
    output_format = session_data.get("output_audio_format", "unknown")
    
    # Assert correct format
    if output_format != "g711_ulaw":
        _orig_print(f"🚨 [SESSION ERROR] Wrong output format! Expected g711_ulaw, got {output_format}", flush=True)
```

Added error detection for session configuration failures:

```python
# Detect session.update errors
if event_type == "error":
    error_msg = error.get("message", "")
    
    if "session" in error_msg.lower():
        _orig_print(f"🚨 [SESSION ERROR] session.update FAILED! Error: {error_msg}", flush=True)
        _orig_print(f"🚨 [SESSION ERROR] This will cause audio noise and wrong language!", flush=True)
```

## Correct Session Configuration

The complete `session.update` payload now looks like this:

```json
{
  "type": "session.update",
  "session": {
    "modalities": ["audio", "text"],
    "instructions": "...(Hebrew prompt)...",
    "input_audio_format": "g711_ulaw",
    "output_audio_format": "g711_ulaw",
    "input_audio_transcription": {
      "model": "gpt-4o-transcribe",
      "language": "he",
      "prompt": "...(transcription prompt)..."
    },
    "turn_detection": {
      "type": "server_vad",
      "threshold": 0.5,
      "prefix_padding_ms": 300,
      "silence_duration_ms": 500,
      "create_response": true
    },
    "input_audio_noise_reduction": {
      "type": "near_field"
    },
    "temperature": 0.6,
    "max_response_output_tokens": 300
  }
}
```

## Verification

### Expected Logs (Success)

When session configuration succeeds, you should see:

```
✅ [SESSION] session.updated received - configuration applied successfully!
✅ [SESSION] Confirmed settings: input=g711_ulaw, output=g711_ulaw, voice=ash
```

### Error Logs (Failure)

If session configuration fails, you will see:

```
🚨 [SESSION ERROR] session.update FAILED! Error: Invalid type for 'session.input_audio_noise_reduction': expected an object, but got a string instead.
🚨 [SESSION ERROR] Session will use DEFAULT settings (PCM16, English, no instructions)
🚨 [SESSION ERROR] This will cause audio noise and wrong language!
```

## Testing

To verify the fix works:

1. **Make a test call** to your Twilio number
2. **Check logs** for `✅ [SESSION] session.updated received`
3. **Verify audio quality** - should be clear (no "vacuum cleaner" noise)
4. **Verify language** - AI should speak Hebrew (not English)
5. **Verify instructions** - AI should follow business prompt

## Files Changed

1. **`server/services/openai_realtime_client.py`**
   - Fixed `input_audio_noise_reduction` format (line 443)
   - Added session validation helper method
   - Added warning log after sending session.update

2. **`server/media_ws_ai.py`**
   - Added `session.updated` event handler (lines 3540-3563)
   - Added `error` event validation for session errors (lines 3522-3537)
   - Added state tracking flags: `_session_config_confirmed`, `_session_config_failed`

## References

- [OpenAI Realtime API Documentation](https://platform.openai.com/docs/guides/realtime)
- [Twilio Media Streams Format: G.711 μ-law](https://www.twilio.com/docs/voice/twiml/stream#message-media)
- Problem statement (Hebrew): See issue description

## Credits

Fix implemented based on detailed analysis from problem statement which correctly identified:
1. The exact error: "expected an object, but got a string"
2. The root cause: Wrong `input_audio_noise_reduction` format
3. The impact: PCM16 vs G.711 mismatch causing noise
4. The solution: Use `{"type": "near_field"}` object format
