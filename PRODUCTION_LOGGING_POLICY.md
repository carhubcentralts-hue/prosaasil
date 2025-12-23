# Production Logging Policy - Implementation Complete ✅

## Overview
Comprehensive implementation of a production-ready logging policy that minimizes log spam in production while maintaining full debugging capabilities in development.

## Key Principle
**DEBUG=1 → Production (minimal logs)**  
**DEBUG=0 → Development (full logs)**

## Implementation Details

### 1. Rate-Limiting Helpers (`logging_setup.py`)
```python
rl = RateLimiter()
if rl.every("audio_drain", 5.0):
    logger.debug(f"[AUDIO_DRAIN] tx={tx_q} out={out_q}")
```

### 2. Once-Per-Call Helpers (`logging_setup.py`)
```python
once = OncePerCall()
if once.once("dsp_enabled"):
    logger.info("[DSP] enabled: highpass+limiter")
```

### 3. Logging Levels by Mode

#### Production (DEBUG=1):
- **BASE_LEVEL**: INFO (only macro events)
- **NOISY_LEVEL**: WARNING (noisy modules silenced)

#### Development (DEBUG=0):
- **BASE_LEVEL**: DEBUG (full debugging)
- **NOISY_LEVEL**: INFO (noisy modules verbose)

### 4. Noisy Modules
These modules are set to WARNING in production, INFO in development:
- `server.media_ws_ai`
- `server.services.audio_dsp`
- `websockets`
- `urllib3`
- `httpx`
- `openai`

## Production Logs (DEBUG=1)

### What You'll See:
✅ **Macro Events (INFO level)**:
- `[BOOT]` - System initialization
- `[CALL_START]` - Call initiated
- `[REALTIME]` - OpenAI connection status
- `[CREATE_APPT]` - Appointment created successfully
- `[DSP]` - DSP initialization (once per call)
- `[WEBHOOK_CLOSE]` - Webhook-triggered session close
- `[CALL_END]` - Call completion
- `[SERVER_ERROR]` - Server error handling

✅ **Always Visible**:
- WARNING - Important warnings
- ERROR - Critical errors

### What You Won't See:
❌ All DEBUG logs:
- Validation checks
- CRM operations details
- Utterance processing
- Audio frame processing
- Queue states
- RMS calculations
- Transcript deltas

❌ Per-frame/per-event spam:
- Audio deltas (rate-limited to once per 10s)
- RMS values (rate-limited to once per 10s)
- TX_SLOW warnings (rate-limited to once per 5s)
- Partial transcripts
- Queue depths

## Development Logs (DEBUG=0)

### What You'll See:
✅ Everything from production, PLUS:
- All DEBUG level logs
- Detailed validation logs
- CRM operation details
- Utterance processing details
- Audio processing details (still rate-limited)

## Error Suppression Strategy

### DSP Errors:
```python
self._error_count += 1

if not self._first_error_logged:
    logger.error(f"[DSP] ERROR: {e} - first occurrence")
    self._first_error_logged = True
elif rl.every("dsp_error", 30.0):
    logger.warning(f"[DSP] ERROR repeating (count={self._error_count})")
```

**Result**:
- First error: ERROR level
- Subsequent errors: WARNING level every 30 seconds
- No error spam

## Files Changed

### 1. `server/logging_setup.py`
- Added `RateLimiter` class
- Added `OncePerCall` class
- Updated `setup_logging()` to use new DEBUG logic
- Added noisy modules configuration

### 2. `server/services/audio_dsp.py`
- Added rate-limiting for RMS logs (once per 10s)
- Implemented error suppression
- Imported RateLimiter

### 3. `server/media_ws_ai.py`
- Fixed `_dprint` logic (now only prints in DEBUG=0)
- Converted ALL print() statements to logger calls
- Added rate-limiting to TX_SLOW warnings
- Added once-per-call to DSP/AUDIO_MODE logs
- Proper log levels for all events:
  - Validation → DEBUG
  - CRM → DEBUG/ERROR
  - Appointments → INFO/DEBUG
  - Registry → DEBUG
  - Handlers → DEBUG/INFO
  - TX warnings → WARNING (rate-limited)
  - REALTIME → INFO/ERROR/DEBUG
  - Utterances → DEBUG

## Testing

Run the test script to verify:
```bash
# Test production mode
DEBUG=1 python test_logging_policy.py

# Test development mode
DEBUG=0 python test_logging_policy.py
```

### Test Results:
✅ All tests pass in both modes
✅ Rate-limiting works correctly
✅ Once-per-call works correctly
✅ Noisy modules properly silenced in production
✅ Macro events visible in both modes
✅ DEBUG logs suppressed in production

## Deployment Instructions

### Environment Variables:
```bash
# Production
DEBUG=1              # Minimal logs
DEBUG_TX=0           # No TX diagnostics

# Development
DEBUG=0              # Full logs
DEBUG_TX=1           # TX diagnostics enabled (optional)
```

### Expected Log Volume:
- **Production**: ~10-20 log lines per call
- **Development**: ~100-500 log lines per call (depending on call complexity)

### Monitoring:
Watch for these macro events in production:
1. `[CALL_START]` - Call initiated
2. `[REALTIME]` - OpenAI connected
3. `[CREATE_APPT]` - Appointment created (if applicable)
4. `[CALL_END]` - Call completed

Any ERROR or WARNING should be investigated.

## Benefits

1. **Production Performance**: Minimal logging overhead
2. **Production Clarity**: Only important events logged
3. **Development Power**: Full debugging when needed
4. **No Log Spam**: Rate-limiting prevents flooding
5. **Error Tracking**: First error logged, repeats suppressed
6. **Easy Toggle**: Single DEBUG env var switches modes

## Migration Notes

### Old Behavior:
- DEBUG=1 meant development (verbose)
- DEBUG=0 meant production (quiet)

### New Behavior:
- DEBUG=1 means production (minimal)
- DEBUG=0 means development (verbose)

**Migration**: No code changes needed, just update environment variables if you were using DEBUG=0 for production.
