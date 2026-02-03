# 🎯 פיצ'ר: פרומפט מותאם אישית לשינוי סטטוסים

## סקירה כללית
פיצ'ר חדש המאפשר לכל עסק להגדיר בצורה מותאמת אישית כיצד ה-AI משנה סטטוסים של לידים במהלך שיחות ו-WhatsApp.

## 🔧 רכיבים שנוספו

### 1. מסד נתונים (Migration 129)
**קובץ:** `server/db_migrate.py`

הוספת עמודות חדשות ל-`prompt_revisions`:
- `status_change_prompt` (TEXT) - פרומפט מותאם אישית לשינוי סטטוסים
- `whatsapp_system_prompt` (TEXT) - פרומפט נפרד ל-WhatsApp (להרחבה עתידית)

**מודל:** `server/models_sql.py` - עדכון `PromptRevisions` class

### 2. Backend API
**קובץ:** `server/routes_smart_prompt_generator.py`

**Endpoints חדשים:**

#### GET `/api/ai/status_change_prompt/get`
- מחזיר את הפרומפט הנוכחי לשינוי סטטוסים
- אם אין פרומפט מותאם - מחזיר תבנית ברירת מחדל
- **אבטחה:** רק owners/admins יכולים לגשת

**Response:**
```json
{
  "success": true,
  "prompt": "...",
  "version": 5,
  "has_custom_prompt": true
}
```

#### POST `/api/ai/status_change_prompt/save`
- שומר פרומפט מותאם אישית
- יוצר גרסה חדשה ב-`prompt_revisions`
- מבטל cache של ה-AI
- **אבטחה:** רק owners/admins יכולים לשמור

**Request:**
```json
{
  "prompt_text": "הנחיות מותאמות אישית..."
}
```

### 3. Agent Factory Integration
**קובץ:** `server/agent_tools/agent_factory.py`

**שינויים:**
1. טוען את הפרומפט המותאם אישית מ-`PromptRevisions`
2. אם אין פרומפט מותאם - משתמש בברירת מחדל
3. מוסיף את ההנחיות ל-system instructions של ה-Agent
4. פועל עבור כל הערוצים: שיחות טלפון, WhatsApp, ועוד

**קוד:**
```python
latest_revision = PromptRevisions.query.filter_by(
    tenant_id=business_id
).order_by(PromptRevisions.version.desc()).first()

if latest_revision and latest_revision.status_change_prompt:
    # Use custom prompt
    status_update_instructions = latest_revision.status_change_prompt
else:
    # Use default prompt
    status_update_instructions = "..."
```

### 4. UI Component
**קובץ:** `client/src/components/settings/StatusChangePromptEditor.tsx`

**פיצ'רים:**
- ✅ עורך טקסט מלא עם סינטקס highlighting
- ✅ טעינה אוטומטית של הפרומפט הנוכחי
- ✅ שמירה עם validation
- ✅ אינדיקציה אם משתמשים בפרומפט מותאם או ברירת מחדל
- ✅ מונה תווים (max 5000)
- ✅ הצגת גרסה נוכחית
- ✅ טיפים וכלי עזר להבנת השימוש
- ✅ הודעות שגיאה והצלחה

### 5. Integration בסטודיו פרומפטים
**קובץ:** `client/src/pages/Admin/PromptStudioPage.tsx`

**שינויים:**
1. הוספת טאב חדש: "פרומפט סטטוסים" עם אייקון 🎯
2. ניווט URL-based: `?tab=statuses`
3. אינטגרציה עם `StatusChangePromptEditor` component

## 🔒 אבטחה

### הרשאות
- רק `system_admin`, `owner`, `admin` יכולים לגשת ולערוך
- `@require_api_auth` decorator על כל ה-endpoints
- CSRF protection enabled

### Data Isolation
- כל עסק רואה **רק** את הפרומפט שלו
- שאילתות משתמשות ב-`tenant_id` לסינון
- אין אפשרות לגשת לפרומפט של עסק אחר

### Validation
- בדיקת אורך מקסימלי: 5000 תווים
- טקסט לא יכול להיות ריק
- Sanitization של input

## 📝 תבנית ברירת מחדל

הפרומפט המוגדר מראש כולל:
- עקרונות כלליים לשינוי סטטוסים
- דוגמאות ספציפיות לכל סטטוס
- מגבלות ברורות - מתי **לא** לשנות סטטוס
- רמות ביטחון (confidence levels)
- העיקרון: "תהיה שמרן! עדכן רק כשבטוח"

## 🚀 תהליך עבודה

### למפתח:
1. יצירת migration: ✅
2. עדכון models: ✅
3. יצירת API endpoints: ✅
4. שילוב ב-Agent Factory: ✅
5. בניית UI component: ✅
6. אינטגרציה בדף ראשי: ✅

### למשתמש:
1. כניסה לסטודיו פרומפטים → טאב "פרומפט סטטוסים"
2. עריכת הפרומפט לפי צרכי העסק
3. שמירה (יוצרת גרסה חדשה)
4. ה-AI מיידית משתמש בפרומפט החדש

## 🔄 Cache Invalidation

כשפרומפט נשמר:
```python
from server.services.ai_service import invalidate_business_cache
invalidate_business_cache(business_id)
```

זה מבטיח שה-AI יטען את הפרומפט המעודכן בשיחה הבאה.

## 📊 דוגמה לשימוש

### פרומפט מותאם אישית לחברת הובלות:

```
🎯 הנחיות לשינוי סטטוס - חברת הובלות XYZ

**עקרונות:**
- שנה סטטוס רק אחרי שקיבלת מספיק מידע
- תמיד רשום סיבה ברורה

**סטטוסים שלנו:**

📌 מעוניין (interested):
- לקוח שואל על מחיר הובלה
- לקוח מעוניין בתאריכים
דוגמה: "לקוח שאל על עלות הובלת 3 חדרים"

📌 נשלחה הצעה (proposal_sent):
- שלחנו הצעת מחיר למייל
דוגמה: "נשלחה הצעת מחיר ₪2,500 למייל"

📌 נסגרה הובלה (moving_booked):
- לקוח אישר תאריך והובלה
- קיבלנו מקדמה
דוגמה: "לקוח אישר הובלה ל-15.3, שילם מקדמה"
```

## ✅ יתרונות

1. **התאמה אישית מלאה** - כל עסק יכול להגדיר את הסטטוסים והחוקים שלו
2. **גמישות** - ניתן לעדכן בכל עת ללא צורך בקוד
3. **שקיפות** - ניהול גרסאות מלא (`prompt_revisions`)
4. **אבטחה** - הפרדה מלאה בין עסקים
5. **UX פשוט** - עורך אינטואיטיבי עם טיפים והדרכה

## 🔮 הרחבות עתידיות

- [ ] היסטוריית גרסאות (rollback לגרסה קודמת)
- [ ] A/B testing של פרומפטים
- [ ] תבניות מוכנות לפי תעשייה
- [ ] AI-powered suggestions לשיפור הפרומפט
- [ ] Analytics - איזה פרומפט עובד הכי טוב

## 📚 קבצים שנוצרו/עודכנו

1. ✅ `server/models_sql.py` - הוספת שדות ל-PromptRevisions
2. ✅ `server/db_migrate.py` - Migration 129
3. ✅ `server/routes_smart_prompt_generator.py` - API endpoints
4. ✅ `server/agent_tools/agent_factory.py` - שילוב הפרומפט
5. ✅ `client/src/components/settings/StatusChangePromptEditor.tsx` - UI component
6. ✅ `client/src/pages/Admin/PromptStudioPage.tsx` - אינטגרציה

## 🧪 בדיקות

### Manual Testing:
1. לכנוס לסטודיו פרומפטים → פרומפט סטטוסים
2. לערוך ולשמור פרומפט מותאם
3. לשלוח הודעת WhatsApp או לבצע שיחה
4. לבדוק שה-AI משנה סטטוסים לפי הפרומפט המותאם

### Database:
```sql
-- בדוק שהמיגרציה רצה
SELECT * FROM prompt_revisions 
WHERE status_change_prompt IS NOT NULL;

-- בדוק גרסאות
SELECT tenant_id, version, changed_by, changed_at 
FROM prompt_revisions 
ORDER BY changed_at DESC;
```

## 🎉 סיכום

הפיצ'ר מוכן לשימוש מלא! כל עסק יכול עכשיו:
- להגדיר בדיוק איך ה-AI משנה סטטוסים
- לראות את ההיסטוריה של השינויים
- לעדכן בכל עת ללא צורך בתמיכה טכנית

**הכל מאובטח, מהיר, וידידותי למשתמש!** 🚀
