# SIP/Asterisk Migration Verification Guide

## Pre-Flight Checklist

Before running tests, verify:

- [ ] All services running: `docker-compose -f docker-compose.sip.yml ps`
- [ ] Asterisk CLI accessible: `docker exec -it prosaas-asterisk asterisk -rvvv`
- [ ] ARI endpoint responsive: `curl -u prosaas:password http://localhost:8088/ari/asterisk/info`
- [ ] Media Gateway running: `docker-compose -f docker-compose.sip.yml logs media-gateway | tail -20`
- [ ] Backend healthy: `curl http://localhost:5000/health`
- [ ] SIP trunk registered (if applicable): `pjsip show registrations`
- [ ] Recording directory accessible: `docker exec prosaas-asterisk ls -la /var/spool/asterisk/recordings/`

## Test Suite

### 1. Inbound Call Tests

#### 1.1 Basic Inbound Call
**Objective**: Verify incoming call is answered and AI responds

**Steps**:
1. Call your DID from a phone
2. Wait for AI to answer
3. Say "Hello" and wait for response
4. Hang up

**Expected Results**:
- [ ] Call answered within 2 seconds
- [ ] AI greeting plays within 2 seconds of answer
- [ ] AI responds to "Hello"
- [ ] Call quality is clear
- [ ] No echo or feedback

**Logs to Check**:
```bash
# Asterisk logs
docker exec prosaas-asterisk asterisk -rvvv
# Look for: "StasisStart", "Bridge", "ExternalMedia"

# Media Gateway logs
docker-compose -f docker-compose.sip.yml logs -f media-gateway
# Look for: "[MEDIA_GATEWAY] Starting session"

# Backend logs
docker-compose -f docker-compose.sip.yml logs -f backend
# Look for: "[ARI] StasisStart", "CallLog created"
```

#### 1.2 Barge-In Test
**Objective**: Verify interruption works correctly

**Steps**:
1. Call your DID
2. Wait for AI to start speaking
3. Interrupt AI mid-sentence
4. Verify AI stops and listens

**Expected Results**:
- [ ] AI stops talking when interrupted
- [ ] AI acknowledges interruption
- [ ] No audio artifacts or cuts
- [ ] Conversation continues smoothly

#### 1.3 Recording Test
**Objective**: Verify entire call is recorded

**Steps**:
1. Call your DID
2. Have a 30-second conversation
3. Hang up
4. Wait 60 seconds for processing
5. Check recording exists

**Expected Results**:
- [ ] Recording file exists: `docker exec prosaas-asterisk ls /var/spool/asterisk/recordings/1/`
- [ ] Recording duration matches call duration
- [ ] Audio quality is clear
- [ ] Both sides audible (dual channel)

**Verify Recording**:
```bash
# List recordings
docker exec prosaas-asterisk ls -lh /var/spool/asterisk/recordings/1/

# Download and play locally
docker cp prosaas-asterisk:/var/spool/asterisk/recordings/1/CALL_ID.wav ./test.wav
# Play with your audio player
```

#### 1.4 Transcription Test
**Objective**: Verify automatic transcription works

**Steps**:
1. Call your DID
2. Say clearly: "This is a test transcription"
3. Wait for AI response
4. Hang up
5. Wait 2-3 minutes for transcription
6. Check CallLog in database

**Expected Results**:
- [ ] CallLog.status = "recorded"
- [ ] CallLog.transcript contains "test transcription"
- [ ] CallLog.recording_url populated
- [ ] Transcription accuracy > 90%

**Check Database**:
```bash
# Connect to database
docker exec -it prosaas-backend python -c "
from server.models_sql import CallLog, db
from server.app_factory import get_process_app

app = get_process_app()
with app.app_context():
    calls = CallLog.query.order_by(CallLog.created_at.desc()).limit(5).all()
    for call in calls:
        print(f'Call: {call.call_sid}')
        print(f'  Status: {call.status}')
        print(f'  Transcript: {call.transcript[:100] if call.transcript else None}')
        print(f'  Recording: {call.recording_url}')
        print()
"
```

### 2. Outbound Call Tests

#### 2.1 Single Outbound Call
**Objective**: Verify outbound calling works

**Steps**:
1. Create outbound call via API
2. Answer the call on destination phone
3. Wait for AI to speak first
4. Have conversation
5. Hang up

**API Request**:
```bash
curl -X POST http://localhost:5000/api/outbound/call \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "business_id": 1,
    "to_number": "+1234567890",
    "from_number": "+0987654321",
    "lead_id": 123
  }'
```

**Expected Results**:
- [ ] Call connects within 5 seconds
- [ ] Destination phone rings
- [ ] AI speaks first when answered
- [ ] Conversation proceeds normally
- [ ] Recording captured

#### 2.2 Bulk Outbound Calls
**Objective**: Verify concurrent outbound calling with limits

**Steps**:
1. Create bulk call job with 10 leads
2. Set max_concurrent = 3
3. Monitor call progression
4. Verify rate limiting

**API Request**:
```bash
curl -X POST http://localhost:5000/api/outbound/bulk \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "business_id": 1,
    "lead_ids": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "max_concurrent": 3
  }'
```

**Expected Results**:
- [ ] Max 3 calls active at any time
- [ ] New calls start as previous complete
- [ ] No duplicates (same lead not called twice)
- [ ] All 10 calls complete or fail
- [ ] Recordings for all answered calls

**Monitor Progress**:
```bash
# Watch active calls
watch -n 1 'curl -s http://localhost:5000/api/outbound/runs/LAST_RUN_ID | jq ".in_progress_count"'

# Check Asterisk channels
docker exec prosaas-asterisk asterisk -rx "core show channels"
```

#### 2.3 No-Duplicate Test
**Objective**: Verify idempotency prevents duplicate calls

**Steps**:
1. Create outbound call to lead 123
2. Immediately create another call to lead 123
3. Verify only one call is made

**Expected Results**:
- [ ] First API call returns call_id
- [ ] Second API call returns same call_id with `is_duplicate: true`
- [ ] Only one actual call made to lead

### 3. Smart Hangup Tests

#### 3.1 Voicemail Detection (15s)
**Objective**: Verify voicemail detection works

**Steps**:
1. Create outbound call to a number that goes to voicemail
2. Let voicemail greeting play
3. Verify call hangs up within 15 seconds

**Expected Results**:
- [ ] Call hangs up within 15 seconds of voicemail greeting
- [ ] CallLog.status = "no_answer" or "voicemail_detected"
- [ ] No recording created (or very short)
- [ ] Hung up before leaving message

**Manual Test**:
```bash
# Create call to known voicemail number
curl -X POST http://localhost:5000/api/outbound/call \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"to_number": "+1VOICEMAIL_NUMBER", ...}'

# Monitor logs for hangup reason
docker-compose -f docker-compose.sip.yml logs -f backend | grep voicemail
```

#### 3.2 Silence Detection (20s)
**Objective**: Verify silence timeout works

**Steps**:
1. Create inbound or outbound call
2. Answer but say nothing
3. Wait 20 seconds
4. Verify call hangs up automatically

**Expected Results**:
- [ ] Call hangs up after 20 seconds of silence
- [ ] CallLog includes hangup reason = "silence_timeout"
- [ ] Recording captured up to hangup
- [ ] Clean hangup (no errors)

### 4. Concurrent Call Tests

#### 4.1 Inbound Concurrency Limit
**Objective**: Verify inbound rate limiting

**Steps**:
1. Configure business max_concurrent_inbound = 2
2. Make 3 simultaneous inbound calls
3. Verify 3rd call is rejected with message

**Expected Results**:
- [ ] First 2 calls accepted
- [ ] 3rd call plays rejection message (Hebrew)
- [ ] 3rd call hangs up immediately
- [ ] No CallLog created for rejected call

**Logs**:
```bash
docker-compose -f docker-compose.sip.yml logs backend | grep "INCOMING_CALL REJECTED"
```

#### 4.2 Outbound Concurrency Limit
**Objective**: Verify outbound slot management

**Steps**:
1. Create bulk call with 100 leads
2. Set max_concurrent = 3
3. Monitor throughout execution
4. Verify never exceeds 3 concurrent

**Expected Results**:
- [ ] Max 3 calls active at any time
- [ ] Queue processes all 100 leads
- [ ] Slots fill immediately when call ends
- [ ] All leads attempted

**Monitor**:
```bash
# Real-time monitoring
watch -n 0.5 'docker exec prosaas-asterisk asterisk -rx "core show channels" | grep -c "active"'
```

### 5. Call Quality Tests

#### 5.1 Audio Quality
**Objective**: Verify audio clarity and codec

**Test Parameters**:
- Codec: g711 ulaw (verify in logs)
- Sample rate: 8kHz
- Frame size: 20ms
- No transcoding

**Manual Check**:
1. Make test call
2. Listen to audio quality
3. Check for artifacts, distortion, echo

**Expected Results**:
- [ ] Clear audio both directions
- [ ] No echo or feedback
- [ ] No robotic or distorted sound
- [ ] Consistent volume
- [ ] Low latency (< 200ms)

**Verify Codec**:
```bash
# Check channel codec
docker exec prosaas-asterisk asterisk -rx "core show channel CHANNEL_ID" | grep Codec
# Should show: "ulaw" or "PCMU"
```

#### 5.2 Latency Test
**Objective**: Measure end-to-end latency

**Steps**:
1. Make inbound call
2. Measure time from answer to first audio
3. Measure time from speaking to AI response

**Expected Results**:
- [ ] Answer to AI greeting: < 2 seconds
- [ ] Speak to AI response: < 1.5 seconds
- [ ] No noticeable delay in conversation
- [ ] Barge-in latency: < 500ms

**Logs to Analyze**:
```bash
# Check timing logs
docker-compose -f docker-compose.sip.yml logs backend | grep "GREETING_PROFILER"
docker-compose -f docker-compose.sip.yml logs media-gateway | grep "latency"
```

### 6. Recording & Transcription Pipeline

#### 6.1 Recording Pipeline
**Objective**: Verify end-to-end recording flow

**Flow**:
1. Call starts → MixMonitor starts
2. Call ends → Recording file created
3. File uploaded to S3/MinIO (if configured)
4. CallLog.recording_url updated

**Verify Each Step**:
```bash
# 1. During call - check MixMonitor
docker exec prosaas-asterisk asterisk -rx "mixmonitor list"

# 2. After call - check file exists
docker exec prosaas-asterisk ls -lh /var/spool/asterisk/recordings/1/

# 3. Check upload status (if S3 enabled)
docker-compose -f docker-compose.sip.yml logs backend | grep "S3_UPLOAD"

# 4. Verify database
# (use database query from section 1.4)
```

**Expected Results**:
- [ ] Recording starts with call (second 0)
- [ ] Recording stops with call end
- [ ] File size > 0 bytes
- [ ] Upload completes (if configured)
- [ ] recording_url in database

#### 6.2 Transcription Pipeline
**Objective**: Verify Whisper transcription works

**Steps**:
1. Complete a test call with clear speech
2. Wait for async transcription (2-5 minutes)
3. Check CallLog.transcript
4. Verify accuracy

**Test Phrases** (say clearly during call):
- "My name is John Smith"
- "My phone number is 555-1234"
- "I am interested in your services"
- "Thank you for your help"

**Expected Results**:
- [ ] All phrases appear in transcript
- [ ] Accuracy > 85%
- [ ] Hebrew transcription works (if applicable)
- [ ] Timestamps included
- [ ] Speaker diarization (optional)

### 7. Error Handling Tests

#### 7.1 Network Failure
**Objective**: Verify graceful handling of network issues

**Simulate**:
```bash
# Disconnect Media Gateway from network
docker network disconnect prosaas-network prosaas-media-gateway

# Wait 30 seconds

# Reconnect
docker network connect prosaas-network prosaas-media-gateway
```

**Expected Results**:
- [ ] Active calls drop cleanly
- [ ] Recordings saved up to disconnect
- [ ] Services auto-reconnect
- [ ] New calls work after reconnect

#### 7.2 Asterisk Restart
**Objective**: Verify recovery from Asterisk restart

**Steps**:
```bash
# Restart Asterisk
docker restart prosaas-asterisk

# Wait for startup
sleep 10

# Make test call
```

**Expected Results**:
- [ ] Asterisk restarts cleanly
- [ ] ARI re-establishes connection
- [ ] Media Gateway reconnects
- [ ] New calls work immediately
- [ ] No orphaned channels

#### 7.3 OpenAI API Failure
**Objective**: Verify handling of AI API errors

**Simulate**:
Set invalid OpenAI API key and make test call

**Expected Results**:
- [ ] Call connects
- [ ] Error logged clearly
- [ ] Fallback message played (if configured)
- [ ] Call ends gracefully
- [ ] Error status in CallLog

### 8. Production Readiness

#### 8.1 Load Test
**Objective**: Verify system handles expected load

**Test Scenario**: 50 concurrent calls for 5 minutes

**Tools**:
- SIPp for load generation
- Monitor CPU, memory, network

**Expected Results**:
- [ ] All 50 calls connect successfully
- [ ] No dropped calls
- [ ] Audio quality maintained
- [ ] CPU < 80%
- [ ] Memory < 80%
- [ ] No errors in logs

#### 8.2 24-Hour Stability
**Objective**: Verify long-term stability

**Steps**:
1. Deploy to staging
2. Run automated calls every 5 minutes
3. Monitor for 24 hours
4. Check for memory leaks, errors

**Expected Results**:
- [ ] No service crashes
- [ ] No memory leaks
- [ ] All calls successful
- [ ] Consistent performance
- [ ] Clean logs (no warnings)

## Acceptance Criteria

### GO Criteria (all must pass):
- [x] Inbound calls work correctly
- [x] Outbound calls work correctly
- [x] Barge-in functions
- [x] Recordings captured from second 0
- [x] Transcription completes successfully
- [x] Voicemail detection works (15s)
- [x] Silence timeout works (20s)
- [x] Concurrent call limits enforced
- [x] No duplicate calls
- [x] Audio quality excellent
- [x] Latency acceptable (< 2s)
- [x] Error handling robust
- [x] Load test passes
- [x] Logs complete and useful

### NO-GO Criteria (any one fails):
- [ ] Audio quality poor
- [ ] High latency (> 3s)
- [ ] Recordings missing
- [ ] Transcription fails
- [ ] Duplicate calls made
- [ ] System instability
- [ ] Memory leaks detected
- [ ] Security vulnerabilities

## Sign-Off

After completing all tests:

```
✅ All tests passed
✅ System ready for production
✅ Migration can proceed

Tested by: _______________
Date: _______________
Signature: _______________
```

## Rollback Plan

If any NO-GO criteria triggered:

1. **Immediate**: Revert to Twilio
   ```bash
   # Change environment variable
   TELEPHONY_PROVIDER=twilio
   
   # Restart backend
   docker-compose -f docker-compose.yml restart backend
   ```

2. **Investigation**: Analyze logs and errors

3. **Fix**: Address issues

4. **Retest**: Run full test suite again

5. **Retry**: Attempt migration again

---

**Next Steps After Verification:**
1. Document any issues found
2. Deploy to staging for extended testing
3. Plan gradual production rollout
4. Monitor closely for first 48 hours
5. Full cutover to Asterisk
