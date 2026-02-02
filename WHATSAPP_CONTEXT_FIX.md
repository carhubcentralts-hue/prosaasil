# WhatsApp Context Loss Fix - Root Cause Analysis

## Problem Discovered

Bot loses context and repeats questions because:
1. **Baileys drops outgoing messages** (`fromMe: true`) without persisting them
2. **Flask saves outgoing** but **doesn't set `lead_id`** so they're not loaded in history
3. **No dedupe** before AI call → duplicate messages trigger duplicate responses

## Root Cause Code Locations

### Issue A: Baileys Skips Outgoing
**File:** `services/whatsapp/baileys_service.js:1710`
```javascript
if (incomingMessages.length === 0) {
  console.log(`[${tenantId}] ⏭️ Skipping ${validMessages.length} outgoing message(s) (fromMe: true)`);
  return;  // ❌ DROPS OUTGOING!
}
```

### Issue B: Flask Saves Outgoing WITHOUT lead_id
**File:** `server/jobs/webhook_process_job.py:404-415`
```python
outgoing_msg = WhatsAppMessage()
outgoing_msg.business_id = business_id
outgoing_msg.to_number = phone_number
outgoing_msg.direction = 'out'
outgoing_msg.body = ai_response
# ❌ MISSING: outgoing_msg.lead_id = lead.id
db.session.add(outgoing_msg)
```

### Issue C: History Load Filters by lead_id
**File:** `server/services/unified_lead_context_service.py:679-683`
```python
messages = WhatsAppMessage.query.filter(
    WhatsAppMessage.lead_id == lead.id,  # ❌ Outgoing has lead_id=NULL!
    WhatsAppMessage.business_id == self.business_id
).order_by(WhatsAppMessage.timestamp.desc()).limit(20).all()
```
**Result:** Only loads `direction='in'` messages because outgoing has `lead_id=NULL`.

### Issue D: No Dedupe Before AI
**File:** `server/routes_whatsapp.py` or webhook handler
- ❌ Missing dedupe check by `(business_id, message_id, remoteJid)`
- Same message → triggers AI twice → duplicate responses

## Fix Summary

### Fix A: Add lead_id to outgoing messages
### Fix B: Load history by (business_id + phone) OR lead_id
### Fix C: Add dedupe before AI call
### Fix D: Keep Baileys filter (it's correct - we want incoming only there)

---

## Verification Checklist

After fix, verify:
- [ ] Outgoing messages have `lead_id` populated
- [ ] History includes both `direction='in'` AND `direction='out'`
- [ ] Bot doesn't repeat same question
- [ ] Duplicate message_id triggers dedupe log
- [ ] Conversation flows naturally for 5+ turns
