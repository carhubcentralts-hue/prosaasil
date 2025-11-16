# 🔧 Realtime API Errors Fixed

## Critical Errors Found

When testing the Realtime API, two critical errors appeared:

```
❌ [REALTIME] Error event: Unknown parameter: 'session.max_output_tokens'.
❌ [REALTIME] Error event: Invalid value: 'input_text'. Value must be 'text'.
```

These errors caused:
- **Silent audio** (no sound on calls)
- **Spanish responses** instead of Hebrew
- Broken greeting delivery

## Root Causes

### 1. Wrong Parameter Name
**Error:** `Unknown parameter: 'session.max_output_tokens'`

OpenAI Realtime API uses `max_response_output_tokens`, not `max_output_tokens`.

### 2. Wrong Content Type
**Error:** `Invalid value: 'input_text'. Value must be 'text'`

When creating conversation items, the content type must be `"text"`, not `"input_text"`.

## Fixes Applied

### Fix 1: Parameter Name (openai_realtime_client.py)

**Before:**
```python
session_config = {
    ...
    "max_output_tokens": max_tokens
}
```

**After:**
```python
session_config = {
    ...
    "max_response_output_tokens": max_tokens
}
```

### Fix 2: Content Type (openai_realtime_client.py)

**Before:**
```python
await self.send_event({
    "type": "conversation.item.create",
    "item": {
        "type": "message",
        "role": "assistant",
        "content": [{
            "type": "input_text",  # ❌ WRONG
            "text": text
        }]
    }
})
```

**After:**
```python
await self.send_event({
    "type": "conversation.item.create",
    "item": {
        "type": "message",
        "role": "assistant",
        "content": [{
            "type": "text",  # ✅ CORRECT
            "text": text
        }]
    }
})
```

### Fix 3: Added Debugging Logs

Added prompt preview logging to verify Hebrew instructions are sent:

```python
print(f"📝 [REALTIME] Prompt preview: {system_prompt[:200]}...")
print(f"✅ [REALTIME] Session configured with voice=alloy, temp=0.15, max_tokens=60")
```

## Expected Behavior After Fixes

### Good Logs:
```
✅ [REALTIME] Connected to OpenAI
✅ [REALTIME] Built system prompt (6980 chars)
📝 [REALTIME] Prompt preview: אתה נציג טלפוני אנושי ומקצועי...
✅ [REALTIME] Session configured with voice=alloy, temp=0.15, max_tokens=60
✅ [REALTIME] Greeting sent successfully
🤖 [REALTIME] AI said: היי! איך אוכל לעזור?  ← HEBREW, not Spanish!
```

### Bad Logs (Before Fix):
```
❌ [REALTIME] Error event: Unknown parameter...
❌ [REALTIME] Error event: Invalid value...
🤖 [REALTIME] AI said: ¡Hola! ¿Cómo te va?  ← Spanish!
```

## Files Modified

1. `server/services/openai_realtime_client.py`
   - `send_text_response()` - Fixed content type: `input_text` → `text`
   - `configure_session()` - Fixed parameter: `max_output_tokens` → `max_response_output_tokens`

2. `server/media_ws_ai.py`
   - Added prompt preview logging for debugging

## Testing

After these fixes:
1. Make a test call
2. Check logs for NO error messages
3. Verify AI responds in Hebrew
4. Listen for clear audio (not silence)

## References

- [OpenAI Realtime API Docs](https://platform.openai.com/docs/guides/realtime)
- Valid content types: `"text"`, `"audio"`, `"input_audio"`
- Valid session parameters: `max_response_output_tokens` (not `max_output_tokens`)
