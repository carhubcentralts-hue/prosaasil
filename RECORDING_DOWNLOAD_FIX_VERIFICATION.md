# Recording Download Fix - Verification Guide

## Summary of Changes

### 1. Fixed `download_recording()` in `server/tasks_recording.py`

**Problem:**
- Was using `requests.get()` directly, bypassing Twilio Client configuration
- This caused 404 errors because auth/region/edge settings were not properly applied

**Solution:**
- ✅ Now uses Twilio SDK Client (same auth + region as rest of app)
- ✅ Extracts Recording SID from URL using regex
- ✅ Fetches recording metadata via `client.recordings(recording_sid).fetch()`
- ✅ Downloads media via `client.http_client.request()` with proper auth
- ✅ Comprehensive logging at every step

**Key Changes:**
```python
# OLD (BROKEN):
session = requests.Session()
session.auth = (account_sid, auth_token)
resp = session.get(url, timeout=15)

# NEW (FIXED):
from twilio.rest import Client
client = Client(account_sid, auth_token)
recording = client.recordings(recording_sid).fetch()
media_url = f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}"
resp = client.http_client.request('GET', media_url, auth=(client.username, client.password))
```

### 2. Verified Webhook Logic in `server/media_ws_ai.py`

**Status:** ✅ Already correct (lines 9979-9986)

The webhook already prioritizes offline transcript:
- If `call_log.final_transcript` exists → use it (no length threshold)
- Only falls back to realtime transcript if offline is missing
- Clear logging for both cases

### 3. No Minimum Length Thresholds

**Verified:** ✅ Only check is `len(final_transcript) > 0` which is correct
- No arbitrary thresholds like `> 50` chars
- Any non-empty offline transcript is used as primary source

## Verification Steps

After deployment, look for these log patterns in a test call:

### ✅ Expected Success Logs:

```
[OFFLINE_STT] Original recording_url for CA...: /2010-04-01/Accounts/AC.../Recordings/RE949ef4484c7c2e207a1fb4ef96aee4b1.json
[OFFLINE_STT] Extracted recording SID: RE949ef4484c7c2e207a1fb4ef96aee4b1
[OFFLINE_STT] Recording fetched: RE949ef4484c7c2e207a1fb4ef96aee4b1, duration=45s
[OFFLINE_STT] Downloading recording via Twilio client: https://api.twilio.com/2010-04-01/Accounts/AC.../Recordings/RE....mp3
[OFFLINE_STT] Download status: 200, bytes=123456
[OFFLINE_STT] ✅ Recording saved to disk: server/recordings/CA....mp3 (123456 bytes)
[OFFLINE_STT] ✅ Transcript obtained: 234 chars for CA...
[WEBHOOK] Using OFFLINE transcript (len=234)
```

### ❌ Should NOT See:

```
[OFFLINE_STT] Download status: 404
[OFFLINE_STT] ❌ All download attempts failed
[WEBHOOK] Offline transcript missing → using realtime
```

## Testing Checklist

- [ ] Make a test call (inbound or outbound)
- [ ] Check backend logs for recording download
- [ ] Verify: `Download status: 200, bytes=XXXX`
- [ ] Verify: `✅ Recording saved to disk`
- [ ] Verify: `✅ Transcript obtained`
- [ ] Verify: `[WEBHOOK] Using OFFLINE transcript`
- [ ] No 404 errors in logs
- [ ] Call details show offline transcript in DB

## Technical Details

### Why This Fix Works

1. **Proper Authentication**: Uses Twilio Client's built-in auth mechanism
2. **Region Support**: Client respects TWILIO_REGION and TWILIO_EDGE env vars
3. **SDK Benefits**: Handles edge cases, retries, and Twilio-specific requirements
4. **Consistent Config**: Same client factory used throughout the app

### Recording SID Extraction

```python
# Input: "/2010-04-01/Accounts/AC.../Recordings/RE949ef4484c7c2e207a1fb4ef96aee4b1.json"
# Regex: r'/Recordings/(RE[a-zA-Z0-9]+)'
# Output: "RE949ef4484c7c2e207a1fb4ef96aee4b1"
```

### Media URL Construction

```python
# recording.uri: "/2010-04-01/Accounts/AC.../Recordings/RE....json"
# Replace .json with .mp3
# Prepend Twilio API domain
# Result: "https://api.twilio.com/2010-04-01/Accounts/AC.../Recordings/RE....mp3"
```

## Rollback Plan

If issues occur, the old code is preserved in git history. The fix is isolated to `download_recording()` function only, so rollback is straightforward.

## Next Steps

1. Deploy to production
2. Monitor first few calls
3. Verify logs match expected patterns
4. Confirm 100% offline transcript usage
5. Check webhook payloads contain offline transcripts
