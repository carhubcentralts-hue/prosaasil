# Fix: AI Speaking State to Track Audio Delivery

## Problem Statement (Hebrew)
לתקן את ההגדרה של is_ai_speaking / ai_response_active כך שתישאר TRUE כל עוד יש אודיו בדרך ללקוח:
1. להדליק is_ai_speaking=True על audio.delta הראשון (כבר יש לכם)
2. לא לכבות על response.audio.done בלבד

אלא לכבות רק כששני תנאים מתקיימים:
- קיבלנו response.audio.done / response.done עבור אותו response_id
- וגם: תורי האודיו התרוקנו בפועל (TX queue + audio_out_queue)
- או שעבר "drain timeout" קצר (למשל 300–600ms) אחרי ה־done.

במילים פשוטות: AI נחשבת "מדברת" עד שהאודיו האחרון באמת הושמע/נשלח — לא עד שהשרת אמר done.

## Solution Overview

### Root Cause
The `is_ai_speaking` flag was being cleared immediately when `response.audio.done` was received, even though audio frames were still in the transmission queues (`tx_q` and `realtime_audio_out_queue`). This caused barge-in to not work correctly mid-sentence because the system thought the AI had stopped speaking when audio was still being transmitted to the client.

### Fix Implementation

#### 1. New Method: `_check_audio_drain_and_clear_speaking()`
Location: `server/media_ws_ai.py` (line ~11153)

This async method implements the drain check logic:
```python
async def _check_audio_drain_and_clear_speaking(self, response_id: Optional[str]):
    DRAIN_TIMEOUT_SEC = 0.5  # 500ms timeout
    POLL_INTERVAL_MS = 50     # Check every 50ms
    
    while checks < max_checks:
        tx_size = self.tx_q.qsize()
        audio_out_size = self.realtime_audio_out_queue.qsize()
        
        if tx_size == 0 and audio_out_size == 0:
            # Clear flags when both queues empty
            self.is_ai_speaking_event.clear()
            self.speaking = False
            # ... clear other flags
            return
        
        await asyncio.sleep(POLL_INTERVAL_MS / 1000.0)
    
    # Timeout - clear anyway to prevent stuck state
```

Key features:
- Polls both queues every 50ms
- Clears `is_ai_speaking` only when BOTH queues are empty
- Times out after 500ms to prevent stuck states
- Clears all related flags atomically

#### 2. Modified `response.audio.done` Handler
Location: `server/media_ws_ai.py` (line ~5110)

**Before:**
```python
self.is_ai_speaking_event.clear()  # Immediate clear
self.speaking = False
```

**After:**
```python
# Store that audio.done was received
self._audio_done_received[done_resp_id] = time.time()
print(f"🔇 [AUDIO_DONE] Received, queues: tx={self.tx_q.qsize()}, audio_out={self.realtime_audio_out_queue.qsize()}")

# Schedule drain check to clear is_ai_speaking after queues empty OR timeout
asyncio.create_task(self._check_audio_drain_and_clear_speaking(done_resp_id))
```

#### 3. Modified `response.done` Handler
Location: `server/media_ws_ai.py` (line ~4155)

Same pattern as audio.done - schedules drain check instead of immediate clear.

#### 4. Modified `response.cancelled` Handler
Location: `server/media_ws_ai.py` (line ~4271 and ~3935)

Updated both locations where cancelled events are handled to use drain check.

#### 5. Barge-In Logic Clarification
Location: `server/media_ws_ai.py` (line ~4641)

Added comment explaining that barge-in should clear immediately (forced interruption):
```python
# Step 4: Reset state (ONLY after successful cancel + cleanup)
# 🔥 NOTE: For barge-in, clear is_ai_speaking IMMEDIATELY after queue flush
# This is different from natural completion (response.audio.done) which waits for drain
# Barge-in = forced interruption, so immediate clear is correct
self.is_ai_speaking_event.clear()
```

### State Transitions

#### Natural Completion (response.audio.done)
```
1. AI sends audio via audio.delta
   → is_ai_speaking = True (on first delta)
   
2. OpenAI sends response.audio.done
   → Store done timestamp
   → Schedule drain check task
   → is_ai_speaking REMAINS True
   
3. Drain check task polls queues every 50ms
   → If queues empty: Clear is_ai_speaking
   → If timeout (500ms): Clear is_ai_speaking anyway
```

#### Forced Interruption (Barge-In)
```
1. User speaks (speech_started event)
   → Cancel active response
   → Send Twilio "clear" event
   → Flush both queues
   → is_ai_speaking = False IMMEDIATELY
```

## Testing

### Test Suite: `test_audio_drain_fix.py`

Created comprehensive tests covering all scenarios:

1. **test_immediate_clear_when_queues_empty** ✅
   - Verifies immediate clear when queues already empty
   
2. **test_delayed_clear_when_queues_draining** ✅
   - Verifies is_ai_speaking remains True while queues drain
   - Clears only after queues become empty
   
3. **test_timeout_clear_when_queues_never_empty** ✅
   - Verifies timeout clear after 500ms if queues stuck
   - Prevents infinite wait on stuck queues
   
4. **test_all_flags_cleared_together** ✅
   - Verifies atomic clearing of all related flags
   - Ensures consistent state
   
5. **test_barge_in_clears_immediately_after_flush** ✅
   - Verifies barge-in uses immediate clear (not drain check)
   - Correct behavior for forced interruption
   
6. **test_natural_completion_uses_drain_check** ✅
   - Verifies natural completion schedules drain check
   - Different from barge-in behavior

All 6 tests pass successfully!

## Benefits

### 1. Correct Barge-In Behavior
- Barge-in now works correctly mid-sentence
- `is_ai_speaking` accurately reflects audio transmission state
- No premature cancellation when audio is still playing

### 2. Prevents Audio Truncation
- Audio in queues will finish playing before state clears
- Users hear complete AI responses
- No abrupt cuts mid-sentence

### 3. Robust State Management
- 500ms timeout prevents stuck states
- Atomic flag clearing ensures consistency
- Clear logging for debugging

### 4. Maintains Barge-In Responsiveness
- Barge-in still clears immediately (forced interruption)
- No delay in user interruption
- Natural completion uses drain, barge-in doesn't

## Configuration

### Timing Constants
```python
DRAIN_TIMEOUT_SEC = 0.5  # 500ms - between 300-600ms as specified
POLL_INTERVAL_MS = 50     # Check every 50ms for responsive drain
```

These can be adjusted if needed:
- Lower timeout = faster clear but higher risk of truncation
- Higher timeout = safer but longer stuck state recovery
- Lower poll interval = more responsive but higher CPU
- Higher poll interval = less CPU but less responsive

## Deployment

### Files Changed
1. `server/media_ws_ai.py` - Core fix implementation
2. `test_audio_drain_fix.py` - Test suite (new file)

### No Breaking Changes
- Backward compatible with existing behavior
- Only affects state clearing timing
- Barge-in behavior unchanged (still immediate)

### Monitoring
Look for these log lines in production:
```
🔇 [AUDIO_DONE] Received for response_id=..., queues: tx=X, audio_out=Y
✅ [AUDIO_DRAIN] Queues empty after XXXms - clearing is_ai_speaking
⏰ [AUDIO_DRAIN] Timeout (0.5s) - clearing is_ai_speaking even with queues: tx=X, audio_out=Y
```

## Summary

The fix ensures that `is_ai_speaking` accurately tracks audio delivery state:
- ✅ Set True on first audio.delta
- ✅ Remain True while audio is in queues
- ✅ Clear only when queues empty OR timeout
- ✅ Barge-in clears immediately (forced interruption)
- ✅ All flags cleared atomically
- ✅ Comprehensive test coverage

This matches the Hebrew requirements exactly: AI נחשבת "מדברת" עד שהאודיו האחרון באמת הושמע/נשלח — לא עד שהשרת אמר done.
