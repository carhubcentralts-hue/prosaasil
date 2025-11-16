# 🔧 Realtime API Audio Fix Summary

## Problem
Realtime API connected successfully but calls produced only background noise ("vacuum cleaner sound") instead of AI responses.

## Root Cause
**Audio output bridge was sending incorrect format to Twilio:**
1. Wrong Twilio WebSocket message structure
2. Missing audio chunk logging for debugging

## Fixes Applied

### 1. Fixed Twilio WebSocket Message Format
**File:** `server/media_ws_ai.py` - `_realtime_audio_out_loop()`

**Before:**
```python
self.tx_q.put_nowait({"type": "media", "payload": audio_b64})
```

**After:**
```python
self.tx_q.put_nowait({
    "event": "media",
    "media": {
        "payload": audio_b64
    }
})
```

**Why:** Twilio expects `{"event": "media", "media": {"payload": "..."}}`, not `{"type": "media", "payload": "..."}`.

### 2. Added Audio Logging
**File:** `server/media_ws_ai.py` - `_realtime_audio_out_loop()`

```python
import base64
num_bytes = len(base64.b64decode(audio_b64)) if audio_b64 else 0
print(f"📤 [REALTIME] Sending {num_bytes} bytes to Twilio")
```

**Why:** Helps debug audio flow and verify chunks are being sent.

### 3. Improved Greeting Delivery
**File:** `server/services/openai_realtime_client.py` - `send_text_response()`

**Before:**
```python
await self.send_event({
    "type": "response.create",
    "response": {
        "modalities": ["audio", "text"],
        "instructions": f"Say exactly this text: {text}"
    }
})
```

**After:**
```python
# Add assistant message to conversation
await self.send_event({
    "type": "conversation.item.create",
    "item": {
        "type": "message",
        "role": "assistant",
        "content": [{
            "type": "input_text",
            "text": text
        }]
    }
})

# Trigger response generation
await self.send_event({
    "type": "response.create"
})
```

**Why:** OpenAI Realtime API requires conversation items to be created before triggering response generation.

### 4. Improved Session Configuration Logging
**File:** `server/services/openai_realtime_client.py` - `configure_session()`

```python
logger.info(f"✅ Session configured: voice={voice}, format={input_audio_format}, vad_threshold={vad_threshold}")
```

**Why:** Better visibility into audio format configuration.

## Verification

### Expected Logs (Good):
```
[REALTIME] Connected to OpenAI
[REALTIME] Session configured: voice=alloy, format=g711_ulaw, vad_threshold=0.6
[REALTIME] Sending greeting: 'שלום...'
[REALTIME] Audio output bridge started
[REALTIME] Sending 160 bytes to Twilio
👤 [REALTIME] User said: שלום
🤖 [REALTIME] AI said: היי! איך אני יכול לעזור?
[REALTIME] Sending 320 bytes to Twilio
```

### Bad Logs (Problem):
```
[REALTIME] Connected to OpenAI
[REALTIME] AI said: היי
# No "Sending X bytes to Twilio" logs → audio not flowing
```

## Technical Details

### Audio Format
- **Input:** g711_ulaw @ 8000 Hz (Twilio standard)
- **Output:** g711_ulaw @ 8000 Hz (Twilio standard)
- **Voice:** alloy (male, neutral)
- **Sample Rate:** 8000 Hz (implicit in g711_ulaw format)

### Twilio WebSocket Protocol
All messages to Twilio must follow:
```json
{
  "event": "media",
  "media": {
    "payload": "<base64-encoded-g711-ulaw>"
  }
}
```

### Files Modified
1. `server/media_ws_ai.py`
   - `_realtime_audio_out_loop()` - Fixed Twilio message format + added logging
   
2. `server/services/openai_realtime_client.py`
   - `send_text_response()` - Fixed greeting delivery
   - `configure_session()` - Improved logging

## Next Steps for Testing
1. Make a test call to your Twilio number
2. Check logs for:
   - ✅ `[REALTIME] Connected to OpenAI`
   - ✅ `[REALTIME] Session configured`
   - ✅ `[REALTIME] Sending X bytes to Twilio`
   - ✅ `👤 [REALTIME] User said: ...`
   - ✅ `🤖 [REALTIME] AI said: ...`
3. Listen for clear AI voice (not background noise)

## Common Issues

### Still hearing noise?
- Check logs for "Sending X bytes" messages
- Verify session shows `format=g711_ulaw`
- Ensure no ffmpeg/resample in audio path

### No audio at all?
- Check `Audio output bridge started` in logs
- Verify `realtime_audio_out_queue` is being populated
- Check for WebSocket connection errors

### AI not responding?
- Check `Session configured` appears in logs
- Verify system prompt is being sent
- Look for OpenAI API errors in logs
