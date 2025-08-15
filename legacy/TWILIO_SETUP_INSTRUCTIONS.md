# 📞 Twilio Setup Instructions - URGENT FIX

## 🚨 Current Problem
User hears "dott" and recording but NO greeting - this means wrong webhook URL in Twilio!

## ✅ Solution: Fix Twilio Webhook Configuration

### Step 1: Login to Twilio Console
Go to: https://console.twilio.com

### Step 2: Find Your Phone Number
1. Go to **Phone Numbers** → **Manage** → **Active numbers**
2. Click on your Israeli phone number (+972...)

### Step 3: Configure Webhook URL
In the **Voice Configuration** section:

**✅ CORRECT URL:**
```
https://ai-crmd.replit.app/webhook/incoming_call
```

**❌ WRONG URLs (don't use these):**
```
https://ai-crmd.replit.app//webhook/incoming_call  (double slash)
https://your-old-domain.com/webhook/incoming_call  (old domain)
http://localhost:5000/webhook/incoming_call       (localhost)
```

### Step 4: Set Method to POST
- Method: **POST**
- Primary handler URL: `https://ai-crmd.replit.app/webhook/incoming_call`

### Step 5: Save Configuration
Click **Save Configuration**

## 🧪 Test After Setup

Call your Twilio number. You should hear:
1. **English**: "Hello, you are speaking with Shai Apartments and Offices..."
2. **Hebrew**: "שלום, אתם מדברים עם שי דירות ומשרדים..."
3. **Beep** for recording

## 🔧 Verification

Our webhook is working correctly:
```bash
curl -X POST https://ai-crmd.replit.app/webhook/incoming_call \
  -d "From=+972501234567&CallSid=TEST"
```

Returns:
```xml
<Response>
  <Say voice="alice">Hello, you are speaking with Shai Apartments and Offices...</Say>
  <Say language="he" voice="alice">שלום, אתם מדברים עם שי דירות ומשרדים...</Say>
  <Record playBeep="true" maxLength="30" timeout="5" finishOnKey="*"/>
</Response>
```

## 🆘 If Still Not Working

1. **Check Twilio Debugger**: Go to Monitor → Debugger in Twilio Console
2. **Look for webhook errors**: Any 404, 500, or timeout errors
3. **Verify URL exactly**: No typos, extra slashes, or wrong domain

The system is ready - just need correct Twilio configuration! 🎯