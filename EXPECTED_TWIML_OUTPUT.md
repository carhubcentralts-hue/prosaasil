# Expected TwiML Output After Fix

## Incoming Call TwiML (CORRECT)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect action="https://prosaas.pro/webhook/stream_ended">
    <Stream track="inbound_track" url="wss://prosaas.pro/ws/twilio-media">
      <Parameter name="CallSid" value="CA19ccfe8b0c90c3b22c9fb591bf36aa25"/>
      <Parameter name="To" value="+97233762734"/>
    </Stream>
  </Connect>
</Response>
```

## Outbound Call TwiML (CORRECT)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect action="https://prosaas.pro/webhook/stream_ended">
    <Stream track="inbound_track" url="wss://prosaas.pro/ws/twilio-media">
      <Parameter name="CallSid" value="CA_OUTBOUND_123"/>
      <Parameter name="To" value="+972123456789"/>
      <Parameter name="direction" value="outbound"/>
      <Parameter name="lead_id" value="123"/>
      <Parameter name="lead_name" value="Test Lead"/>
      <Parameter name="business_id" value="10"/>
      <Parameter name="business_name" value="Example Business"/>
      <Parameter name="template_id" value="5"/>
    </Stream>
  </Connect>
</Response>
```

## Key Differences from Before

### ❌ BEFORE (Broken):
- Had `<Record maxLength="600" playBeep="false" recordingTrack="inbound" timeout="3" transcribe="false" />`
- This prevented WebSocket from connecting properly

### ✅ AFTER (Fixed):
- Clean `<Connect>` and `<Stream>` only
- WebSocket connects successfully
- Recording still happens (via Twilio's native recording mechanism)

## What to Check in Logs

When you make a test call, look for these log lines:

```
✅ call_log created immediately for CA19ccfe8b0c90c3b22c9fb591bf36aa25
[CALL_SETUP] Greeting mode: ai_only (no static Play/Say)
🔥 TWIML_HOST=prosaas.pro
🔥 TWIML_WS=wss://prosaas.pro/ws/twilio-media
🔥 TWIML_FULL=<?xml version="1.0" encoding="UTF-8"?><Response><Connect action="https://prosaas.pro/webhook/stream_ended"><Stream track="inbound_track" url="wss://prosaas.pro/ws/twilio-media">...
```

**Important**: Make sure `TWIML_FULL` does NOT contain `<Record` anywhere!

## WebSocket Connection Flow

1. **Twilio receives clean TwiML** → Only `<Connect>` + `<Stream>`
2. **WebSocket opens** → `wss://prosaas.pro/ws/twilio-media`
3. **Stream starts** → You should see `🎤 WS_START` in logs
4. **Audio flows** → Real-time processing works
5. **Stream ends** → `stream_ended` webhook triggered
6. **Recording retrieved** → From Twilio's API (not from TwiML `<Record>`)
7. **Offline STT runs** → Transcription happens
8. **Summary generated** → Post-call extraction completes

## Testing Checklist

After deploying this fix:

- [ ] Restart backend service
- [ ] Make a test incoming call
- [ ] Verify no `<Record` in TWIML_FULL log
- [ ] Verify `🎤 WS_START` appears in logs
- [ ] Verify `REALTIME` audio processing happens
- [ ] Call ends successfully
- [ ] Verify `[RECORDING] Stream ended` appears
- [ ] Verify `[OFFLINE_STT] Transcript obtained` appears
- [ ] Check call_log in database has transcription and summary
