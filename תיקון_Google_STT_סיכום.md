# תיקון Google STT - סיכום בעברית

## מה תוקן?

תוקנה הבעיה:
```
GOOGLE_APPLICATION_CREDENTIALS environment variable is not set
```

## השינויים שבוצעו

### 1. הוספת משתנה סביבה

בכל השירותים הרלוונטיים הוספנו:
```yaml
GOOGLE_APPLICATION_CREDENTIALS: /root/secrets/gcp-stt-sa.json
```

### 2. הוספת Volume Mount

בכל השירותים הרלוונטיים הוספנו:
```yaml
volumes:
  - /root/secrets/gcp-stt-sa.json:/root/secrets/gcp-stt-sa.json:ro
```

ה-`:ro` פירושו read-only (קריאה בלבד) לאבטחה.

### 3. שירותים שעודכנו

**בפיתוח (docker-compose.yml):**
- `backend` (legacy)
- `worker`
- `prosaas-api`
- `prosaas-calls`

**בפרודקשן (docker-compose.prod.yml):**
- `worker`
- `prosaas-api`
- `prosaas-calls`

## הנחיות פריסה

### שלב 1: עצירת קונטיינרים

```bash
docker compose down
```

### שלב 2: הרצה מחדש עם force-recreate

**חובה לשים את הדגל `--force-recreate`!**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate
```

למה `--force-recreate` חובה?
- משתני הסביבה נקבעים רק בעת יצירת הקונטיינר
- Volume mounts מוגדרים רק בעת יצירת הקונטיינר
- ללא זה, השינויים לא ייכנסו לתוקף!

## אימות התיקון

### 1. בדיקת משתנה סביבה

```bash
# בדיקה בשירות API
docker compose exec prosaas-api env | grep GOOGLE_APPLICATION_CREDENTIALS

# בדיקה בשירות Worker
docker compose exec worker env | grep GOOGLE_APPLICATION_CREDENTIALS

# בדיקה בשירות Calls
docker compose exec prosaas-calls env | grep GOOGLE_APPLICATION_CREDENTIALS
```

צפוי לראות:
```
GOOGLE_APPLICATION_CREDENTIALS=/root/secrets/gcp-stt-sa.json
```

### 2. בדיקת קובץ

```bash
# בדיקה שהקובץ קיים
docker compose exec prosaas-api ls -l /root/secrets/gcp-stt-sa.json

# בדיקה שהקובץ נגיש לקריאה
docker compose exec prosaas-api cat /root/secrets/gcp-stt-sa.json > /dev/null && echo "✅ הקובץ נגיש"
```

### 3. בדיקת Google STT

השירות צריך להיות מסוגל כעת להשתמש ב-Google STT ללא שגיאות.

## פתרון בעיות נפוצות

### שגיאה: "No such file or directory"

**פתרון:**
```bash
# וודא שהקובץ קיים על השרת
ls -l /root/secrets/gcp-stt-sa.json

# אם הקובץ לא קיים, יש להעתיק אותו למיקום הנכון
# cp your-service-account.json /root/secrets/gcp-stt-sa.json
```

### שגיאה: "Permission denied"

**פתרון:**
```bash
# תן הרשאות קריאה לקובץ
chmod 644 /root/secrets/gcp-stt-sa.json

# וודא שהתיקייה נגישה
chmod 755 /root/secrets
```

### משתנה הסביבה לא קיים בקונטיינר

**פתרון:**
```bash
# וודא שהרצת את הפקודה עם --force-recreate
docker compose down
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate
```

## אבטחה

✅ **הקובץ במצב read-only** - הקונטיינרים יכולים רק לקרוא את הקובץ, לא לשנות אותו

✅ **הקובץ לא בגיט** - אסור להעלות את קובץ ה-Service Account ל-Git!

✅ **גיבוי** - שמור גיבוי מאובטח של קובץ ה-Service Account

## קבצים שהשתנו

1. `docker-compose.yml` - הגדרות פיתוח
2. `docker-compose.prod.yml` - הגדרות פרודקשן
3. `GOOGLE_STT_DEPLOYMENT_GUIDE.md` - מדריך פריסה מפורט באנגלית

## סיכום

התיקון מבטיח ש:
1. ✅ משתנה הסביבה `GOOGLE_APPLICATION_CREDENTIALS` מוגדר בכל השירותים הרלוונטיים
2. ✅ קובץ ה-Service Account נגיש לקונטיינרים במצב קריאה בלבד
3. ✅ Google STT יעבוד בפרודקשן ללא שגיאות
4. ✅ התיקון פועל גם בפיתוח וגם בפרודקשן

## תמיכה

במקרה של בעיות:
1. בדוק לוגים: `docker compose logs -f [שם-שירות]`
2. וודא שה-Service Account ב-Google Cloud מאושר לשימוש ב-STT API
3. בדוק שקובץ ה-JSON תקין ולא פג תוקף
