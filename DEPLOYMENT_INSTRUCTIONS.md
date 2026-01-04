# 🚀 הוראות פריסה - כדי לראות את השינויים

## ⚠️ חשוב מאוד!

השינויים שבוצעו הם בקוד ונמצאים ב-repository, אבל **לא יהיו נראים בדפדפן** עד שתפרוס מחדש את הפרויקט.

## 🔧 מה שונה בקוד:

### 1. ✅ Email Service - תיקון 'business is undefined'
- **קובץ**: `server/services/email_service.py`
- **תיקון**: תמיד מספק business/lead/agent עם fallback
- **תוצאה**: לא יהיו יותר שגיאות של `'business' is undefined` בשליחת מיילים

### 2. ✅ TTS Preview - תיקון Invalid modalities
- **קובץ**: `server/routes_ai_system.py`
- **תיקון**: שינוי modalities מ-`["audio"]` ל-`["audio", "text"]`
- **תיקון נוסף**: fallback אוטומטי מ-Realtime ל-speech.create
- **תוצאה**: כל הקולות יעבדו בתצוגה מקדימה

### 3. ✅ Nginx Cache - index.html לא יישמר בcache
- **קובץ**: `docker/nginx.conf`
- **תיקון**: הוספת `no-cache` ל-`index.html`
- **תוצאה**: עדכונים בפרונט יהיו נראים מיד (אחרי deploy)

## 📋 הוראות פריסה

### שלב 1: עצור את כל הקונטיינרים
```bash
docker compose down
```

### שלב 2: נקה Docker cache (חשוב!)
```bash
docker system prune -af
```

### שלב 3: בנה מחדש ללא cache
```bash
docker compose build --no-cache
```

### שלב 4: הרם את השירותים
```bash
docker compose up -d
```

### שלב 5: בדוק שהכל רץ
```bash
docker compose ps
docker compose logs -f --tail=100
```

## 🧹 ניקוי Cache בדפדפן

אחרי שהפריסה הושלמה, **חובה לנקות cache בדפדפן**:

### Chrome / Edge:
1. לחץ `Ctrl + Shift + Delete` (Windows) או `Cmd + Shift + Delete` (Mac)
2. בחר "Cached images and files"
3. לחץ "Clear data"
4. רענן את הדף `Ctrl + F5` (Windows) או `Cmd + Shift + R` (Mac)

### Firefox:
1. לחץ `Ctrl + Shift + Delete`
2. בחר "Cache"
3. לחץ "Clear Now"
4. רענן את הדף `Ctrl + F5`

### Safari:
1. לחץ `Cmd + Option + E` (Empty Caches)
2. רענן את הדף `Cmd + R`

## ✅ אימות שהשינויים עובדים

### בדיקה 1: Email Service
```bash
# שלח מייל test לעסק tenant_id=4
# ודא שאין שגיאת 'business' is undefined בלוגים
docker compose logs backend | grep -i "business.*undefined"
```

אם אין תוצאות - מעולה! התיקון עובד.

### בדיקה 2: TTS Preview
1. לך ל**הגדרות AI** → **בחירת קול**
2. נסה 3 קולות שונים:
   - `alloy` (אמור לעבוד דרך speech.create)
   - `cedar` (אמור לעבוד דרך realtime)
   - `coral` (אמור לעבוד עם fallback אם צריך)
3. בדוק את הלוגים:
```bash
docker compose logs backend | grep -i "TTS_PREVIEW"
```

אמור לראות:
```
[TTS_PREVIEW] speech.create success: ... bytes (mp3)
או
[TTS_PREVIEW] Realtime success: ... bytes (wav)
```

### בדיקה 3: דף מיילים - Footer ניתן לעריכה
**הקוד כבר קיים!** פשוט תצטרך לפרוס מחדש ולנקות cache:

1. לך ל**מיילים** → **שלח ללידים**
2. בחר ליד
3. אמור לראות שדה **"פוטר המייל (חשוב!)"** עם רקע צהוב
4. אפשר לערוך את הפוטר
5. הפוטר נשמר לכל עסק

**שורה בקוד**: `client/src/pages/emails/EmailsPage.tsx:1466`

## 🔍 פתרון בעיות

### בעיה: עדיין לא רואה שינויים אחרי deploy
**פתרון**:
1. ודא ש-Docker build התבצע בהצלחה:
   ```bash
   docker compose logs frontend | grep -i "build\|error"
   ```
2. ודא שהקונטיינר frontend רץ:
   ```bash
   docker compose ps frontend
   ```
3. בדוק את תוכן ה-container:
   ```bash
   docker exec -it prosaas-frontend ls -lah /usr/share/nginx/html/
   ```
4. נקה cache בדפדפן **בכוח** (`Ctrl + Shift + Delete`)

### בעיה: Frontend לא נבנה
```bash
# בדוק שגיאות build
docker compose logs frontend
```

אם יש שגיאות, תקן אותן ובנה מחדש:
```bash
docker compose build --no-cache frontend
```

### בעיה: Backend לא רץ
```bash
docker compose logs backend | tail -50
```

## 📝 סיכום

כל השינויים **כבר בקוד** וממתינים לפריסה:
- ✅ Email service - business fallback
- ✅ TTS preview - modalities fix + fallback
- ✅ Nginx - no-cache for index.html
- ✅ דף מיילים - footer עריך (הקוד כבר שם!)

**פשוט תפרוס מחדש ותנקה cache בדפדפן!**
