# Before/After Conversion Examples

## Example 1: Error Messages with Emojis

### Before
```python
print(f"❌ LOGIN: User not found for email={email}")
print(f"❌ Invalid Twilio signature:")
print(f"   URL calculated: {url}")
```

### After
```python
logger.error(f"❌ LOGIN: User not found for email={email}")
logger.error(f"❌ Invalid Twilio signature:")
logger.error(f"   URL calculated: {url}")
```

## Example 2: Success Messages

### Before
```python
print(f"✅ [WA_AI_DONE] Agent response received in {ai_time:.2f}s: '{ai_response[:100]}...'")
print(f"🚀 [WA_START] Processing {len(messages)} WhatsApp messages for tenant={tenant_id}")
```

### After
```python
logger.info(f"✅ [WA_AI_DONE] Agent response received in {ai_time:.2f}s: '{ai_response[:100]}...'")
logger.info(f"🚀 [WA_START] Processing {len(messages)} WhatsApp messages for tenant={tenant_id}")
```

## Example 3: Warning Messages

### Before
```python
print("⚠️ DEV MODE: VALIDATE_TWILIO_SIGNATURE=false - signature validation skipped")
print(f"⚠️ WhatsApp thread pool full ({_active_wa_threads}/{MAX_CONCURRENT_WA_THREADS})")
```

### After
```python
logger.warning("⚠️ DEV MODE: VALIDATE_TWILIO_SIGNATURE=false - signature validation skipped")
logger.warning(f"⚠️ WhatsApp thread pool full ({_active_wa_threads}/{MAX_CONCURRENT_WA_THREADS})")
```

## Example 4: Debug Messages (Conditional)

### Before
```python
if DEBUG: print(f"✅ [REGISTRY] Registered session for call {call_sid[:8]}...")
if DEBUG: print(f"⏱️ [PARALLEL] Client created in {(t_client-t_start)*1000:.0f}ms")
```

### After
```python
if DEBUG: logger.debug(f"✅ [REGISTRY] Registered session for call {call_sid[:8]}...")
if DEBUG: logger.debug(f"⏱️ [PARALLEL] Client created in {(t_client-t_start)*1000:.0f}ms")
```

## Example 5: Multi-line F-strings

### Before
```python
print(f"✅ [CALL CONFIG] Loaded for business {business_id}: "
      f"bot_speaks_first={config.bot_speaks_first}, "
      f"auto_end_goodbye={config.auto_end_on_goodbye}")
```

### After
```python
logger.info(f"✅ [CALL CONFIG] Loaded for business {business_id}: "
            f"bot_speaks_first={config.bot_speaks_first}, "
            f"auto_end_goodbye={config.auto_end_on_goodbye}")
```

## Example 6: Force Print (Critical Operations)

### Before
```python
force_print(f"[HANGUP] executed reason={self.pending_hangup_reason} call_sid={call_sid}")
force_print(f"🚀 [FAQ_HIT] biz={business_id} intent={intent_key} score={score:.3f}")
```

### After
```python
logger.error(f"[HANGUP] executed reason={self.pending_hangup_reason} call_sid={call_sid}")
logger.info(f"🚀 [FAQ_HIT] biz={business_id} intent={intent_key} score={score:.3f}")
```

## Example 7: Import and Logger Definition Added

### Before
```python
from flask import Blueprint, request, jsonify

webhook_bp = Blueprint('webhook', __name__, url_prefix='/webhook')

def process_webhook():
    print(f"🚀 Processing webhook...")
```

### After
```python
from flask import Blueprint, request, jsonify
import logging

logger = logging.getLogger(__name__)
webhook_bp = Blueprint('webhook', __name__, url_prefix='/webhook')

def process_webhook():
    logger.info(f"🚀 Processing webhook...")
```

## Preserved Infrastructure Code

These were **NOT** converted (intentionally):

```python
# Print override mechanism (media_ws_ai.py)
_orig_print = builtins.print
def print(*args, **kwargs):
    kwargs.setdefault('flush', True)
    _original_print(*args, **kwargs)
builtins.print = print
```

```python
# Fallback lambda for missing send method
self._ws_send_method = getattr(ws, 'send_text', lambda x: print(f"❌ No send method: {x}"))
```
