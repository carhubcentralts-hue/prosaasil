# Fix Summary: Silence Handler, Goodbye Detection, and Prompt Cache

## Issues Fixed

### 1. Silence Handler Auto-Hangup in SIMPLE_MODE (Telephony) 🔇

**Problem:**
- In SIMPLE_MODE (telephony calls), the system was auto-closing calls after 10 seconds of silence
- This happened because STT wasn't picking up the user well (8kHz telephony quality)
- The silence failsafe would trigger a polite closing message like "תודה שהתקשרת, נשמח לעזור לך בפעם הבאה"
- Then the GOODBYE CHECK would detect the closing phrase and trigger SMART_HANGUP

**Root Cause:**
- `_send_text_to_ai()` was generating SILENCE_HANDLER responses in all modes
- The silence monitor wasn't checking for SIMPLE_MODE before triggering auto-hangup
- This caused premature call disconnections in telephony scenarios

**Solution:**
- Added SIMPLE_MODE check in silence monitor (line ~9332) to skip auto-hangup entirely
- Modified `_send_text_to_ai()` to return early in SIMPLE_MODE, preventing SILENCE_HANDLER responses
- Now in telephony mode, the system never auto-closes on silence - letting users take their time

**Code Changes:**
```python
# In silence monitor
if SIMPLE_MODE:
    # In SIMPLE_MODE, never auto-close or hangup due to silence
    # Let the conversation continue - user may be thinking or having connection issues
    continue

# In _send_text_to_ai()
if SIMPLE_MODE:
    print(f"🔇 [SIMPLE_MODE] Skipping SILENCE_HANDLER - no auto-closing on silence in telephony mode")
    return
```

---

### 2. Goodbye Detection with Incomplete Lead Data 🚫

**Problem:**
- AI would sometimes say "תודה שהתקשרת... ביי" even when lead data wasn't complete
- With `auto_end_on_goodbye=True`, the system would hang up immediately
- This caused incomplete lead captures (e.g., missing phone number or name)

**Root Cause:**
- The goodbye detection logic didn't check if required_lead_fields were captured
- It only checked for `user_has_spoken` and AI polite closing phrases
- Lead completeness was ignored in the hangup decision

**Solution:**
- Added SIMPLE_MODE guard that checks `lead_captured` status before allowing goodbye hangup
- When lead is incomplete (required fields not captured), the hangup is blocked
- System logs the block reason and continues the conversation to collect missing data

**Code Changes:**
```python
elif self.auto_end_on_goodbye and ai_polite_closing_detected and self.user_has_spoken:
    # 🔥 FIX: In SIMPLE_MODE with required_lead_fields, check if lead is complete
    if SIMPLE_MODE and self.required_lead_fields and not self.lead_captured:
        # Lead is incomplete - block hangup even if AI said goodbye
        print(f"🔒 [SMART_HANGUP] Goodbye detected but lead incomplete in SIMPLE_MODE - NOT hanging up")
        print(f"   required_lead_fields={self.required_lead_fields}")
        print(f"   lead_captured={self.lead_captured}")
        pass
    elif not self.required_lead_fields:
        # Prompt-only mode - allow hangup
        ...
```

---

### 3. Prompt Cache Direction Bug (Inbound/Outbound Mixing) 🔄

**Problem:**
- The prompt cache was using only `business_id` as the cache key
- This caused inbound and outbound prompts to overwrite each other
- Sometimes the system would use the inbound prompt for outbound calls (or vice versa)
- This led to incorrect greeting styles and behavior

**Root Cause:**
- `PromptCache` class used `Dict[int, CachedPrompt]` with business_id as key
- No distinction between inbound and outbound directions
- Cache collisions were inevitable when both call types existed

**Solution:**
- Changed cache key format to `f"{business_id}:{direction}"` (e.g., "123:inbound")
- Updated CachedPrompt dataclass to include direction field
- Modified all cache operations (get, set, invalidate) to use composite key
- Updated realtime_prompt_builder to pass direction to cache operations

**Code Changes:**
```python
# prompt_cache.py
class PromptCache:
    def __init__(self):
        self._cache: Dict[str, CachedPrompt] = {}  # Changed from Dict[int, ...]
    
    def _make_cache_key(self, business_id: int, direction: str = "inbound") -> str:
        return f"{business_id}:{direction}"
    
    def get(self, business_id: int, direction: str = "inbound") -> Optional[CachedPrompt]:
        cache_key = self._make_cache_key(business_id, direction)
        entry = self._cache.get(cache_key)
        ...

# realtime_prompt_builder.py
cached = cache.get(business_id, direction=call_direction)
cache.set(business_id=business_id, ..., direction=call_direction)
```

---

## Files Modified

### 1. `server/media_ws_ai.py`
- Added SIMPLE_MODE check in silence monitor (line ~9332)
- Modified `_send_text_to_ai()` to skip SILENCE_HANDLER in SIMPLE_MODE (line ~9589)
- Added lead completeness check in goodbye detection (line ~4496)

### 2. `server/services/prompt_cache.py`
- Changed cache key from `int` to `str` with format `business_id:direction`
- Added `direction` field to CachedPrompt dataclass
- Updated get(), set(), invalidate() methods to use composite key
- Added `_make_cache_key()` helper method

### 3. `server/services/realtime_prompt_builder.py`
- Updated cache.get() to pass direction parameter
- Updated cache.set() to pass direction parameter
- Added logging to show direction in cache operations

---

## Testing

### Automated Tests
Created `test_silence_and_cache_fixes.py` with comprehensive cache tests:

```
✅ PASS - Prompt Cache Direction Separation
✅ PASS - Cache Invalidation
✅ PASS - Cache Key Format

🎉 ALL TESTS PASSED!
```

### Manual Testing Checklist
- [ ] Test inbound call to verify no auto-hangup on silence
- [ ] Test outbound call to verify no auto-hangup on silence  
- [ ] Test goodbye detection with incomplete lead data (should continue conversation)
- [ ] Test goodbye detection with complete lead data (should hangup)
- [ ] Test cache returns correct prompt for inbound vs outbound

---

## Impact

### Positive Changes
1. **Better telephony experience**: No more premature hangups in phone calls
2. **Complete lead capture**: System won't hang up until all required fields are collected
3. **Correct prompt usage**: Inbound and outbound calls now use their proper prompts

### No Breaking Changes
- All changes are additive guards and fixes
- Existing behavior preserved for non-SIMPLE_MODE scenarios
- Cache format change is backward compatible (old entries will expire naturally)

---

## Security Review

✅ **CodeQL Analysis**: No security vulnerabilities detected  
✅ **Code Review**: No issues found

---

## Deployment Notes

1. The prompt cache will automatically rebuild with new keys after deployment
2. Old cache entries will expire naturally within 10 minutes (CACHE_TTL_SECONDS)
3. No database migrations required
4. No configuration changes required

---

## Related Issues

This fix addresses the following behavior:
- Auto-hangup on silence after greeting (Bug #1)
- Goodbye triggered with incomplete lead data (Bug #2)
- Inbound/outbound prompt mixing (Bug #3)

All issues mentioned in the original problem statement have been resolved.
