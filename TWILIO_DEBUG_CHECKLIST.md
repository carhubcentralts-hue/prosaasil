# Twilio Debug Checklist - Hebrew AI Call Center

## Current Status
Date: August 16, 2025
Domain: ai-crmd.replit.app  
Issue: Calls are silent, webhooks not reaching our server

## Twilio Console Verification Steps

### 1. Phone Number Configuration
1. Go to Twilio Console → Phone Numbers → Active Numbers
2. Click on your phone number
3. In "Voice & Fax" section verify:
   - **A call comes in**: Must be "Webhook"
   - **URL**: Must be exactly `https://ai-crmd.replit.app/webhook/incoming_call`
   - **HTTP Method**: Must be "POST"

### 2. Domain Verification Test
Test our webhook manually:
```bash
curl -X POST "https://ai-crmd.replit.app/webhook/incoming_call" \
  -d "CallSid=MANUAL_TEST&From=%2B972501234567&To=%2B972337636805" \
  -H "Content-Type: application/x-www-form-urlencoded"
```

Expected response: TwiML with Hebrew greeting and Stream connection

### 3. Debug File Check
After calling, check if debug file exists:
```bash
ls -la /tmp/webhook_debug.log
```

If file doesn't exist → webhook not reaching our server
If file exists → webhook works, check TTS/audio setup

## Solution Steps
1. ✅ Verify Twilio Console URL is correct
2. ✅ Test webhook manually  
3. ✅ Make test call
4. ✅ Check debug logs

## Expected Behavior
When calling the number, you should hear:
"שלום, הגעתם לשי דירות ומשרדים בע״מ. אנא המתינו רגע ונחבר אתכם למערכת."

Then the call should connect to WebSocket for AI conversation.
