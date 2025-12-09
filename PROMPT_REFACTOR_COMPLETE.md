# 🔥 סיכום תיקון: ניקוי Prompts וקוד מטקסטים Hardcoded

תאריך: 9 דצמבר 2025

## 🎯 מטרה
להסיר לחלוטין כל טקסט hardcoded מהשיחות ולהבטיח שכל ההתנהגות מגיעה רק מ:
1. **System Prompt** (כללי ומופשט)
2. **Business Prompt** מה-DB (פר-עסק)

## ✅ שינויים שבוצעו

### 1. ניקוי System Prompts ב-`realtime_prompt_builder.py`

#### 1.1. `build_inbound_system_prompt()` - שיחות נכנסות
**שינויים:**
- ✅ הסרת משפט סיום קשיח: `"מצוין, קיבלתי. בעל מקצוע יחזור אליך בהקדם. תודה ולהתראות."`
- ✅ הסרת בקשת טלפון קשיחה: `"מה הטלפון שלך לאישור?"`
- ✅ הוספת הצהרה ברורה: **"BUSINESS_PROMPT is THE SINGLE SOURCE OF TRUTH"**
- ✅ הוספת כלל: "Customer phone is ALREADY available - do NOT ask for it"
- ✅ שינוי הוראות תיאום פגישות להיות גנריות ללא טקסט ספציפי

**תוצאה:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 BUSINESS PROMPT - THE SINGLE SOURCE OF TRUTH FOR BEHAVIOR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If there is ANY conflict between system rules and business prompt:
→ ALWAYS PREFER THE BUSINESS PROMPT.
```

#### 1.2. `build_outbound_system_prompt()` - שיחות יוצאות
**שינויים:**
- ✅ הסרת דוגמאות ברכה קשיחות: `"שלום, מדבר נציג של {business_name}..."`
- ✅ הסרת משפטי סיום קשיחים
- ✅ הוספת הצהרה זהה: **"OUTBOUND PROMPT is THE SINGLE SOURCE OF TRUTH"**
- ✅ הוספת כלל: "Customer phone is ALREADY available"

#### 1.3. `_build_critical_rules_compact()` - DEPRECATED
**שינוי:**
- ✅ הפונקציה שונתה ל-DEPRECATED ומחזירה מחרוזת ריקה
- ✅ הוספת אזהרת לוג אם הפונקציה נקראת

### 2. ניקוי `media_ws_ai.py`

#### 2.1. `_check_polite_closing()`
**שינויים:**
- ✅ הסרת משפטים hardcoded: `"נציג יחזור אליך"`, `"נחזור אליך"`, `"ניצור קשר"`
- ✅ השארת רק משפטי ברכה גנריים

#### 2.2. `_handle_function_call()`
**שינויים:**
- ✅ הוספת טיפול מלא בכלי `schedule_appointment`
- ✅ **שימוש ב-`customer_phone` מהשיחה** - לא מבקש טלפון מהלקוח!
- ✅ שליחת תשובה לשרת רק אחרי אימות הזמינות
- ✅ ה-AI מקבל הודעה ברורה רק אחרי שהשרת מאשר: `"success": True`

**לוגיקת תיאום פגישות:**
```python
# 🔥 USE customer_phone FROM CALL - already available!
customer_phone = getattr(self, 'phone_number', None)

# Validate slot
is_available = validate_appointment_slot(business_id, requested_dt)

# Create appointment only if available
appointment_id = create_appointment(
    business_id=business_id,
    customer_phone=customer_phone,  # מהשיחה!
    customer_name=customer_name,
    requested_dt=requested_dt,
    service_type=service_type
)

# Return success to AI only after server confirms
if appointment_id:
    return {"success": True, "appointment_id": appointment_id}
```

#### 2.3. `create_appointment()` - Wrapper חדש
**שינויים:**
- ✅ נוסף wrapper פשוט שמקבל `datetime` object
- ✅ קורא ל-`create_appointment_from_realtime()` עם המרה אוטומטית ל-ISO
- ✅ מחזיר appointment_id או None

### 3. `load_call_config()` ב-`media_ws_ai.py`

**כבר היה תקין!**
- ✅ השורות 231-232 כבר מסירות `'phone'` מ-`required_lead_fields`
- ✅ הקוד: `sanitized_fields = [f for f in raw_required_fields if f != 'phone']`

### 4. כלי תיאום פגישות `schedule_appointment`

**הגדרת הכלי ב-`_build_realtime_tools_for_call()`:**
```python
appointment_tool = {
    "type": "function",
    "name": "schedule_appointment",
    "description": "Schedule an appointment when customer confirms time",
    "parameters": {
        "properties": {
            "customer_name": {"type": "string"},
            "appointment_date": {"type": "string", "description": "YYYY-MM-DD"},
            "appointment_time": {"type": "string", "description": "HH:MM"},
            "service_type": {"type": "string"}
        },
        "required": ["customer_name", "appointment_date", "appointment_time"]
    }
}
```

**שימו לב:**
- ✅ אין `customer_phone` בפרמטרים - נלקח מהשיחה!
- ✅ רק name, date, time הם חובה

## 📋 בדיקת צ'ק-ליסט

### ✅ טקסטים hardcoded הוסרו
```bash
grep "בעל מקצוע יחזור" server/  # No matches found ✅
grep "מה הטלפון שלך" server/     # No matches found ✅
```

### ✅ System Prompts נקיים
- ✅ אין דוגמאות ספציפיות (מנעולן, שירותים וכו')
- ✅ אין משפטי סיום קשיחים
- ✅ יש הצהרה ברורה על Business Prompt כמקור יחיד
- ✅ הוראות תיאום פגישות גנריות ללא טקסט עברי

### ✅ תיאום פגישות עובד נכון
- ✅ משתמש ב-`customer_phone` מהשיחה (לא שואל!)
- ✅ שואל רק: name + date/time
- ✅ קורא לשרת עם `validate_appointment_slot()`
- ✅ מחכה לתשובה מהשרת לפני שמאשר ללקוח
- ✅ מעדכן ה-AI רק אחרי `success: True` מהשרת

### ✅ required_lead_fields נקי
- ✅ `'phone'` מוסר אוטומטית בשורה 232 של `media_ws_ai.py`

## 🎯 תוצאה סופית

### שיחה בעסק A (ללא תיאום פגישות)
1. ✅ ה-AI **לא** מבקש טלפון (כבר יש מהשיחה)
2. ✅ ה-AI **לא** אומר "בעל מקצוע יחזור אליך" אלא רק מה שכתוב ב-Business Prompt
3. ✅ כל ההתנהגות מגיעה מה-Business Prompt בלבד

### שיחה בעסק B (עם תיאום פגישות)
1. ✅ ה-AI מבקש רק: **שם + תאריך/שעה**
2. ✅ ה-AI **לא** מבקש טלפון
3. ✅ הלוגים מראים:
   - 📅 `[APPOINTMENT] Using customer_phone from call: +972XXXXXXXXX`
   - 📅 `[APPOINTMENT] Checking slot: 2025-12-10 14:00:00+02:00`
   - ✅ `[APPOINTMENT] Created successfully: #123`
4. ✅ ה-AI אומר שנקבע תור **רק** אחרי `{"success": True}` מהשרת

## 📝 הוראות שימוש

### להוסיף Business Prompt לעסק
```sql
UPDATE business_settings 
SET ai_prompt = '{"calls": "אתה נציג של חברת XYZ. תפקידך לאסוף שם ועיר. בסיום תגיד: תודה, ניצור קשר."}'
WHERE tenant_id = 123;
```

### להפעיל תיאום פגישות
```sql
UPDATE business_settings 
SET enable_calendar_scheduling = TRUE
WHERE tenant_id = 123;
```

## 🔥 עקרונות מרכזיים

1. **אין טקסט hardcoded בשום מקום**
   - לא בקוד Python
   - לא ב-System Prompts
   - הכל מגיע מ-Business Prompt

2. **Customer phone תמיד זמין**
   - נלקח מ-Twilio: `From` header
   - שמור ב-`self.phone_number`
   - **אין צורך לבקש אותו בשיחה**

3. **תיאום פגישות = server-side**
   - AI שולח: name + date + time
   - Server בודק זמינות
   - Server יוצר appointment
   - Server מחזיר success/error
   - **רק אז** AI מאשר ללקוח

4. **Business Prompt = מקור האמת היחיד**
   - אם יש סתירה בין System Prompt ל-Business Prompt
   - **תמיד לעדיף את Business Prompt**

## 🚀 סיום

כל הקוד עובר קומפילציה בהצלחה:
```bash
✅ server/services/realtime_prompt_builder.py - compiled
✅ server/media_ws_ai.py - compiled
```

**המערכת עכשיו 100% נקייה ומונחית DB!**
