# BUILD 350: Testing Guide

## 🧪 How to Test the Implementation

### Test 1: Verify No Mid-Call Tools Load

**What to check**: During a call, ensure NO tool-related logs appear

**Expected behavior**:
```
✅ [BUILD 350] Tool loading DISABLED - pure conversation mode
```

**NOT expected** (these should NOT appear):
```
❌ ✅ [BUILD 329] Tool added ONCE
❌ 🔧 [BUILD 313] Tool schema built for fields: [...]
❌ 🔧 [BUILD 313] Function call received!
```

**How to verify**:
1. Start a test call (inbound or outbound)
2. Watch logs during greeting
3. Confirm you see "Tool loading DISABLED" message
4. Confirm you DON'T see any "Tool added" or "Tool schema" messages

---

### Test 2: Verify No City Lock During Call

**What to check**: User mentions city, but no "CITY LOCKED" logs appear during call

**Test conversation**:
```
AI: "שלום! במה אוכל לעזור?"
User: "אני צריך חשמלאי בתל אביב"
```

**Expected behavior**:
```
🤖 [REALTIME] AI said: [AI response about electrical service]
```

**NOT expected** (these should NOT appear):
```
❌ 🔒 [BUILD 336] CITY LOCKED from STT: 'תל אביב'
❌ 🔒 [BUILD 336] SERVICE LOCKED from STT: 'חשמלאי'
```

**How to verify**:
1. Start a call
2. User mentions both city and service
3. Check logs - confirm NO "LOCKED" messages
4. Call continues naturally with NO field extraction

---

### Test 3: Verify No Mid-Call NLP for Appointments

**What to check**: User mentions appointment, but NO NLP parser runs during call

**Test conversation**:
```
AI: "אוכל לקבוע לך פגישה?"
User: "כן, בבקשה"
```

**Expected behavior** (with ENABLE_LEGACY_TOOLS = False):
```
✅ [BUILD 350] lead_capture_state IGNORED - using summary-only extraction
```

**NOT expected** (these should NOT appear):
```
❌ 🔍 [NLP] ▶️ Analyzing conversation for appointment intent...
❌ 🎯 [NLP] ✅ Detected action=schedule_appointment
```

**How to verify**:
1. Start a call with appointments enabled
2. Have conversation about scheduling
3. Check logs - confirm NO "[NLP]" messages during call
4. Simple keyword detection may log: "📅 [BUILD 350] Appointment keyword detected"

---

### Test 4: Verify Summary-Based Extraction Works

**What to check**: At END of call, service and city are extracted from transcript

**Test conversation**:
```
AI: "שלום! במה אוכל לעזור?"
User: "אני צריך חשמלאי"
AI: "בסדר, באיזו עיר?"
User: "תל אביב"
AI: "אוקיי, אז אתה צריך חשמלאי בתל אביב, נכון?"
User: "כן"
[Call ends]
```

**Expected behavior at END**:
```
🎯 [WEBHOOK] Extracted SPECIFIC service from AI confirmation: 'חשמלאי'
📋 [WEBHOOK] Enriching from Lead #123
✅ [WEBHOOK] Call completed webhook queued: phone=+972..., city=תל אביב, service=חשמלאי
```

**How to verify**:
1. Complete a full call with city and service mentioned
2. Wait for call to end
3. Check logs for "[WEBHOOK]" section
4. Confirm service and city are extracted from transcript
5. Confirm webhook payload contains correct data

---

### Test 5: Verify Keyword-Based Appointment Detection

**What to check**: When AI mentions appointment keyword, detection triggers

**Test scenario** (appointments enabled):
```
AI: "מעולה! קבעתי לך פגישה ליום שני בשעה 10:00"
```

**Expected behavior**:
```
📅 [BUILD 350] Appointment keyword detected: 'קבעתי' in AI response
📅 [BUILD 350] AI said: מעולה! קבעתי לך פגישה...
📅 [BUILD 350] Simple appointment detection triggered
```

**How to verify**:
1. Enable appointments in business settings
2. Start a call
3. Have AI mention appointment-related keywords
4. Check logs for "📅 [BUILD 350]" messages
5. Verify detection happens WITHOUT NLP parsing

---

### Test 6: Verify Legacy Mode Still Works

**What to check**: Setting ENABLE_LEGACY_TOOLS = True re-enables old behavior

**How to test**:
1. Edit `server/media_ws_ai.py` line ~98:
   ```python
   ENABLE_LEGACY_TOOLS = True  # Temporarily enable
   ```
2. Restart server
3. Start a call
4. Watch logs - should see OLD behavior:
   ```
   ✅ [LEGACY] Tool added
   🔒 [BUILD 336] CITY LOCKED from STT: '...'
   🔍 [LEGACY DEBUG] Calling NLP after user transcript
   ```
5. Change back to `False` and restart

**Purpose**: Ensures we didn't break anything - legacy code is preserved

---

## 🎯 Quick Checklist

Before marking BUILD 350 as complete, verify:

- [ ] Flag is set: `ENABLE_LEGACY_TOOLS = False`
- [ ] No tool logs during call startup
- [ ] No "CITY LOCKED" or "SERVICE LOCKED" during call
- [ ] No "[NLP]" logs during call (when legacy disabled)
- [ ] Simple keyword detection works (appointments enabled)
- [ ] Service extracted from transcript at END of call
- [ ] City extracted from transcript at END of call
- [ ] Webhook receives correct data from summary
- [ ] Python files compile without errors
- [ ] Verification script passes

---

## 📊 Log Patterns Reference

### ✅ CORRECT (BUILD 350 Active)
```
🟢 ✅ [BUILD 350] Tool loading DISABLED - pure conversation mode
🟢 ✅ [BUILD 350] lead_capture_state IGNORED - using summary-only extraction
🟢 📅 [BUILD 350] Appointment keyword detected: 'פגישה'
🟢 🎯 [WEBHOOK] Extracted SPECIFIC service from AI confirmation: '...'
```

### ❌ INCORRECT (Legacy Mode Active)
```
🔴 ✅ [BUILD 329] Tool added ONCE (no prompt resend)
🔴 🔒 [BUILD 336] CITY LOCKED from STT: '...'
🔴 🔒 [BUILD 336] SERVICE LOCKED from STT: '...'
🔴 🔍 [NLP] ▶️ Analyzing conversation for appointment intent...
🔴 📋 [WEBHOOK] Lead capture state: {...}
```

---

## 🚀 Next Steps After Testing

1. Run several test calls (inbound + outbound)
2. Verify webhook payloads contain correct data
3. Test with appointments enabled and disabled
4. Test with different cities and services
5. Verify summary quality is good
6. Monitor production for a few days
7. If stable, can remove legacy code entirely (optional)

---

## 📞 Support

If you encounter issues:
1. Check `ENABLE_LEGACY_TOOLS` flag is set correctly
2. Review logs for BUILD 350 markers
3. Verify Python syntax with: `python3 -m py_compile server/media_ws_ai.py`
4. Run verification script: `./verify_build_350.sh`
5. Compare logs with patterns above

---

**BUILD 350 Testing Guide Complete** ✅
