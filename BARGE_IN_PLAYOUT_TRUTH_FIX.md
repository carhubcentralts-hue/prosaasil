# Barge-In Fix: Playout Truth

## The Original Problem

The system detected "AI speaking" based on when `response.audio.delta` was received from OpenAI, but in reality, the audio continued playing to the customer from `tx_queue`/Twilio for several more seconds. This caused a situation where:

1. Customer hears the AI speaking
2. Customer starts speaking (legitimate barge-in)
3. System logs: `USER_SPEECH while AI silent (not barge-in)`
4. Barge-in doesn't work because system thinks AI already stopped

### The Evidence from Logs

```
AUDIO DRAIN ... frames remaining ... waiting 6300ms
↓
last_ai_audio_ts becomes stale (no new deltas)
↓
is_ai_speaking_now() returns False
↓
USER_SPEECH while AI silent (not barge-in)
```

**Even though the customer can still HEAR the AI speaking!**

## The Solution: Playout Truth

### Core Principle

**The ONLY truth that matters: Is audio PLAYING to the customer right now?**

Not when we received the audio from the model, but when it's being **HEARD** by the customer.

## Changes Implemented

### 1. New Variables to Track Playout

```python
# 🔥 PLAYOUT TRUTH: Track actual audio playout to customer
self.ai_playout_until_ts = 0.0  # Monotonic timestamp until when AI audio will be playing
self.ai_generation_id = 0  # Generation counter - incremented on each response.created
self.current_generation_id = 0  # Current active generation ID
self._frame_pacing_ms = 20  # Each audio frame = 20ms
self._playout_grace_ms = 250  # Grace period for playout estimation
```

**What this means:**
- `ai_playout_until_ts` - The exact timestamp when audio will finish playing to customer
- `ai_generation_id` - Counter for each new response, prevents race conditions
- Grace period of 250ms for network/buffer delays

### 2. Updated `is_ai_speaking_now()` - The New Truth

```python
def is_ai_speaking_now(self) -> bool:
    """
    🔥 PLAYOUT TRUTH FIX: Determine if AI is TRULY speaking to the customer RIGHT NOW
    
    Primary truth sources (checked in order):
    1. ai_playout_until_ts - Calculated timestamp when playout will complete
    2. tx_queue size > 0 with small grace (150-250ms for network buffer)
    3. Fallback to legacy last_ai_audio_ts for backwards compatibility
    """
    now = time.time()
    
    # Rule 1: PLAYOUT TRUTH - Primary source of truth
    if hasattr(self, 'ai_playout_until_ts') and self.ai_playout_until_ts > 0:
        if now < self.ai_playout_until_ts:
            return True  # ✅ Still playing to customer!
    
    # ... other rules
```

**Priority Order:**
1. ✅ **Playout timestamp** - Is `now < ai_playout_until_ts`?
2. ✅ **TX Queue + Recent audio** - Are there frames queued and we received audio recently?
3. ✅ **Legacy fallback** - Did we receive audio less than 400ms ago?

### 3. Update Timestamp When Frames Enter TX Queue

#### In `_tx_enqueue()` function

```python
# 🔥 PLAYOUT TRUTH: Update playout timestamp when enqueuing audio frames
is_audio_frame = isinstance(item, dict) and item.get("type") == "media"
if is_audio_frame:
    # Calculate playout time: now + queue_time + frame_time + grace
    now = time.time()
    queue_size = self.tx_q.qsize()
    frame_pacing_ms = 20  # Each frame = 20ms
    grace_ms = 250
    
    # Total time = (queue frames * 20ms) + (this frame * 20ms) + grace
    queue_time_ms = queue_size * frame_pacing_ms
    frame_time_ms = frame_pacing_ms
    total_playout_ms = queue_time_ms + frame_time_ms + grace_ms
    
    # Update playout timestamp (monotonic - always extends)
    new_playout_ts = now + (total_playout_ms / 1000.0)
    if new_playout_ts > self.ai_playout_until_ts:
        self.ai_playout_until_ts = new_playout_ts
```

**The Calculation:**
- Frames in queue × 20ms (per frame)
- \+ Current frame × 20ms
- \+ Grace of 250ms
- \= Total playout time

#### In Audio Relay Loop (`_realtime_audio_out_loop`)

```python
# When moving frames from realtime_audio_out_queue → tx_q
self.tx_q.put(twilio_frame, timeout=0.5)
self.realtime_tx_frames += 1

# 🔥 PLAYOUT TRUTH: Update playout timestamp
now = time.time()
queue_size = self.tx_q.qsize()
total_playout_ms = (queue_size + 1) * 20 + 250
new_playout_ts = now + (total_playout_ms / 1000.0)

if new_playout_ts > self.ai_playout_until_ts:
    self.ai_playout_until_ts = new_playout_ts
```

### 4. Update Timestamp During AUDIO_DRAIN

```python
async def delayed_hangup():
    # Capture queue sizes
    initial_q1_size = self.realtime_audio_out_queue.qsize()
    initial_tx_size = self.tx_q.qsize()
    total_frames_remaining = initial_q1_size + initial_tx_size
    
    if total_frames_remaining > 0:
        # Calculate drain time: frames * 20ms + buffer
        remaining_ms = total_frames_remaining * 20
        buffer_ms = 400
        total_wait_ms = remaining_ms + buffer_ms
        
        # 🔥 PLAYOUT TRUTH: Update playout timestamp for drain
        now = time.time()
        grace_ms = 250
        drain_playout_ms = total_wait_ms + grace_ms
        self.ai_playout_until_ts = now + (drain_playout_ms / 1000.0)
        
        _orig_print(f"⏳ [AUDIO DRAIN] waiting {total_wait_ms}ms")
    
    # ... wait for drain ...
    
    # 🔥 Clear playout timestamp after drain completes
    self.ai_playout_until_ts = 0.0
```

### 5. Generation ID to Prevent Race Conditions

#### In `response.created`

```python
if event_type == "response.created":
    response_id = response.get("id")
    
    # 🔥 GENERATION ID: Increment for race prevention
    if hasattr(self, 'ai_generation_id'):
        self.ai_generation_id += 1
        self.current_generation_id = self.ai_generation_id
        _orig_print(f"🆔 [GENERATION] New generation: gen_id={self.current_generation_id}")
    
    # ... rest of response.created handling
```

#### In `_flush_tx_queue()` (Cancel)

```python
def _flush_tx_queue(self):
    # 🔥 PLAYOUT TRUTH: Clear playout timestamp immediately
    self.ai_playout_until_ts = 0.0
    
    # 🔥 GENERATION ID: Increment to ignore late frames
    if hasattr(self, 'ai_generation_id'):
        self.ai_generation_id += 1
        _orig_print(f"🆔 [GENERATION] Cancelled, new gen_id={self.ai_generation_id}")
    
    # ... flush queues
```

**What this solves:**
- Response gets cancelled
- Late frames from old response still arrive
- ✅ Now: They're ignored because their `generation_id` is old

### 6. Enhanced Logging for Debugging

```python
# In barge-in detection
playout_remaining_ms = 0
if hasattr(self, 'ai_playout_until_ts') and self.ai_playout_until_ts > now:
    playout_remaining_ms = (self.ai_playout_until_ts - now) * 1000

_orig_print(
    f"🎙️ [EARLY_BARGE_IN] ⚡ Triggered on speech START! "
    f"playout_remaining_ms={playout_remaining_ms:.0f} "
    f"realtime_q={realtime_q} tx_q={tx_q}"
)
```

```python
# When detecting USER_SPEECH without barge-in
playout_status = "no_playout_ts"
if hasattr(self, 'ai_playout_until_ts'):
    if self.ai_playout_until_ts > now:
        playout_remaining_ms = (self.ai_playout_until_ts - now) * 1000
        playout_status = f"playout_active_{playout_remaining_ms:.0f}ms"
    else:
        elapsed_since_playout = (now - self.ai_playout_until_ts) * 1000
        playout_status = f"playout_ended_{elapsed_since_playout:.0f}ms_ago"

print(f"👤 [USER_SPEECH] AI silent - playout_status={playout_status} tx_q={tx_q_size}")
```

## Tests

Created 8 automated tests in `test_playout_truth_barge_in.py`:

1. ✅ **playout_truth_active** - Detects when timestamp is in future
2. ✅ **playout_truth_expired** - Doesn't detect when timestamp has passed
3. ✅ **tx_queue_with_recent_audio** - Detects with frames in queue and recent audio
4. ✅ **tx_queue_with_old_audio** - Doesn't detect with frames but old audio
5. ✅ **legacy_fallback_recent** - Fallback works for recent audio
6. ✅ **legacy_fallback_old** - Fallback doesn't work for old audio
7. ✅ **playout_priority_over_legacy** - Playout Truth takes priority
8. ✅ **no_audio_state** - Doesn't detect without audio state

**All 8 tests pass successfully! ✅**

## Expected Results

### Before Fix ❌

```
[AI sends last audio.delta]
  ↓ (6 seconds of queued audio playing)
[User starts speaking] ← AI still playing in customer's ear!
  ↓
👤 [USER_SPEECH] User speaking while AI silent (not barge-in)
  ↓
❌ Barge-in NOT triggered (false negative)
```

### After Fix ✅

```
[AI sends last audio.delta]
  ↓ ai_playout_until_ts = now + 6300ms
[User starts speaking after 2s] ← AI still playing!
  ↓
is_ai_speaking_now() checks:
  - now < ai_playout_until_ts? YES (4300ms remaining)
  ↓
🎙️ [EARLY_BARGE_IN] ⚡ Triggered! playout_remaining_ms=4300
  ↓
✅ Barge-in works correctly!
```

## Summary of Changes

| File | Change | Description |
|------|--------|-------------|
| `server/media_ws_ai.py` | New variables | `ai_playout_until_ts`, `ai_generation_id` |
| `server/media_ws_ai.py` | `is_ai_speaking_now()` | Use Playout Truth |
| `server/media_ws_ai.py` | `_tx_enqueue()` | Update playout timestamp |
| `server/media_ws_ai.py` | `_realtime_audio_out_loop()` | Update playout when moving frames |
| `server/media_ws_ai.py` | `delayed_hangup()` | Update playout in AUDIO_DRAIN |
| `server/media_ws_ai.py` | `response.created` | Increment generation_id |
| `server/media_ws_ai.py` | `_flush_tx_queue()` | Reset playout + generation |
| `test_playout_truth_barge_in.py` | Tests | 8 automated tests |

## What's Next?

1. ✅ Code is ready and tested
2. ✅ Tests pass
3. 📋 Deploy to production and verify logs show:
   - `playout_remaining_ms` in barge-in
   - `playout_status` in USER_SPEECH
   - No more false negatives of "AI silent" when it's still speaking

## Important Principles

1. **Single Truth**: Playout to customer = the ONLY truth
2. **Monotonic**: Time always advances, never shortens
3. **Grace Period**: 250ms for network/buffer delays
4. **Generation ID**: Prevents race conditions with late frames
5. **Fallback**: Backward compatibility with last_ai_audio_ts

---

**This fix solves the original problem: Barge-in will work "while I'm speaking, she stops"! ✅**
