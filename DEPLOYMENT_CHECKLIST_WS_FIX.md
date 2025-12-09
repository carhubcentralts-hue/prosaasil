# WebSocket Fix - Deployment Checklist

## Pre-Deployment

- [x] Removed `vr.record()` from `incoming_call()` function
- [x] Removed `vr.record()` from `outbound_call()` function
- [x] Verified no lint errors in modified files
- [x] Confirmed recording logic intact in `stream_ended` webhook
- [x] Confirmed offline STT worker not modified
- [x] Created documentation files

## Deployment Steps

1. **Backup current version** (optional but recommended)
   ```bash
   git stash
   # or
   cp server/routes_twilio.py server/routes_twilio.py.backup
   ```

2. **Apply changes**
   ```bash
   git pull origin cursor/fix-twiml-for-ws-cad1
   # or manually copy the fixed routes_twilio.py
   ```

3. **Restart backend service**
   ```bash
   # Docker:
   docker-compose restart prosaas-backend
   
   # Systemd:
   sudo systemctl restart prosaas-backend
   
   # Manual:
   pkill -f "python.*asgi.py" && python3 asgi.py &
   ```

4. **Monitor logs during restart**
   ```bash
   # Docker:
   docker-compose logs -f prosaas-backend
   
   # Direct logs:
   tail -f /var/log/prosaas/backend.log
   ```

## Post-Deployment Testing

### Test 1: Incoming Call
- [ ] Make a test call to your Twilio number
- [ ] Verify call connects successfully
- [ ] Verify AI responds properly
- [ ] Speak for a few seconds
- [ ] Hang up
- [ ] Check logs for expected output (see below)

### Test 2: Log Verification
Check that logs contain:
- [ ] `[CALL_SETUP] Greeting mode: ai_only (no static Play/Say)`
- [ ] `🔥 TWIML_FULL=<?xml version="1.0" encoding="UTF-8"?><Response><Connect`
- [ ] **NO** `<Record` in TWIML_FULL
- [ ] `🎤 WS_START - call_sid=CA...`
- [ ] `🎤 REALTIME` events during call
- [ ] `[RECORDING] Stream ended → safe to start recording`
- [ ] `[OFFLINE_STT] Transcript obtained`
- [ ] `✅ Post-call extraction complete`

### Test 3: Database Verification
```sql
-- Check latest call has transcription
SELECT 
    call_sid, 
    status, 
    recording_url,
    LENGTH(transcription) as transcript_length,
    LENGTH(call_summary) as summary_length,
    created_at
FROM call_logs 
ORDER BY created_at DESC 
LIMIT 1;
```

Expected results:
- [ ] `status` = 'completed' or 'transcribed'
- [ ] `recording_url` is not NULL
- [ ] `transcript_length` > 0
- [ ] `summary_length` > 0

### Test 4: Outbound Call (Optional)
If you use outbound calling feature:
- [ ] Trigger an outbound call from the UI
- [ ] Verify connection works
- [ ] Verify recording happens
- [ ] Check logs for same patterns as incoming call

## Rollback Plan (If Needed)

If something goes wrong:

1. **Restore backup**
   ```bash
   git stash pop
   # or
   cp server/routes_twilio.py.backup server/routes_twilio.py
   ```

2. **Restart service**
   ```bash
   docker-compose restart prosaas-backend
   ```

3. **Report issue**
   - Save error logs
   - Note what test failed
   - Contact support with details

## Success Criteria

✅ **Fix is successful if:**
- Incoming calls connect and WebSocket works
- Real-time audio streaming happens (check WS_START in logs)
- No `<Record>` tag in TWIML_FULL logs
- Recordings still saved after call ends
- Offline transcription still works
- Post-call summaries still generated

❌ **Rollback if:**
- Calls fail to connect
- No audio streaming (no WS_START events)
- Recordings not saved
- Transcription doesn't work
- Any critical errors in logs

## Expected Performance

- **TwiML generation**: < 100ms (no change from before)
- **WebSocket connection**: < 500ms (should improve!)
- **Call quality**: Same or better than before
- **Recording processing**: Same as before (happens after call)
- **Transcription time**: Same as before (offline, async)

## Monitoring Commands

```bash
# Watch logs in real-time
docker-compose logs -f prosaas-backend | grep -E "(TWIML|WS_START|RECORDING|OFFLINE_STT)"

# Count successful WebSocket connections
docker-compose logs prosaas-backend | grep "WS_START" | wc -l

# Check for Record tags (should be 0 for normal calls)
docker-compose logs prosaas-backend | grep "TWIML_FULL" | grep "<Record" | wc -l

# Verify recordings are being processed
docker-compose logs prosaas-backend | grep "OFFLINE_STT" | tail -5
```

## Quick Health Check

Run this after deployment:

```bash
#!/bin/bash
echo "=== WebSocket Fix Health Check ==="
echo ""

echo "1. Backend Status:"
systemctl status prosaas-backend 2>/dev/null || docker-compose ps prosaas-backend

echo ""
echo "2. Recent Calls (last 5):"
docker-compose logs prosaas-backend | grep "TWIML_FULL" | tail -5

echo ""
echo "3. WebSocket Connections (last hour):"
docker-compose logs --since 1h prosaas-backend | grep "WS_START" | wc -l

echo ""
echo "4. Recordings Processed (last hour):"
docker-compose logs --since 1h prosaas-backend | grep "OFFLINE_STT" | wc -l

echo ""
echo "5. Check for Record tags (should be 0):"
docker-compose logs --since 1h prosaas-backend | grep "TWIML_FULL" | grep -c "<Record"

echo ""
echo "=== Health Check Complete ==="
```

## Contact Information

If you encounter issues:
1. Check logs first
2. Review this checklist
3. Check the documentation files:
   - `TWIML_WS_FIX.md`
   - `תיקון_בעיית_WebSocket.md`
   - `EXPECTED_TWIML_OUTPUT.md`

---

**Remember**: The fix is simple - we removed `<Record>` from initial TwiML. Recording still happens through Twilio's native mechanism and is fetched after the call ends.
