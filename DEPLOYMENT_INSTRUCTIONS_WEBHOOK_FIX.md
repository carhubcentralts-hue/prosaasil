# 🚀 Deployment Instructions - Webhook City/Service Fix

## What Was Fixed

Fixed webhook `city` and `service_category` fields that were coming as empty, even though:
- ✅ Transcription was working
- ✅ Summary was accurate  
- ✅ Extraction logic was correct

**Root Cause**: Timing issue - webhook sent before offline extraction completed.

## Changes Made

### Modified Files:
- `server/media_ws_ai.py` - Fixed webhook wait logic (1 file changed)

### Key Changes:
1. ✅ Wait loop now checks for `extracted_city/service` instead of just `final_transcript`
2. ✅ Moved wait loop BEFORE fallback logic (was after)
3. ✅ Increased wait time to 15 seconds (3 attempts × 5 sec)
4. ✅ Added comprehensive logging

## Deployment Steps

### Option 1: Docker Restart (Recommended)
```bash
# Pull latest code
git pull origin cursor/fix-webhook-city-service-dbf0

# Restart services
docker-compose down
docker-compose up -d --build

# Verify logs
docker-compose logs -f backend | grep WEBHOOK
```

### Option 2: Process Restart
```bash
# Pull latest code
git pull origin cursor/fix-webhook-city-service-dbf0

# Restart the backend service
sudo systemctl restart prosaas-backend
# OR
pm2 restart prosaas-backend

# Check logs
pm2 logs prosaas-backend | grep WEBHOOK
```

## Testing After Deployment

### 1. Make a Test Call
Call your business number and say clearly:
```
"אני צריך תיקון מנעול חכם בבית שאן"
```

### 2. Wait for Processing
After call ends, wait ~20-30 seconds for:
- Recording download
- Transcription
- Summary generation
- **Extraction** (the new fixed part!)
- Webhook sending

### 3. Check Logs

**Look for these log lines:**

✅ **Extraction Success:**
```
[OFFLINE_EXTRACT] ✅ Extracted city from summary: 'בית שאן'
[OFFLINE_EXTRACT] ✅ Extracted service from summary: 'תיקון מנעול חכם'
```

✅ **Webhook Wait:**
```
⏳ [WEBHOOK] Waiting for offline extraction to complete...
✅ [WEBHOOK] Offline extraction found on attempt 2: city='בית שאן', service='תיקון מנעול חכם'
```

✅ **Final Status:**
```
📊 [WEBHOOK] Status after waiting for offline extraction:
   - city: 'בית שאן' (from_calllog: True)
   - service: 'תיקון מנעול חכם' (from_calllog: True)
```

✅ **Webhook Sent:**
```
[WEBHOOK] 📦 Payload built: call_id=CA..., phone=+972..., city=בית שאן
✅ [WEBHOOK] Call completed webhook queued: city=בית שאן, service=תיקון מנעול חכם
```

### 4. Verify Webhook Payload

Check your webhook endpoint (n8n, Zapier, etc.) received:
```json
{
  "event_type": "call.completed",
  "city": "בית שאן",                    ✅ NOT EMPTY
  "service_category": "תיקון מנעול חכם",  ✅ NOT EMPTY
  "summary": "...בית שאן...תיקון מנעול חכם...",
  ...
}
```

## Rollback Plan

If something goes wrong:

```bash
# Revert to previous version
git checkout HEAD~1 server/media_ws_ai.py

# Restart services
docker-compose restart backend
# OR
pm2 restart prosaas-backend
```

## Performance Impact

- **Wait time added**: 0-15 seconds per call (only when extraction pending)
- **User impact**: None (runs after call ends, in background thread)
- **Server load**: Minimal (just polling DB every 5 seconds)

## Success Criteria

✅ Webhook contains actual city name (not empty)  
✅ Webhook contains specific service type (not empty or generic)  
✅ Logs show extraction found and used  
✅ No regression in other webhook fields (phone, transcript, summary)  

## Support

If extraction still fails after 15 seconds:
1. Check offline worker is running
2. Check recording download succeeded
3. Check OpenAI API key is valid
4. Check sufficient API credits

Logs will show which step failed.

---

**Ready to Deploy**: ✅ Yes  
**Breaking Changes**: ❌ None  
**Database Migration**: ❌ Not needed (columns already exist)  
**Rollback Safe**: ✅ Yes
