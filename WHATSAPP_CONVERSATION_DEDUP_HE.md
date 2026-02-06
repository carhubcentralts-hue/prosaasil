# תיקון כפילויות צ׳אטים - סיכום מלא

## הבעיה שתוקנה

המערכת יצרה מספר שיחות נפרדות לאותו אדם בגלל זיהוי שונה:
- הודעות של הבוט → שיחה A
- הודעות של הלקוח → שיחה B  
- אירועי מערכת → שיחה C

**הסיבה**: מזהים שונים עבור אותו אדם:
- `lid@8762...` (מכשירי אנדרואיד)
- `972504...` (מספר רגיל)
- `972504...@s.whatsapp.net` (JID של WhatsApp)
- `972504...@c.us` (פורמט ישן)

## הפתרון: מפתח קנוני (Canonical Key)

### מה זה?

**מפתח קנוני** = מזהה יחיד לשיחה, לא משנה איך הלקוח מזוהה

**הפורמט**:
```
אם יש ליד: lead:{business_id}:{lead_id}
אם אין ליד: phone:{business_id}:{phone_e164}
```

**דוגמאות**:
```python
# אותו ליד, מספרים שונים → אותו מפתח!
get_canonical_conversation_key(1, lead_id=123, phone_e164="+972501234567")
# → "lead:1:123"

get_canonical_conversation_key(1, lead_id=123, phone_e164="+972509999999")
# → "lead:1:123"  # אותו מפתח בדיוק!

# ללא ליד, לפי מספר
get_canonical_conversation_key(1, phone_e164="+972501234567")
# → "phone:1:+972501234567"
```

### איך זה עובד?

#### 1. יצירת מפתח קנוני

**קובץ**: `server/utils/whatsapp_utils.py`

**פונקציה**: `get_canonical_conversation_key()`

**סדר עדיפות**:
1. `lead_id` - הכי אמין, לא משתנה גם אם המספר משתנה
2. `phone_e164` - מספר טלפון מנורמל (עם `+`)

#### 2. שינויים במסד הנתונים

**טבלה**: `whatsapp_conversation`

**עמודה חדשה**: `canonical_key`

**אינדקס**: `(business_id, canonical_key)` - לחיפוש מהיר

**Unique constraint**: מונע כפילויות ברמת מסד הנתונים

#### 3. עדכון שירות הסשן

**קובץ**: `server/services/whatsapp_session_service.py`

**שינויים**:
```python
# לפני:
get_or_create_session(business_id, customer_wa_id, provider)

# אחרי (עם פרמטרים חדשים):
get_or_create_session(
    business_id, 
    customer_wa_id, 
    provider,
    lead_id=lead.id,           # חדש!
    phone_e164=phone_e164      # חדש!
)
```

**לוגיקת החיפוש**:
1. מחפש לפי `canonical_key` (מועדף)
2. Fallback: חיפוש לפי `customer_wa_id` (legacy)
3. מעדכן סשן ישן עם `canonical_key` אם נמצא

**יתרונות**:
- מונע יצירת כפילויות
- שומר על תאימות לאחור
- "מרפא את עצמו" (מעדכן סשנים ישנים)

#### 4. עדכון עיבוד webhook

**קובץ**: `server/jobs/webhook_process_job.py`

**שינויים**: כל קריאה ל-`update_session_activity()` עכשיו מעבירה:
```python
update_session_activity(
    business_id=business_id,
    customer_wa_id=phone_number,
    direction="in",
    provider="baileys",
    lead_id=lead.id if lead else None,      # חדש!
    phone_e164=phone_e164_for_lead          # חדש!
)
```

**3 מיקומים עודכנו**:
1. כשה-AI לא פעיל (הודעה נכנסת בלבד)
2. כשה-AI מעבד הודעה (נכנסת)
3. כשה-AI שולח תשובה (יוצאת)

## המיגרציה והאיחוד

### סקריפט הBackfill

**קובץ**: `server/scripts/backfill_canonical_keys_and_merge_duplicates.py`

**מה הוא עושה**:
1. **ממלא** `canonical_key` לכל השיחות הקיימות
2. **מוצא** כפילויות (שיחות עם אותו `canonical_key`)
3. **מאחד** כפילויות לשיחה ראשית (האחרונה לפי זמן)
4. **מוסיף** unique constraint למניעת כפילויות עתידיות

**איך להריץ**:
```bash
# Dry-run (ברירת מחדל) - רק מראה מה יקרה
python server/scripts/backfill_canonical_keys_and_merge_duplicates.py

# הרצה אמיתית - עושה את השינויים
python server/scripts/backfill_canonical_keys_and_merge_duplicates.py --execute

# דילוג על שלבים מסוימים
python server/scripts/backfill_canonical_keys_and_merge_duplicates.py --skip-backfill
python server/scripts/backfill_canonical_keys_and_merge_duplicates.py --skip-merge
```

### אסטרטגיית האיחוד

**שיחה ראשית**: השיחה האחרונה (לפי `last_message_at`)

**שיחות כפולות**:
- נסגרות (`is_open=False`)
- מסומנות כמסוכמות (`summary_created=True`)
- ההודעות נשארות נגישות (קשורות לפי `business_id` + `to_number`)
- אם לראשית אין `lead_id` והכפולה כן יש - מועתק

## תיקון תצוגת שמות

### Frontend

**קובץ**: `client/src/shared/utils/conversation.ts`

**פונקציה**: `getConversationDisplayName()`

**סדר עדיפות**:
1. `lead_name` - שם מהCRM
2. `push_name` - שם איש קשר מWhatsApp
3. `name` - שדה כללי
4. `peer_name`
5. `phone_e164` - מספר טלפון מפורמט
6. Fallback: `"ללא שם"`

**טיפול ב-LID**:
- מזהה וסופח `lid@` identifiers
- **לעולם לא מציג** מספרים של `@lid`
- חוזר לשם ליד או מספר מפורמט

### Backend

**קובץ**: `server/routes_crm.py`

**API Endpoint**: `/api/crm/threads`

**לוגיקה**:
```python
# ניקוי תצוגת מספר - לא להציג @lid
if display_phone and '@lid' in display_phone:
    display_phone = None  # אל תציג LID
elif display_phone:
    display_phone = display_phone.replace('@s.whatsapp.net', '')

# עדיפות שם
display_name = lead_name or push_name or customer_name or display_phone or 'לא ידוע'
```

## בדיקות

### Unit Tests

**קובץ**: `tests/test_canonical_conversation_key.py`

**כיסוי**:
- ✅ יצירת מפתח עם lead_id
- ✅ יצירת מפתח עם phone_e164 בלבד
- ✅ נרמול מספר (הוספת `+`)
- ✅ עדיפות lead_id על פני phone
- ✅ בידוד עסקים (מפתחות שונים לעסקים שונים)
- ✅ טיפול בשגיאות (דורש מזהה)
- ✅ טיפול בשגיאות (דורש business_id)

**הרצת בדיקות**: כל הבדיקות עברו ✅

## היתרונות העיקריים

### 1. מקור אמת יחיד
- שיחה **אחת** לאדם לעסק
- לא משנה איך הוא מזוהה (JID, LID, מספר)
- עקבי בכל סוגי ההודעות

### 2. הגנה ברמת מסד הנתונים
- Unique constraint מונע כפילויות
- גם אם יש באג בקוד, ה-DB אוכף ייחוד
- "מרפא את עצמו" (מעדכן נתונים ישנים)

### 3. תאימות לאחור
- קוד קיים עובד ללא שינויים
- מיגרציה הדרגתית (backfill אחרי deploy)
- אין שינויים שוברים ל-API

### 4. חווית משתמש
- רשימת שיחות נקייה (ללא כפילויות)
- שמות תקינים (לעולם לא `lid@...`)
- היסטוריית הודעות מלאה באותו thread

### 5. ביצועים
- חיפושים מאונדקסים (מהיר)
- פחות כפילות נתונים
- שאילתות נקיות יותר

## הפעלה בפרודקשן

### צ׳קליסט Deploy

```bash
# 1. Deploy הקוד (מוסיף עמודה, עדיין אין constraint)
git pull

# 2. הרצת מיגרציה (מוסיף עמודה ואינדקס)
# קורה אוטומטית בהפעלה

# 3. הרצת backfill (dry-run קודם)
python server/scripts/backfill_canonical_keys_and_merge_duplicates.py

# 4. בדיקת תוצאות, ואז הרצה אמיתית
python server/scripts/backfill_canonical_keys_and_merge_duplicates.py --execute

# 5. אימות שאין כפילויות
# בדיקה בלוגים
```

### ניטור

**לוגים לעקוב אחריהם**:
```
[CANONICAL_KEY] Generated: lead:1:123
[WA-SESSION] Found session by canonical_key: session_id=456
[WA-SESSION] ✨ Created NEW session canonical_key=lead:1:123
```

**שאילתות לניטור**:
```sql
-- מציאת כפילויות שנותרו
SELECT canonical_key, COUNT(*) as count
FROM whatsapp_conversation
WHERE canonical_key IS NOT NULL
GROUP BY canonical_key
HAVING COUNT(*) > 1;

-- כיסוי backfill
SELECT 
  COUNT(*) as total,
  COUNT(canonical_key) as with_key,
  COUNT(*) - COUNT(canonical_key) as missing_key
FROM whatsapp_conversation;
```

## פתרון בעיות

### בעיה: עדיין יש שיחות כפולות ישנות

**פתרון**: הרץ את סקריפט הbackfill
```bash
python server/scripts/backfill_canonical_keys_and_merge_duplicates.py --execute
```

### בעיה: נוצרות כפילויות חדשות

**בדיקות**:
1. האם ה-unique constraint פעיל?
2. האם קריאות הסשן מעבירות `lead_id` ו-`phone_e164`?

### בעיה: שיחה לא נמצאת עבור ליד

**סיבות אפשריות**:
1. `canonical_key` לא מוגדר → הרץ backfill
2. לליד אין מספר → בדוק `lead.phone_e164`
3. אי התאמה בפורמט מספר → בדוק נרמול

## קבצים שהשתנו

**מימוש עיקרי**:
- ✅ `server/utils/whatsapp_utils.py` - פונקציית מפתח קנוני
- ✅ `server/models_sql.py` - מודל WhatsAppConversation
- ✅ `server/services/whatsapp_session_service.py` - ניהול סשן
- ✅ `server/jobs/webhook_process_job.py` - עיבוד webhook

**מסד נתונים**:
- ✅ `server/db_migrate.py` - מיגרציה 138

**סקריפטים**:
- ✅ `server/scripts/backfill_canonical_keys_and_merge_duplicates.py` - מיגרציית נתונים

**Frontend**:
- ✅ `client/src/shared/utils/conversation.ts` - לוגיקת תצוגת שמות
- ✅ `server/routes_crm.py` - API endpoint

**בדיקות**:
- ✅ `tests/test_canonical_conversation_key.py` - בדיקות יחידה

**תיעוד**:
- ✅ `CONVERSATION_DEDUPLICATION.md` - תיעוד טכני באנגלית
- ✅ `WHATSAPP_LID_FIX_HE.md` - סיכום בעברית (קובץ זה)

## סיכום אבטחה

✅ **אין פגיעויות אבטחה** - ניתוח CodeQL עבר בהצלחה

**שיקולי אבטחה**:
- ✅ אימות קלט על כל הפרמטרים
- ✅ הגנה מפני SQL injection (שימוש ב-ORM)
- ✅ אין חשיפת מידע אישי בלוגים
- ✅ Unique constraint מונע race conditions

## השפעה על ביצועים

**חיובי**:
- ✅ פחות נתונים כפולים
- ✅ חיפושים מאונדקסים מהירים
- ✅ פחות שיחות לשאילתה
- ✅ מסד נתונים נקי יותר

**ניטרלי**:
- תקורת אינדקס מינימלית
- Backfill הוא פעולה חד-פעמית
- דפוסי שאילתה לא השתנו

**אין רגרסיות**:
- תאים לאחור
- Fallback לחיפוש legacy
- אין שינויים שוברים

## סטטוס: ✅ מוכן לפרודקשן

כל הצ׳קליסט הושלם. הפתרון מאובטח, נבדק ומתועד.

---

**Build**: 138  
**תאריך**: 2024-02-06  
**סטטוס**: ✅ הושלם
