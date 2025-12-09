# TwiML WebSocket Connection Fix

## Problem
The WebSocket connections were failing because the TwiML included a `<Record>` tag that interfered with the `<Stream>` connection.

### Before (Broken TwiML):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Record maxLength="600" playBeep="false" recordingTrack="inbound" timeout="3" transcribe="false" />
  <Connect action="https://prosaas.pro/webhook/stream_ended">
    <Stream track="inbound_track" url="wss://prosaas.pro/ws/twilio-media">
      <Parameter name="CallSid" value="CA19ccfe8b0c90c3b22c9fb591bf36aa25" />
      <Parameter name="To" value="+97233762734" />
    </Stream>
  </Connect>
</Response>
```

### After (Fixed TwiML):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect action="https://prosaas.pro/webhook/stream_ended">
    <Stream track="inbound_track" url="wss://prosaas.pro/ws/twilio-media">
      <Parameter name="CallSid" value="CA19ccfe8b0c90c3b22c9fb591bf36aa25" />
      <Parameter name="To" value="+97233762734" />
    </Stream>
  </Connect>
</Response>
```

## Changes Made

### File: `server/routes_twilio.py`

**1. incoming_call() function (lines 459-465)**
- ❌ Removed: `vr.record()` call with all its parameters
- ✅ Kept: Clean `<Connect>` and `<Stream>` structure

**2. outbound_call() function (lines 566-572)**
- ❌ Removed: `vr.record()` call with all its parameters  
- ✅ Kept: Clean `<Connect>` and `<Stream>` structure

## What Was NOT Changed (Working Correctly)
- ✅ `stream_ended` webhook - triggers recording after stream ends
- ✅ `_trigger_recording_for_call()` - handles recording retrieval
- ✅ `tasks_recording.py` - offline STT worker
- ✅ `recording_service.py` - recording download and processing
- ✅ All recording and transcription logic remains intact

## How It Works Now

1. **Call starts** → Clean TwiML with only `<Connect>` + `<Stream>` sent to Twilio
2. **WebSocket opens** → Real-time audio streaming works properly
3. **Stream ends** → `stream_ended` webhook triggers
4. **Recording retrieved** → Twilio's native recording is fetched
5. **Offline STT** → Recording is transcribed asynchronously
6. **Summary generated** → Post-call extraction runs

## Expected Logs After Fix

### During Call:
```
✅ call_log created immediately for CA19ccfe8b0c90c3b22c9fb591bf36aa25
[CALL_SETUP] Greeting mode: ai_only (no static Play/Say)
🔥 TWIML_HOST=prosaas.pro
🔥 TWIML_WS=wss://prosaas.pro/ws/twilio-media
🔥 TWIML_FULL=<?xml version="1.0" encoding="UTF-8"?><Response><Connect action="https://prosaas.pro/webhook/stream_ended"><Stream track="inbound_track" url="wss://prosaas.pro/ws/twilio-media">...
```

### WebSocket Events:
```
🎤 WS_START - call_sid=CA19ccfe8b0c90c3b22c9fb591bf36aa25
🎤 REALTIME - Processing audio chunks
```

### After Call Ends:
```
[RECORDING] Stream ended → safe to start recording for CA19ccfe8b0c90c3b22c9fb591bf36aa25
✅ Found existing recording for CA19ccfe8b0c90c3b22c9fb591bf36aa25
[OFFLINE_STT] Transcript obtained from Whisper API
✅ Post-call extraction complete
```

## Verification Steps

1. **Restart backend**
2. **Make test call**
3. **Check logs for**:
   - ✅ No `<Record>` in TWIML_FULL
   - ✅ WS_START event appears
   - ✅ REALTIME audio processing
   - ✅ [OFFLINE_STT] after call ends
   - ✅ Recording and transcription complete

## Why This Fix Works

The `<Record>` tag in TwiML creates a separate recording session that conflicts with the `<Stream>` WebSocket connection. By removing it:

- WebSocket connections establish properly
- Real-time audio streaming works
- Twilio still creates its own native recording
- We fetch the recording after the call via the API
- Offline STT and post-call processing work as before

**The recording happens through Twilio's native mechanism, not through the TwiML `<Record>` tag.**
