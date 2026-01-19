# מדריך תיקון מערכת Attachments

## סיכום הבעיה והפתרון

### הבעיה המקורית
- חוזים (Contracts) - יצירה נכשלת ואין כפתור העלאת קובץ
- תפוצות WhatsApp (Broadcasts) - העלאת מדיה לא עובדת
- מיילים (Emails) - אין כפתור לצירוף קובץ
- השגיאה: `relation "attachments" does not exist`

### השורש האמיתי
**המערכת כולה מיושמת במלואה!** הבעיה היחידה: המיגרציות לא רצו בהפעלת הקונטיינר.

### הפתרון
הוספנו שורה אחת ל-`docker-compose.yml`:
```yaml
RUN_MIGRATIONS_ON_START: 1
```

## מה כבר קיים במערכת? ✅

### Backend - מלא ומושלם
1. **טבלת attachments** - Migration 76 (קיימת)
2. **טבלת contract_files** - Migration 77 (קיימת)
3. **AttachmentService** - תומך ב-R2 ו-local storage
4. **API Endpoints**:
   - `POST /api/attachments/upload` - העלאת קובץ
   - `GET /api/attachments` - רשימת קבצים
   - `GET /api/attachments/{id}` - פרטי קובץ
   - `POST /api/attachments/{id}/sign` - יצירת URL חתום
5. **חוזים** - משתמשים ב-attachments
6. **תפוצות** - תומכות ב-`attachment_id`
7. **מיילים** - תומכים ב-`attachment_ids`

### Frontend - מלא ומושלם
1. **ContractDetails.tsx** - כפתור "העלה קובץ" (שורה 341-348)
2. **EmailsPage.tsx** - רכיב AttachmentPicker משולב (שורה 2802)
3. **AttachmentPicker.tsx** - רכיב מלא עם:
   - בחירת קבצים קיימים
   - העלאת קבצים חדשים
   - תצוגה מקדימה
   - סינון לפי סוג קובץ
   - תמיכה ב-single/multi mode

## הוראות פריסה

### שלב 1: עדכון הקוד
```bash
git pull origin copilot/fix-attachments-issues
```

### שלב 2: הפעלה מחדש של הקונטיינרים
```bash
# עצור הכל (ללא -v כדי לשמור את הנתונים)
docker compose down

# בנה מחדש והפעל
docker compose up -d --build

# אם יש בעיות, נקה הכל (⚠️ מוחק נתונים!):
# docker compose down -v
# docker compose up -d --build
```

### שלב 3: בדיקת המיגרציות
```bash
# בדוק לוגים של backend
docker logs prosaas-backend | grep -i "migration"

# חפש:
# "Migration 76 completed - Unified attachments system ready"
# "Migration 77 completed - Contracts system with attachment integration"
```

## בדיקות פונקציונליות

### בדיקה 1: חוזים (Contracts)
1. היכנס ל-`/app/contracts`
2. לחץ "חוזה חדש"
3. מלא כותרת ויצור חוזה
4. **צפוי**: תיפתח דף פרטי חוזה עם כפתור "העלה קובץ"
5. לחץ "העלה קובץ" → בחר PDF/תמונה
6. **צפוי**: הקובץ יעלה והכפתור "שלח לחתימה" יהפוך לזמין

### בדיקה 2: מיילים (Emails)
1. היכנס ל-`/app/emails`
2. לחץ "שלח מייל חדש"
3. מלא כתובת מייל ותוכן
4. **צפוי**: יש כפתור/רכיב "צרף קובץ"
5. לחץ על הרכיב → העלה קובץ או בחר קיים
6. **צפוי**: מספר הקבצים המצורפים מוצג
7. שלח → **צפוי**: המייל נשלח עם הקבצים

### בדיקה 3: תפוצות WhatsApp (Broadcasts)
1. היכנס ל-`/app/whatsapp-broadcast`
2. צור תפוצה חדשה
3. **צפוי**: שדה `attachment_id` זמין (אם בממשק)
4. העלה מדיה דרך `/api/attachments/upload`
5. הוסף `attachment_id` לתפוצה
6. **צפוי**: המדיה נשלחת עם ההודעה

## בדיקת אחסון R2

אם הגדרת Cloudflare R2:

```bash
# בדוק שהמשתנים קיימים
docker exec prosaas-backend env | grep R2

# צפוי:
# ATTACHMENT_STORAGE_DRIVER=r2
# R2_ACCOUNT_ID=...
# R2_BUCKET_NAME=...
# R2_ACCESS_KEY_ID=...
# R2_SECRET_ACCESS_KEY=...
# R2_ENDPOINT=...
# ATTACHMENT_SECRET=... (חובה!)
```

בלוגים צפוי לראות:
```
Attachment service initialized with storage provider: R2StorageProvider
```

## טיפול בשגיאות

### שגיאה: "ATTACHMENT_SECRET not set"
```bash
# הוסף למשתנה סביבה .env
ATTACHMENT_SECRET=<random-32-chars>

# או צור אחד:
openssl rand -hex 32
```

### שגיאה: "relation attachments does not exist"
```bash
# הרץ מיגרציות ידנית
docker exec prosaas-backend python -m server.db_migrate
```

### שגיאה: "Failed to upload file"
1. בדוק שיש הרשאות כתיבה ל-`/app/storage/attachments`
2. ודא ש-ATTACHMENT_SECRET מוגדר
3. בדוק לוגים: `docker logs prosaas-backend | grep ATTACHMENT`

## מבנה הקבצים

```
server/
├── models_sql.py                  # Attachment model (line 1101+)
├── services/
│   ├── attachment_service.py     # Core service
│   └── storage/                   # Storage providers
│       ├── base.py                # Interface
│       ├── local_provider.py     # Local FS storage
│       └── r2_provider.py        # Cloudflare R2
├── routes_attachments.py         # API endpoints
├── routes_contracts.py           # Contracts integration
├── email_api.py                  # Email integration
└── routes_whatsapp.py            # Broadcasts integration

client/src/
├── pages/
│   ├── contracts/
│   │   ├── ContractDetails.tsx   # Has upload button!
│   │   └── CreateContractModal.tsx
│   └── emails/
│       └── EmailsPage.tsx        # Has AttachmentPicker!
└── shared/components/
    └── AttachmentPicker.tsx      # Reusable component
```

## סיכום

**הכל כבר בנוי ומוכן!** רק צריך להפעיל את המיגרציות.

אחרי `docker compose up` עם ה-docker-compose.yml המעודכן:
- ✅ טבלת attachments תיווצר
- ✅ חוזים יעבדו עם העלאת קבצים
- ✅ מיילים יתמכו בצירופים
- ✅ תפוצות יעבדו עם מדיה

אם משהו לא עובד - **בדוק תחילה את הלוגים של המיגרציות!**
