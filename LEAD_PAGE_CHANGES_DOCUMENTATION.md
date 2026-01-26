# תיעוד שינויים בדף ליד / Lead Page Changes Documentation

## סיכום השינויים / Summary of Changes

### 1. מיזוג טאבים של WhatsApp / WhatsApp Tabs Merge ✅

**מה השתנה / What Changed:**
- איחוד שני הטאבים "וואטסאפ" (conversation) ו-"שליחה מתבנית" (wa_template) לטאב אחד בשם "וואטסאפ"
- המרקע הטכני: בקובץ `client/src/pages/Leads/LeadDetailPage.tsx`, קוד הטאבים עודכן כך שבמקום שני טאבים נפרדים יש טאב משולב אחד

**המבנה החדש / New Structure:**
```
טאב וואטסאפ (whatsapp)
├─ שליחת הודעה מתבנית (למעלה)
│  ├─ בחירת תבנית
│  ├─ עריכת הודעה
│  └─ שליחת הודעה
└─ סיכום שיחת וואטסאפ (למטה)
   ├─ סיכום אחרון
   └─ כפתור לפתיחת השיחה המלאה
```

**איך זה עובד / How It Works:**
1. הטאב החדש `MergedWhatsAppTab` משלב את שני הרכיבים הקודמים
2. הממשק לשליחת הודעה מתבנית נמצא בחלק העליון
3. סיכום השיחה האחרון נמצא מתחת
4. לחיצה על "פתח שיחה מלאה" פותחת את חלון הצ'אט המלא

**קבצים שונו / Files Changed:**
- `client/src/pages/Leads/LeadDetailPage.tsx`: קוד הטאבים והרכיב המשולב

---

### 2. תיקון תצוגת תיוגים בעברית / Hebrew Labels Fix ✅

**הבעיה / The Problem:**
- בפעילות אחרונה, שינויי סטטוס הוצגו עם השמות הקנוניים באנגלית (למשל "new", "contacted")
- מקור הליד הוצג באנגלית (למשל "form", "call")

**הפתרון / The Solution:**
1. **שינויי סטטוס**: השימוש בפונקציה `getStatusLabel()` להמרת שמות קנוניים לתיוגים בעברית
2. **מקור ליד**: הוספת מיפוי לתרגום מקורות:
   - `form` → "טופס באתר"
   - `call` → "שיחה נכנסת"
   - `whatsapp` → "וואטסאפ"
   - `manual` → "הוספה ידנית"
   - `imported_outbound` → "יבוא קובץ"

**קבצים שונו / Files Changed:**
- `client/src/pages/Leads/LeadDetailPage.tsx`: פונקציה `getActivityDescription()` עודכנה

**דוגמה / Example:**
- **לפני**: סטטוס שונה מ"new" ל"contacted"
- **אחרי**: סטטוס שונה מ"חדש" ל"יצרנו קשר"

---

### 3. טאבים גמישים לדף ליד / Flexible Lead Tabs System 🚧

**תכנון ויישום חלקי / Partial Implementation:**

#### בסיס נתונים / Database Layer ✅
- **מיגרציה 112**: הוסף עמודה `lead_tabs_config` לטבלת `business`
- סוג הנתונים: JSON (NULL = ברירת מחדל)
- מבנה: `{"primary": ["tab1", "tab2", "tab3"], "secondary": ["tab4", "tab5", "tab6"]}`

#### API Endpoints ✅
1. **GET /api/business/current**: מחזיר את `lead_tabs_config` בתגובה
2. **PUT /api/business/current/settings**: מאפשר עדכון `lead_tabs_config`
   - תיקוף: מקסימום 3 טאבים ראשיים, 6 סה"כ
   - תמיכה ב-NULL (ברירת מחדל) או אובייקט JSON מותאם

#### קוד שונה / Modified Code ✅
- `server/models_sql.py`: הוספת שדה `lead_tabs_config` למודל Business
- `server/routes_business_management.py`: הוספת תמיכה ב-API
- `server/db_migrate.py`: מיגרציה 112

#### טאבים זמינים / Available Tabs:
```javascript
// Primary tabs (max 3)
- activity: פעילות (Timeline)
- reminders: משימות
- documents: מסמכים (חוזים + הערות עם קבצים)

// Secondary tabs (shown in "More" menu)
- overview: סקירה
- whatsapp: וואטסאפ (משולב)
- calls: שיחות טלפון
- email: מייל
- contracts: חוזים
- appointments: פגישות
- ai_notes: שירות לקוחות AI
- notes: הערות חופשיות
```

#### השימוש בעתיד / Future Usage:

**לעדכן טאבים לעסק מסוים / To Update Tabs for a Business:**
```sql
UPDATE business 
SET lead_tabs_config = '{
  "primary": ["activity", "reminders", "whatsapp"],
  "secondary": ["overview", "calls", "email"]
}'
WHERE id = <business_id>;
```

**להחזיר לברירת מחדל / Reset to Default:**
```sql
UPDATE business 
SET lead_tabs_config = NULL
WHERE id = <business_id>;
```

**הערות חשובות / Important Notes:**
- מקסימום 3 טאבים ראשיים (מוצגים ישירות)
- מקסימום 6 טאבים סה"כ (3 ראשיים + 3 בתפריט "עוד")
- אם `lead_tabs_config` הוא NULL, המערכת משתמשת בברירות המחדל
- הקוד בצד לקוח עדיין משתמש בטאבים הקבועים - נדרש פיתוח נוסף לטעינה דינמית

---

## הרצת המיגרציות / Running Migrations

### בסביבת פיתוח / Development:
```bash
# אם יש לך Python ו-Flask מותקנים
cd /home/runner/work/prosaasil/prosaasil
python migration_add_lead_tabs_config.py
```

### בסביבת Docker / Docker Environment:
```bash
# הרץ את כל המיגרציות
./run_migrations.sh

# או דרך Docker
docker exec <container_name> /app/run_migrations.sh
```

---

## בדיקות ואימות / Testing and Validation

### בדיקות ידניות / Manual Testing:

1. **בדיקת מיזוג טאבי WhatsApp:**
   - [ ] פתח דף ליד
   - [ ] לחץ על "עוד" ובחר "וואטסאפ"
   - [ ] ודא שיש שני חלקים: שליחת הודעה למעלה וסיכום למטה
   - [ ] שלח הודעה ווודא שהיא נשלחת
   - [ ] לחץ על "פתח שיחה מלאה" ווודא שהצ'אט נפתח

2. **בדיקת תיוגים בעברית:**
   - [ ] פתח דף ליד
   - [ ] עבור לטאב "פעילות"
   - [ ] ודא ששינויי סטטוס מוצגים בעברית
   - [ ] ודא שמקור הליד מוצג בעברית
   - [ ] צור ליד חדש ווודא שהוא מוצג בעברית

3. **בדיקת טאבים גמישים (Backend):**
   - [ ] שלח GET ל-`/api/business/current` ווודא ש-`lead_tabs_config` מוחזר
   - [ ] שלח PUT ל-`/api/business/current/settings` עם `lead_tabs_config` ווודא שהוא נשמר
   - [ ] בדוק במסד הנתונים ש-`lead_tabs_config` עודכן

---

## עבודה עתידית / Future Work

### יישום מלא של טאבים גמישים / Full Flexible Tabs Implementation:

1. **קוד לקוח / Client-Side:**
   - [ ] טעינת `lead_tabs_config` מה-API
   - [ ] רינדור דינמי של טאבים בהתאם להגדרות
   - [ ] fallback לברירת מחדל אם אין הגדרות

2. **ממשק משתמש / UI:**
   - [ ] דף הגדרות לבחירת טאבים
   - [ ] גרירה ושחרור (drag & drop) לסידור טאבים
   - [ ] תצוגה מקדימה של הטאבים

3. **תיעוד משתמש / User Documentation:**
   - [ ] מדריך למנהלי עסק כיצד להתאים טאבים
   - [ ] הסבר על כל טאב וייעודו
   - [ ] דוגמאות לתצורות נפוצות

---

## סיכום טכני / Technical Summary

### שינויים בקוד / Code Changes:
1. **Frontend (TypeScript/React):**
   - `client/src/pages/Leads/LeadDetailPage.tsx`:
     - הוספת רכיב `MergedWhatsAppTab`
     - עדכון `getActivityDescription()` לתמיכה בעברית
     - עדכון טאבים משניים להסרת `conversation` ו-`wa_template` והוספת `whatsapp`

2. **Backend (Python/Flask):**
   - `server/models_sql.py`: הוספת `lead_tabs_config` למודל Business
   - `server/routes_business_management.py`: תמיכה ב-API לטאבים גמישים
   - `server/db_migrate.py`: מיגרציה 112

3. **Database:**
   - מיגרציה 112: עמודה חדשה `lead_tabs_config JSON` בטבלת `business`

### תלויות / Dependencies:
- אין תלויות חדשות
- שימוש בספריות קיימות (React, Flask, SQLAlchemy)

### בטיחות נתונים / Data Safety:
- כל המיגרציות הן additive בלבד (לא מוחקות נתונים)
- תמיכה ב-NULL ב-`lead_tabs_config` (ברירת מחדל)
- תיקוף בצד השרת למניעת הגדרות לא חוקיות

---

## תמיכה ופתרון בעיות / Support & Troubleshooting

### בעיות נפוצות / Common Issues:

1. **הטאב המשולב של WhatsApp לא מופיע:**
   - ודא שהמיגרציה רצה בהצלחה
   - בדוק את קונסולת הדפדפן לשגיאות
   - נקה cache והתחבר מחדש

2. **תיוגים עדיין באנגלית:**
   - ודא שסטטוסים מוגדרים במסד הנתונים עם תיוגים בעברית
   - בדוק שהשרת מחזיר את הסטטוסים הנכונים

3. **המיגרציה נכשלת:**
   - בדוק שיש חיבור למסד הנתונים
   - ודא שאין שגיאות ב-logs
   - הרץ את המיגרציה שוב (היא idempotent)

---

## קרדיטים / Credits

**מפתח / Developer:** GitHub Copilot
**תאריך / Date:** 2026-01-26
**גרסה / Version:** Build 112

---

## רישיון / License

חלק מפרויקט ProSaaS
