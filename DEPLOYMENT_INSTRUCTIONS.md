# 🚀 AgentLocator 71 - Deployment Instructions

## Environment Variables Setup (CRITICAL)

### In Replit Deployments → Environment Variables:

```bash
# Version Tracking (update for each deployment)
GIT_COMMIT=AgentLocator-71-v1.2.3
BUILD_TIME=2025-08-24T20:15Z
DEPLOY_ID=RPLT-20250824-2015

# Core Application
PUBLIC_BASE_URL=https://ai-crmd.replit.app
DATABASE_URL=postgresql://...

# Twilio (REQUIRED for watchdog system)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=your_auth_token

# OpenAI
OPENAI_API_KEY=sk-...

# Google Cloud (TTS/STT) - Use ONE of these methods:
# Method 1: JSON content
GCP_CREDENTIALS_JSON={"type":"service_account",...}
# Method 2: File path  
GOOGLE_APPLICATION_CREDENTIALS=/path/to/gcp.json
```

## Deployment Configuration

### Build Command:
```bash
pip install --no-cache-dir -r AgentLocator/requirements.txt
```

### Run Command (CRITICAL - must use eventlet):
```bash
python3 -m gunicorn -k eventlet -w 1 -b 0.0.0.0:$PORT AgentLocator.main:app
```

## Pre-Deployment Checklist

- [ ] Update `DEPLOY_ID` to new unique value
- [ ] Ensure `GIT_COMMIT` matches current version
- [ ] Verify all environment variables are set in Deployment (not just Workspace)
- [ ] Close any running Workspace "Run" processes
- [ ] Delete any old/conflicting deployments

## Post-Deployment Validation

### Automatic Validation:
```bash
python3 deployment_validation.py https://ai-crmd.replit.app
```

### Manual Validation:

1. **Version Check:**
   ```bash
   curl -s https://ai-crmd.replit.app/version | jq
   ```
   Should return current `DEPLOY_ID` and `GIT_COMMIT`

2. **Cache Headers:**
   ```bash
   curl -I https://ai-crmd.replit.app/webhook/incoming_call
   ```
   Should include `Cache-Control: no-store, no-cache`

3. **Static Files:**
   ```bash
   curl -I https://ai-crmd.replit.app/static/tts/greeting_he.mp3  # 200
   curl -I https://ai-crmd.replit.app/static/tts/fallback_he.mp3  # 200
   ```

4. **Health Check:**
   ```bash
   curl https://ai-crmd.replit.app/healthz  # "ok"
   ```

5. **WebSocket Test:**
   - Open websocketking.com
   - Connect to: `wss://ai-crmd.replit.app/ws/twilio-media`
   - Should get "Connected (101)"

## Live Call Testing

1. **Expected Log Sequence:**
   ```
   🚩 APP_START {"app":"AgentLocator-71","deploy_id":"RPLT-20250824-2015",...}
   WS_CONNECTED (hebrew_realtime: true/false)
   WS_START (streamSid, call_sid, hebrew_asr: active)
   HEBREW_SPEECH (text, final: true/false) 
   PING_PONG_TX (call_sid, response_url)
   ```

2. **Fallback Test (if WebSocket fails):**
   ```
   WATCHDOG_REDIRECT (no_stream_start/no_media)
   WATCHDOG_REDIRECT_OK
   POST /webhook/handle_recording (200/204)
   ```

## Troubleshooting Common Issues

### "Deployment running old code"
- Verify `APP_START` log shows new `DEPLOY_ID`
- Update `DEPLOY_ID` to force rebuild
- Use `--no-cache-dir` in build command

### "Greeting then silence"
- Check WebSocket 101 connection
- Verify eventlet in run command (`-k eventlet`)
- Check Twilio credentials in deployment ENV
- Look for `WATCHDOG_REDIRECT_OK` within 6 seconds

### "404 on health endpoints" 
- Deployment not updated - check `DEPLOY_ID` mismatch
- Close workspace Run processes

### "WebSocket 31920 handshake error"
- Missing `-k eventlet` in run command
- Port conflicts (close other services)
- ProxyFix configuration issue

## Force Rebuild Process

If deployment seems cached:

1. Update `DEPLOY_ID` to new unique value
2. Use `--no-cache-dir` in build command  
3. Restart deployment completely
4. Verify new version with `/version` endpoint

## Success Criteria

✅ `/version` returns new `DEPLOY_ID`  
✅ TwiML includes cache-busting headers  
✅ WebSocket connects (101 response)  
✅ Health endpoints return 200  
✅ Live call: either Hebrew conversation OR watchdog redirect (no silence)  

When all criteria pass, the deployment is successful and "greeting then silence" issue is resolved.