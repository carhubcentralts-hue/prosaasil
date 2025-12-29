# תיקון מלא: שם לקוח ומין - CRM Context
# Complete Fix: Customer Name and Gender - CRM Context

## הבעיה המקורית (Original Problem)
```
יש לי בעיה שהcrm context לא עובר!
```

הלוגים הראו:
```
crm_context exists: False
pending_customer_name: None
extracted name: None
```

## דרישות נוספות (New Requirements)
1. ✅ **קריאת מין מהלקוח בUI**: אם רשום מין בUI, המערכת צריכה לקרוא אותו ולדעת איך לדבר
2. ✅ **עדכון אוטומטי של מין**: אם המערכת הבינה מין מהשיחה, לעדכן אוטומטית בUI
3. ✅ **שיחות נכנסות ויוצאות**: הכל צריך לעבוד גם לשיחות נכנסות וגם ליוצאות!

## הפתרון המלא (Complete Solution)

### 1️⃣ חילוץ שם לקוח (Customer Name Extraction)
**קובץ**: `server/media_ws_ai.py`, שורות 3885-3910

```python
# אם אין שם ב-pending_customer_name, שואלים את Lead במסד
if not self.crm_context.customer_name and lead_id:
    lead = Lead.query.filter_by(id=lead_id, tenant_id=business_id_safe).first()
    if lead:
        full_name = lead.full_name or f"{lead.first_name or ''} {lead.last_name or ''}".strip()
        customer_name = extract_first_name(full_name) or full_name
        self.crm_context.customer_name = customer_name
```

### 2️⃣ חילוץ מין מוקדם (Early Gender Fetch)
**קובץ**: `server/media_ws_ai.py`, שורות 3142-3171

כשמחלצים שם לקוח בתחילת השיחה, **גם מחלצים מין**:

```python
# אחרי שמצאנו שם
if resolved_name:
    self.pending_customer_name = resolved_name
    
    # 🆕 חילוץ מין מאותו Lead
    if lead_id:
        lead = Lead.query.filter_by(id=lead_id, tenant_id=business_id_safe).first()
    elif phone_number:
        # חיפוש לפי טלפון (לשיחות נכנסות)
        lead = Lead.query.filter_by(tenant_id=business_id_safe).filter(
            Lead.phone_e164.in_(phone_variants)
        ).first()
    
    if lead and lead.gender:
        self.pending_customer_gender = lead.gender
        print(f"✅ [GENDER] Fetched from Lead: '{lead.gender}'")
```

**עובד ל:**
- ✅ שיחות נכנסות: חיפוש לפי טלפון
- ✅ שיחות יוצאות: חיפוש לפי lead_id

### 3️⃣ שימוש במין ב-NAME_ANCHOR
**קובץ**: `server/media_ws_ai.py`, שורות 3594-3603

סדר עדיפות לזיהוי מין:
1. **Priority 0** (חדש!): `pending_customer_gender` - המין שנמשך מוקדם
2. Priority 1: CallLog/Lead במסד נתונים
3. Priority 2: זיהוי מהשם (דני=זכר, רונית=נקבה)

```python
customer_gender = None

# Priority 0: משתמשים במין שכבר נמשך
if hasattr(self, 'pending_customer_gender') and self.pending_customer_gender:
    customer_gender = self.pending_customer_gender
    print(f"🧠 [GENDER] Using pending: {customer_gender}")

# Priority 1: fallback למסד נתונים
if not customer_gender:
    lead = Lead.query.get(lead_id)
    if lead and lead.gender:
        customer_gender = lead.gender
```

### 4️⃣ זיהוי מין מהשיחה + עדכון אוטומטי
**קובץ**: `server/media_ws_ai.py`, שורות 7016-7042

**כבר עובד!** הקוד הקיים:
- מזהה מין מהשיחה ("אני אישה" / "אני גבר")
- מעדכן אוטומטית את Lead במסד נתונים
- עובד גם לשיחות נכנסות וגם ליוצאות

```python
detected_gender = detect_gender_from_conversation(text)

if detected_gender:
    # עדכון Lead במסד
    lead.gender = detected_gender
    db.session.commit()
    print(f"🧠 [GENDER] Detected from conversation: {detected_gender} (saved to Lead {lead.id})")
    
    # עדכון NAME_ANCHOR עם מין חדש
    updated_anchor = build_name_anchor_message(
        customer_name, 
        use_policy, 
        detected_gender  # מין חדש!
    )
```

## זרימה מלאה (Complete Flow)

### שיחה נכנסת עם Lead קיים (Inbound Call with Existing Lead)
```
1. התחלת שיחה
   ↓
2. חילוץ שם + מין מהמסד (לפי טלפון)
   → pending_customer_name = "דני"
   → pending_customer_gender = "male"
   ↓
3. NAME_ANCHOR injection
   → משתמשים ב-pending_customer_gender
   → "שם הלקוח דני (זכר), תדבר אליו בגוף זכר"
   ↓
4. במהלך השיחה: "אני אישה"
   → detected_gender = "female"
   → עדכון Lead.gender = "female"
   → עדכון NAME_ANCHOR
   ↓
5. שיחה הבאה
   → pending_customer_gender = "female" (מהמסד!)
   → השיחה מתחילה עם מין נכון
```

### שיחה יוצאת עם lead_id (Outbound Call with lead_id)
```
1. התחלת שיחה עם lead_id=123
   ↓
2. חילוץ שם + מין מהמסד (לפי lead_id)
   → pending_customer_name = "רונית"
   → pending_customer_gender = "female"
   ↓
3. NAME_ANCHOR injection
   → משתמשים ב-pending_customer_gender
   → "שם הלקוח רונית (נקבה), תדבר אליה בגוף נקבה"
   ↓
4. אם בשיחה: "אני גבר"
   → detected_gender = "male"
   → עדכון Lead.gender = "male"
   → שיחה הבאה תהיה עם מין נכון
```

## בדיקות (Testing)

### Test Case 1: קריאת מין מהמסד - שיחה נכנסת
```python
Lead: first_name="דני", gender="male"
Phone: "+972501234567"

Result:
✅ pending_customer_gender = "male"
✅ NAME_ANCHOR uses male pronouns
```

### Test Case 2: קריאת מין מהמסד - שיחה יוצאת
```python
Lead: first_name="רונית", gender="female"
lead_id: 123

Result:
✅ pending_customer_gender = "female"
✅ NAME_ANCHOR uses female pronouns
```

### Test Case 3: עדכון מין מהשיחה
```python
Initial: Lead.gender = None
Conversation: "אני אישה"

Result:
✅ Lead.gender updated to "female"
✅ NAME_ANCHOR re-injected with female
✅ Next call uses "female" from database
```

### Test Case 4: שיחה נכנסת ללא Lead קיים
```python
Phone: "+972509999999"
Lead: Not found

Result:
✅ pending_customer_gender = None (fallback to name-based detection)
✅ If conversation reveals gender → saves to new Lead
```

## לוגים צפויים (Expected Logs)

### לוגים טובים (Success):
```
✅ [GENDER] Fetched from Lead: 'male' (lead_id=123)
🧠 [GENDER] Using pending: male
✅ [CRM_CONTEXT] Fetched customer name from Lead: 'דני' (lead_id=123)
✅ [CRM_CONTEXT] Fetched customer gender from Lead: 'male' (lead_id=123)
```

### לוגים של עדכון מהשיחה:
```
🧠 [GENDER] Detected from conversation: female (saved to Lead 123)
✅ [NAME_ANCHOR] Re-injecting with updated gender: female
```

## קבצים ששונו (Files Changed)
1. ✅ `server/media_ws_ai.py` - הוספת 3 נקודות חילוץ מין
2. ✅ `test_gender_fetch_and_persist.py` - בדיקות יחידה חדשות
3. ✅ `test_crm_context_name_fetch.py` - בדיקות שם קיימות

## סיכום (Summary)

### מה עובד עכשיו:
✅ חילוץ שם לקוח מהמסד (גם נכנס וגם יוצא)
✅ חילוץ מין מהמסד (גם נכנס וגם יוצא)
✅ שימוש במין לדיבור נכון (זכר/נקבה)
✅ זיהוי מין מהשיחה (אוטומטי)
✅ עדכון Lead במסד (לשיחות הבאות)
✅ עובד לשיחות נכנסות ויוצאות!

### Deployment
- ✅ Backward compatible
- ✅ Zero downtime
- ✅ All tests pass
- ✅ Production ready
