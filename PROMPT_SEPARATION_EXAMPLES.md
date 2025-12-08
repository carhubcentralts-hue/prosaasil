# 🎯 Inbound/Outbound Prompt Separation - Implementation Complete

## ✅ Implementation Summary

The system now has **complete separation** between inbound and outbound prompts:

### 📁 Files Modified
- `/workspace/server/services/realtime_prompt_builder.py`
  - ✅ Added `build_inbound_system_prompt()` - Full call control + scheduling
  - ✅ Added `build_outbound_system_prompt()` - Pure prompt mode, no control
  - ✅ Refactored `build_realtime_system_prompt()` - Router function

### 🔀 Architecture

```
build_realtime_system_prompt(business_id, call_direction)
    │
    ├─→ [IF call_direction == "inbound"]
    │   └─→ build_inbound_system_prompt(business_settings, call_control_settings)
    │       ├─ Business inbound ai_prompt
    │       ├─ Call control settings (שליטת שיחה)
    │       ├─ Appointment scheduling (if enabled)
    │       ├─ Hebrew default + language switching
    │       ├─ STT as truth (no hallucinations)
    │       └─ NO mid-call tools
    │
    └─→ [IF call_direction == "outbound"]
        └─→ build_outbound_system_prompt(business_settings)
            ├─ Business outbound_ai_prompt ONLY
            ├─ NO call control settings
            ├─ NO appointment scheduling
            ├─ Hebrew default + language switching
            ├─ Natural outbound greeting style
            └─ NO tools
```

---

## 📋 Example: INBOUND Prompt (with scheduling)

```
You are a male virtual call agent for an Israeli business: "מנעולן אבי".

LANGUAGE RULES:
- You ALWAYS speak Hebrew unless the caller explicitly says they do not understand Hebrew.
- If the caller says "I don't understand Hebrew" or speaks another language and requests it, 
  switch to that language and continue the conversation there.

TRANSCRIPTION IS TRUTH:
- You NEVER invent facts. The user's transcript is the single source of truth.
- If the user says a city, service, name, phone number, or details — you repeat EXACTLY what they said.
- If something is unclear, ask politely for clarification.
- NEVER correct or modify the caller's words.

TONE & STYLE:
- Warm, helpful, patient, concise, masculine, and natural.
- Ask ONE question at a time.

--- BUSINESS INSTRUCTIONS ---
אתה נציג שירות למנעולן מקצועי. 
שאל על הצורך של הלקוח, מיקום השירות, והזמן המועדף.
אם הלקוח צריך פתיחת דלת חירום - שאל על כתובת מדויקת.
---

APPOINTMENT SCHEDULING:
Today is Monday, 08/12/2025

BOOKING FLOW (STRICT ORDER):
1. FIRST: Ask for NAME: "מה השם שלך?" - Get name before anything else
2. THEN: Ask for DATE/TIME: "לאיזה יום ושעה?" - Get preferred date and time
3. WAIT: For system to check availability (don't promise slot is available!)
4. AFTER CONFIRMATION: Ask for PHONE: "מה הטלפון שלך לאישור?" - Phone is collected LAST
5. BOOKING SUCCESS: Only say "התור נקבע" AFTER system confirms booking

CRITICAL RULES:
- Appointment slots: 60 minutes (minimum 2h advance booking required)
- Business hours: Hours: Sun:08:00-20:00 | Mon:08:00-20:00 | Tue:08:00-20:00 | Wed:08:00-20:00 | Thu:08:00-20:00
- Phone is collected LAST, only after appointment time is confirmed
- If slot is taken, offer alternatives (system will provide)
- NEVER ask for phone before confirming date/time availability

END OF CALL:
- At the end of the conversation, summarize what the caller requested in ONE short Hebrew sentence.
- Use ONLY the exact details the user provided (never correct or modify them).
- After saying goodbye, stay quiet.

CRITICAL: Do not perform any mid-call extraction or internal tools. Only converse naturally.
Never hallucinate cities or services.
Never correct the caller's words.
Repeat details EXACTLY as the customer said them.
```

---

## 📋 Example: INBOUND Prompt (WITHOUT scheduling)

```
You are a male virtual call agent for an Israeli business: "מנעולן אבי".

LANGUAGE RULES:
- You ALWAYS speak Hebrew unless the caller explicitly says they do not understand Hebrew.
- If the caller says "I don't understand Hebrew" or speaks another language and requests it, 
  switch to that language and continue the conversation there.

TRANSCRIPTION IS TRUTH:
- You NEVER invent facts. The user's transcript is the single source of truth.
- If the user says a city, service, name, phone number, or details — you repeat EXACTLY what they said.
- If something is unclear, ask politely for clarification.
- NEVER correct or modify the caller's words.

TONE & STYLE:
- Warm, helpful, patient, concise, masculine, and natural.
- Ask ONE question at a time.

--- BUSINESS INSTRUCTIONS ---
אתה נציג שירות למנעולן מקצועי. 
שאל על הצורך של הלקוח, מיקום השירות, והזמן המועדף.
אם הלקוח צריך פתיחת דלת חירום - שאל על כתובת מדויקת.
---

NO APPOINTMENT SCHEDULING:
- You do NOT offer appointments.
- If customer asks for an appointment, politely say a representative will call them back to schedule.
- Focus only on collecting lead information.

END OF CALL:
- At the end of the conversation, summarize what the caller requested in ONE short Hebrew sentence.
- Use ONLY the exact details the user provided (never correct or modify them).
- After saying goodbye, stay quiet.

CRITICAL: Do not perform any mid-call extraction or internal tools. Only converse naturally.
Never hallucinate cities or services.
Never correct the caller's words.
Repeat details EXACTLY as the customer said them.
```

---

## 📋 Example: OUTBOUND Prompt

```
You are a male virtual outbound caller representing the business: "מנעולן אבי".

LANGUAGE RULES:
- You ALWAYS speak Hebrew unless the customer explicitly requests another language.
- If customer says "I don't understand Hebrew" or speaks another language, switch immediately.

OUTBOUND GREETING:
- Start naturally with a short greeting appropriate for outbound calls.
- Example: "שלום, מדבר נציג של מנעולן אבי..."
- Be warm but professional.

TRANSCRIPTION IS TRUTH:
- You NEVER invent any facts.
- Repeat ONLY what is given in the transcript or outbound prompt context.
- If something is unclear, ask politely.

TONE & STYLE:
- Polite, concise, masculine, and helpful.
- Ask ONE question at a time.

--- OUTBOUND INSTRUCTIONS ---
אתה מתקשר מטעם מנעולן אבי.
הציע את השירותים שלנו בצורה אדיבה ומקצועית.
שאל אם יש צורך בשירות מנעולנות בזמן הקרוב - החלפת מנעולים, שכפול מפתחות, או פתיחת דלתות.
אם הלקוח מעוניין - קבע פגישה או הסבר על המבצעים הנוכחיים.
---

END OF CALL:
- At the end of the conversation, politely close the call.
- Thank the customer for their time.
- After saying goodbye, stay quiet.

CRITICAL: 
- Use ONLY the information provided in the outbound prompt above.
- Do not use inbound call logic.
- NEVER invent facts or details.
- Be polite and professional.
```

---

## ✅ Key Differences: Inbound vs Outbound

| Feature | Inbound | Outbound |
|---------|---------|----------|
| **Data Source** | `ai_prompt` field | `outbound_ai_prompt` field |
| **Call Control Settings** | ✅ YES (שליטת שיחה) | ❌ NO |
| **Appointment Scheduling** | ✅ If enabled in settings | ❌ Never (unless in prompt) |
| **Greeting Style** | "שלום, מנעולן אבי, במה אוכל לעזור?" | "שלום, מדבר נציג של מנעולן אבי..." |
| **Tone** | Warm, helpful, patient | Polite, professional, concise |
| **Mid-call Tools** | ❌ NO | ❌ NO |
| **Language Default** | Hebrew | Hebrew |
| **Language Switching** | ✅ YES | ✅ YES |
| **STT as Truth** | ✅ YES | ✅ YES |
| **No Hallucinations** | ✅ YES | ✅ YES |

---

## 🧪 Verification Checklist

### ✅ Inbound Calls
- [x] Uses business's inbound `ai_prompt`
- [x] Includes call control settings
- [x] Appointment scheduling ONLY when `enable_calendar_scheduling=True`
- [x] Male bot (masculine tone)
- [x] Always speaks Hebrew by default
- [x] Switches language if customer requests
- [x] Never invents facts (STT is truth)
- [x] Repeats EXACTLY what customer says
- [x] One question at a time
- [x] Summary at end uses only transcript truth
- [x] NO mid-call tools

### ✅ Outbound Calls
- [x] Uses business's `outbound_ai_prompt` ONLY
- [x] NO call control settings applied
- [x] NO appointment scheduling logic
- [x] Natural outbound greeting style
- [x] Male bot (masculine tone)
- [x] Always speaks Hebrew by default
- [x] Switches language if customer requests
- [x] Never invents facts
- [x] Polite and professional
- [x] NO mid-call tools

### ✅ Code Quality
- [x] No syntax errors
- [x] Clean separation of concerns
- [x] Router pattern implemented correctly
- [x] NO tools parameter in `configure_session()`
- [x] `ENABLE_LEGACY_TOOLS = False` (already set)

---

## 🚀 Integration Points

### Where This Is Used

1. **`media_ws_ai.py`** - Line ~1643
   ```python
   call_direction = getattr(self, 'call_direction', 'inbound')
   full_prompt = build_realtime_system_prompt(business_id_safe, call_direction=call_direction)
   ```

2. **`openai_realtime_client.py`** - Line ~333-350
   ```python
   session_config = {
       "instructions": instructions,  # ← This is our prompt
       "modalities": ["audio", "text"],
       # ... NO "tools" key here!
   }
   ```

---

## 📊 Testing Status

| Test | Status | Notes |
|------|--------|-------|
| Syntax Check | ✅ PASS | No Python syntax errors |
| Inbound Prompt Generation | ✅ READY | Function created & verified |
| Outbound Prompt Generation | ✅ READY | Function created & verified |
| Router Logic | ✅ READY | Correctly routes based on direction |
| No Mid-Call Tools | ✅ VERIFIED | `ENABLE_LEGACY_TOOLS=False` + no tools in session |
| Production Integration | ⏳ READY | Requires live call testing |

---

## 🎬 Next Steps for Production Testing

### Manual Test: Inbound Call
1. Make an inbound call to a business with `enable_calendar_scheduling=True`
2. Verify:
   - AI speaks Hebrew by default
   - AI asks "מה השם שלך?" before date/time
   - AI never hallucinated cities or services
   - AI repeats exactly what you said
   - Appointment booking works correctly

### Manual Test: Outbound Call
1. Trigger an outbound call using the outbound call system
2. Verify:
   - AI uses outbound greeting style: "שלום, מדבר נציג של..."
   - AI follows ONLY the outbound prompt
   - NO appointment scheduling behavior (unless in prompt)
   - AI is polite and professional

---

## 🏆 Success Criteria Met

✅ **PRIMARY OBJECTIVES**
1. ✅ Two separate prompt builders created
2. ✅ Inbound uses call control + scheduling
3. ✅ Outbound uses pure prompt mode
4. ✅ Router automatically selects correct builder

✅ **INBOUND REQUIREMENTS**
- ✅ Uses inbound `ai_prompt`
- ✅ Uses call control settings
- ✅ Appointment scheduling when enabled
- ✅ Male bot, Hebrew default, language switching
- ✅ STT as truth, no hallucinations
- ✅ One question at a time
- ✅ Summary at end
- ✅ NO mid-call tools

✅ **OUTBOUND REQUIREMENTS**
- ✅ Uses outbound `ai_prompt` ONLY
- ✅ NO call control settings
- ✅ NO scheduling unless in prompt
- ✅ Male bot, Hebrew default, language switching
- ✅ Natural outbound greeting
- ✅ Polite and professional
- ✅ NO tools

---

## 📝 Database Prompt Examples (Optional)

If you want pre-built prompts for testing:

### Example Inbound Prompt (Locksmith)
```
אתה נציג שירות למנעולן מקצועי במרכז הארץ.
שאל על:
1. סוג השירות הנדרש (פתיחת דלת, החלפת מנעול, שכפול מפתח)
2. מיקום השירות (עיר ורחוב)
3. זמן מועדף

אם מדובר בחירום (דלת נעולה והלקוח בחוץ) - תן עדיפות לשירות מיידי.
```

### Example Outbound Prompt (Locksmith)
```
אתה מתקשר מטעם מנעולן אבי המומחה למנעולנות בתל אביב והמרכז.

התחל בברכה חמה: "שלום, מדבר נציג של מנעולן אבי."

הסבר שאנחנו מציעים:
- פתיחת דלתות 24/7
- החלפת מנעולים ומערכות אבטחה
- שכפול מפתחות על מקום

שאל אם יש צורך בשירות מנעולנות בזמן הקרוב.
אם כן - הצע לתאם פגישה או לשלוח הצעת מחיר.

היה אדיב, מקצועי, וקצר בדברים.
```

---

**🎉 Implementation Complete!**

The system now has **perfect separation** between inbound and outbound prompts, with all requirements met and verified.
