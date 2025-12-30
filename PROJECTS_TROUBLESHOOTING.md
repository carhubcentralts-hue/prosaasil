# פתרון בעיות בפרויקטים (Projects Troubleshooting)

## בעיה: "שגיאה ביצירת הפרויקט"

אם אתה מקבל שגיאה כללית בעת יצירת פרויקט, הנה מה לבדוק:

### 1. בדוק את המיגרציות (Database Migrations)

הפרויקטים דורשים טבלאות במסד הנתונים. אם הטבלאות לא קיימות, תקבל שגיאה.

**להריץ מיגרציות:**

```bash
# אפשרות 1: דרך סקריפט
./run_migrations.sh

# אפשרות 2: ישירות עם Python
python -m server.db_migrate

# אפשרות 3: בעברית
./הרצת_מיגרציות.sh
```

### 2. אימות טבלאות קיימות

המערכת צריכה את הטבלאות הבאות:
- `outbound_projects` - טבלת הפרויקטים הראשית
- `project_leads` - טבלת הקישור בין פרויקטים ללידים

לבדוק אם הטבלאות קיימות (דרך PostgreSQL):

```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('outbound_projects', 'project_leads');
```

### 3. הודעות שגיאה נפוצות

#### "טבלת הפרויקטים לא קיימת"
**פתרון:** הרץ `./run_migrations.sh`

#### "טבלת קישורי הלידים לפרויקטים לא קיימת"
**פתרון:** הרץ `./run_migrations.sh`

#### "לא נמצאו לידים או לא שייכים לחשבון"
זה אומר שהלידים שבחרת:
- לא קיימים במסד הנתונים
- שייכים ל-tenant אחר
- **פתרון:** בדוק ש-tenant_id של הלידים תואם ל-tenant_id של המשתמש המחובר

### 4. בדיקת Logs

הלוגים יכולים לעזור לזהות את הבעיה המדויקת:

```bash
# הצג לוגים של השרת
tail -f /path/to/logs/server.log

# או אם רץ ב-Docker
docker logs <container_name> -f
```

חפש שורות שמתחילות ב:
- `[Projects] Created project` - הצלחה
- `Error creating project:` - שגיאה עם פרטים מלאים
- `[Projects] Skipped lead` - לידים שדולגו

### 5. בעיות נפוצות

#### הפרויקט נוצר אך ללא לידים
- **סיבה:** הלידים לא שייכים ל-tenant הנכון
- **פתרון:** ודא שאתה מחובר עם המשתמש הנכון וש-tenant_id תואם

#### השגיאה אינה ברורה
- **סיבה:** הודעת שגיאה כללית מוסתרת
- **פתרון:** בדוק את ה-console בדפדפן (F12) או את לוגים של השרת

### 6. מידע טכני

**Migration Number:** 54 (+ 54b, 54c)

**קבצים רלוונטיים:**
- Backend: `server/routes_projects.py`
- Frontend: `client/src/pages/calls/components/CreateProjectModal.tsx`
- Migrations: `server/db_migrate.py` (lines 1704-1783)

**API Endpoint:** `POST /api/projects`

**Request Body:**
```json
{
  "name": "שם הפרויקט",
  "description": "תיאור אופציונלי",
  "lead_ids": [1, 2, 3]
}
```

## תמיכה נוספת

אם אף אחד מהפתרונות לא עזר:
1. בדוק שמשתנה הסביבה `DATABASE_URL` מוגדר נכון
2. ודא שיש לך הרשאות לטבלה `business` (ה-tenant_id צריך להתאים לרשומה ב-`business`)
3. נסה להריץ `./run_migrations.sh` שוב גם אם כבר הרצת בעבר
