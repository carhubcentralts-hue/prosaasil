# Call Plane Fix - Verification Guide

## Summary of Changes

This PR fixes critical boot errors and missing call logs that were preventing incoming and outgoing calls from being tracked and handled properly.

### Root Causes Fixed

1. **NameError in routes_calendar.py** - `require_page_access` was not imported
2. **Blueprint imports not fail-fast** - App continued running with broken routes
3. **Missing trace logs** - No visibility when calls arrive or fail

## Changes Made

### 1. Fix Import Error in routes_calendar.py

**File**: `server/routes_calendar.py`

**Problem**: Line 83 used `@require_page_access('calendar')` decorator but the function was not imported.

**Fix**: Added proper import at the top of the file:
```python
from server.security.permissions import require_page_access  # Page access decorator
```

**Impact**: Calendar routes will now load without NameError crash.

### 2. Make Blueprint Imports Fail-Fast

**File**: `server/app_factory.py`

**Problem**: When a blueprint failed to import, the app continued starting without critical routes (like Twilio webhooks), resulting in "no log at all" when calls arrived.

**Fix**: Wrapped critical blueprint imports in try-except that re-raises:
```python
try:
    from server.routes_twilio import twilio_bp
    app.register_blueprint(twilio_bp)
    app.logger.info("✅ Twilio blueprint registered (call webhooks active)")
except Exception as e:
    app.logger.error(f"❌ [BOOT][FATAL] Failed to import/register Twilio blueprint: {e}")
    import traceback
    traceback.print_exc()
    raise RuntimeError(f"Critical blueprint 'routes_twilio' failed to register: {e}")
```

**Impact**: 
- App will CRASH immediately if Twilio or Calendar blueprints fail to load
- Forces fix before deployment instead of running in broken state
- Clear error message in logs: `[BOOT][FATAL]`

### 3. Add Trace Logging for Inbound Calls

**File**: `server/routes_twilio.py`

**Function**: `incoming_call()` (line 433)

**Added**:
```python
# 🔥 TRACE LOGGING: Log all incoming calls immediately
x_twilio_signature = request.headers.get('X-Twilio-Signature', '')
logger.info(f"[TWILIO][INBOUND] hit path=/webhook/incoming_call call_sid={call_sid} from={from_number} to={to_number} direction={twilio_direction} signature_present={bool(x_twilio_signature)}")
print(f"[TWILIO][INBOUND] hit path=/webhook/incoming_call call_sid={call_sid} from={from_number} to={to_number}")
```

**Impact**: Every incoming call will log immediately with call details, even if it crashes later.

### 4. Add Trace Logging for Outbound Webhook

**File**: `server/routes_twilio.py`

**Function**: `outbound_call()` (line 676)

**Added**:
```python
# 🔥 TRACE LOGGING: Log all outbound calls immediately
x_twilio_signature = request.headers.get('X-Twilio-Signature', '')
logger.info(f"[TWILIO][OUTBOUND] hit path=/webhook/outbound_call call_sid={call_sid} from={from_number} to={to_number} lead_id={lead_id} business_id={business_id} signature_present={bool(x_twilio_signature)}")
print(f"[TWILIO][OUTBOUND] hit path=/webhook/outbound_call call_sid={call_sid} from={from_number} to={to_number}")
```

**Impact**: Every outbound call webhook will log immediately.

### 5. Add Trace Logging for Outbound API Calls

**File**: `server/services/twilio_outbound_service.py`

**Function**: `create_outbound_call()` (line 113)

**Added**:
```python
# 🔥 TRACE LOGGING: Generate unique request ID for tracking
import uuid
req_uuid = str(uuid.uuid4())[:8]
log.info(f"[OUTBOUND][REQ={req_uuid}] tenant={business_id} lead_id={lead_id} to={to_phone} from={from_phone}")
print(f"[OUTBOUND][REQ={req_uuid}] tenant={business_id} to={to_phone} from={from_phone}")

# Before Twilio API call
log.info(f"[OUTBOUND][REQ={req_uuid}] calling twilio...")
print(f"[OUTBOUND][REQ={req_uuid}] calling twilio...")

# After successful call
log.info(f"[OUTBOUND][REQ={req_uuid}] twilio_ok call_sid={call_sid}")
print(f"[OUTBOUND][REQ={req_uuid}] twilio_ok call_sid={call_sid}")

# On failure
log.error(f"[OUTBOUND][REQ={req_uuid}] twilio_failed err={str(e)}")
print(f"[OUTBOUND][REQ={req_uuid}] twilio_failed err={str(e)}")
```

**Impact**: Full lifecycle tracking of outbound calls with unique request ID.

## Verification Steps

### Step 1: Check Boot Logs

After deployment, check server logs for:

✅ **Success indicators**:
```
✅ Twilio blueprint registered (call webhooks active)
✅ Calendar blueprint registered
```

❌ **Failure indicators (if present, deployment should fail)**:
```
❌ [BOOT][FATAL] Failed to import/register Twilio blueprint: ...
❌ [BOOT][FATAL] Failed to import/register Calendar blueprint: ...
NameError: name 'require_page_access' is not defined
```

### Step 2: Test Inbound Calls

Make a test call to the Twilio number. Check logs for:

```
[TWILIO][INBOUND] hit path=/webhook/incoming_call call_sid=CA... from=+972... to=+972...
```

This log should appear **immediately** when the call arrives, even if there's a crash later.

### Step 3: Test Outbound Calls

Initiate an outbound call from the UI. Check logs for sequence:

```
[OUTBOUND][REQ=abc123de] tenant=X lead_id=Y to=+972... from=+972...
[OUTBOUND][REQ=abc123de] calling twilio...
[OUTBOUND][REQ=abc123de] twilio_ok call_sid=CA...
[TWILIO][OUTBOUND] hit path=/webhook/outbound_call call_sid=CA... from=+972... to=+972...
```

### Step 4: Verify No "Silent Failures"

**Before this fix**: Call arrives → no log → route not registered → silent failure
**After this fix**: Call arrives → log appears → if route fails, we see the crash

## Security Verification

✅ **Twilio webhooks are properly secured**:
- All webhook endpoints use `@csrf.exempt` (correct for machine-to-machine)
- All webhook endpoints use `@require_twilio_signature` (validates Twilio signature)
- NO `@require_page_access` on webhooks (would break machine-to-machine calls)

## Known Non-Issues

### Pydantic Cache Clear Error
The error `"additionalProperties": "error"` in logs is NOT related to calls. It's a separate Pydantic caching issue. This PR focuses only on call plane.

### Agent Warmup
The `get_or_create_agent` import in `lazy_services.py` is CORRECT. The function exists in `agent_factory.py` at line 79. Any previous ImportError was transient or from old code.

## Rollback Plan

If this PR causes issues, rollback is simple:
1. Revert the 4 file changes
2. Redeploy

The changes are minimal and surgical - only fixing imports and adding logging.

## Definition of Done

- [x] ✅ Backend doesn't start if blueprint import fails (Fail-Fast)
- [x] ✅ No more NameError on require_page_access
- [x] ✅ Every incoming call logs `[TWILIO][INBOUND]` immediately
- [x] ✅ Every outbound call logs `[OUTBOUND][REQ=uuid]` lifecycle
- [x] ✅ Webhooks exempt from page access (use Twilio signature)
- [ ] ⏳ After deployment: See logs for every call attempt (verification step)

## Next Steps After Deployment

1. Monitor logs for `[TWILIO][INBOUND]` and `[OUTBOUND]` entries
2. If calls still don't work, we now have visibility into WHERE they fail
3. Common issues to check if logs show calls arriving but failing:
   - Database connection (check business lookup)
   - WebSocket connection (check stream setup)
   - Agent warmup (check agent creation)

## Questions to Ask When Debugging

With these logs, you can now answer:

1. **Are calls reaching the backend at all?**
   → Look for `[TWILIO][INBOUND]` or `[OUTBOUND][REQ=]`

2. **Is the Twilio signature valid?**
   → Check `signature_present=True` in logs

3. **Is Twilio API call succeeding?**
   → Look for `twilio_ok call_sid=` vs `twilio_failed err=`

4. **Which business/tenant is receiving the call?**
   → Check `tenant=X` in outbound logs, or business lookup in inbound

5. **Did blueprints load properly?**
   → Look for `✅ Twilio blueprint registered` in boot logs

---

**Author**: GitHub Copilot
**Date**: 2026-01-18
**Issue**: Fix incoming/outgoing calls not arriving/dropping immediately
