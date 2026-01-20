# 🚀 מדריך פריסה: תכונת מאגר (Assets Library)

## סיכום השינויים

התכונה "מאגר" כבר מיושמת במלואה בקוד:
- ✅ UI מלא (AssetsPage.tsx)
- ✅ API מלא (routes_assets.py)
- ✅ כלי AI (tools_assets.py)
- ✅ מיגרציה (Migration 81 ב-db_migrate.py)
- ✅ רישום בסיידבר (MainLayout.tsx)
- ✅ רישום ב-page_registry.py
- ✅ תמיכת WhatsApp media (tools_whatsapp.py)

## 🔴 למה הדף לא נראה בפריסה הקודמת?

**הסיבה המרכזית:** המיגרציה לא הוסיפה את 'assets' ל-enabled_pages של העסקים הקיימים.

### מה קורה בפריסה הבאה?

**Migration 81** תרוץ אוטומטית ותעשה את הפעולות הבאות:

1. **יצירת טבלאות** (אם לא קיימות):
   - `asset_items` - פריטים במאגר
   - `asset_item_media` - תמונות מקושרות לפריטים

2. **עדכון enabled_pages** (🔥 חדש!):
   ```sql
   -- הוספת 'assets' לעסקים קיימים
   UPDATE business
   SET enabled_pages = enabled_pages::jsonb || '["assets"]'::jsonb
   WHERE enabled_pages IS NOT NULL
     AND NOT (enabled_pages::jsonb ? 'assets')
   
   -- הגדרת ברירת מחדל לעסקים עם NULL/ריק
   UPDATE business
   SET enabled_pages = '["dashboard",...,"assets",...]'::jsonb
   WHERE enabled_pages IS NULL OR enabled_pages::text = '[]'
   ```

## ✅ איך לוודא שהכל עובד?

### לאחר הפריסה:

#### 1. בדיקת המיגרציה
```bash
# התחבר לשרת
ssh production-server

# בדוק שהטבלאות קיימות
psql $DATABASE_URL -c "\dt asset*"

# Expected output:
#  public | asset_items      | table | ...
#  public | asset_item_media | table | ...
```

#### 2. בדיקת enabled_pages
```bash
# בדוק שכל העסקים יש להם 'assets'
psql $DATABASE_URL -c "
SELECT id, name, 
       enabled_pages::jsonb ? 'assets' AS has_assets,
       jsonb_array_length(enabled_pages::jsonb) AS total_pages
FROM business
LIMIT 10;
"

# Expected output:
# id | name        | has_assets | total_pages
# ---|-------------|------------|-------------
# 1  | Business 1  | t          | 15
# 2  | Business 2  | t          | 15
```

#### 3. בדיקה בממשק
1. התחבר כמשתמש (agent/admin/owner)
2. פתח את הסיידבר
3. חפש את הדף **"מאגר"** עם אייקון 📦
4. לחץ עליו - צריך להיפתח דף ריק עם כפתור "פריט חדש"

#### 4. בדיקת AI Tools
```bash
# בדוק בלוגים שה-AI tools נטענים
tail -f /var/log/app.log | grep "Assets Library ENABLED"

# Expected output:
# 📦 Assets Library ENABLED for business 1 - assets tools added
```

## 🐛 אם הדף עדיין לא נראה

### אפשרות 1: המיגרציה לא רצה
```bash
# הפעל מיגרציות ידנית
cd /app
python3 -c "
from server.db_migrate import apply_migrations
from server.app_factory import create_app
app = create_app()
with app.app_context():
    apply_migrations()
"
```

### אפשרות 2: enabled_pages לא עודכן
```sql
-- הפעל ידנית
UPDATE business
SET enabled_pages = enabled_pages::jsonb || '["assets"]'::jsonb
WHERE NOT (enabled_pages::jsonb ? 'assets');
```

### אפשרות 3: הפרונטאנד לא נבנה מחדש
```bash
# בנה את הפרונטאנד
cd /app/client
npm run build

# הפעל מחדש את השרת
systemctl restart prosaasil
```

## 📊 לוג המיגרציה הצפוי

```
🔧 MIGRATION CHECKPOINT: Migration 81: Assets Library - Creating asset_items and asset_item_media tables
🔧 MIGRATION CHECKPOINT:   → Creating asset_items table...
🔧 MIGRATION CHECKPOINT:   ✅ asset_items table created
🔧 MIGRATION CHECKPOINT:   → Creating asset_item_media table...
🔧 MIGRATION CHECKPOINT:   ✅ asset_item_media table created
🔧 MIGRATION CHECKPOINT:   → Enabling 'assets' page for all businesses...
🔧 MIGRATION CHECKPOINT:   ✅ Enabled 'assets' page for X businesses
🔧 MIGRATION CHECKPOINT: ✅ Migration 81 completed - Assets Library tables created and page enabled
```

## 🎯 מה המשתמש יראה?

### בסיידבר:
```
סקירה כללית
לידים
WhatsApp
...
📦 מאגר          ← חדש!
...
הגדרות מערכת
```

### בדף המאגר:
- רשת של כרטיסי פריטים (ריק בהתחלה)
- כפתור "פריט חדש" למעלה
- חיפוש וסינון
- מודאל ליצירת פריטים חדשים

### האינטראקציה עם AI:
```
לקוח: "יש לכם דירות בתל אביב?"
AI: [מחפש במאגר עם assets_search]
AI: "כן! יש לנו מספר דירות. אשלח לך..."
AI: [שולח תמונות עם whatsapp_send + attachment_ids]
```

## 📞 תמיכה

אם משהו לא עובד:
1. בדוק את הלוגים: `/var/log/app.log`
2. בדוק שהמיגרציה רצה: `grep "Migration 81" /var/log/app.log`
3. בדוק שהפרונטאנד נבנה: `ls -la /app/client/dist/assets/AssetsPage*`

---

**תאריך עדכון:** 2026-01-20  
**גרסה:** 1.0  
**מיגרציה:** 81  
**סטטוס:** ✅ מוכן לפריסה
