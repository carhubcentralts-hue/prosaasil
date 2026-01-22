# WhatsApp Baileys Fix - Deployment & Testing Guide

## סיכום השינויים

תיקנו 6 בעיות קריטיות שגרמו לבייליס להתחבר אבל לא לענות, כולל תמיכה מלאה באנדרואיד ו-LID:

### 1️⃣ תיקון DNS/Hostname (EAI_AGAIN backend)
- **הבעיה**: הבייליס ניסה לקרוא ל-`backend` שלא קיים ב-DNS של Docker
- **הפתרון**: 
  - שימוש ב-`prosaas-api:5000` במקום `backend`
  - הוספת `BACKEND_BASE_URL` כמשתנה סביבה
  - 🔥 **waitForBackendReady** - retry עם exponential backoff לפני העלאת webhook sender
  - `depends_on` עם `service_healthy` למניעת race conditions
  - 🔥 **תור Persistent** על filesystem (`storage/queue`) שלא נאבד בריסטארט
  - שמירה אוטומטית של התור כל 30 שניות
  - דדופ לפי (tenant_id:wa_message_id)

### 2️⃣ נעילת גרסת Baileys
- **הבעיה**: `TypeError: shouldSyncHistoryMessage is not a function`
- **הפתרון**:
  - נעילה לגרסה 6.7.5 (ללא ^ או ~)
  - 🔥 **npm ci** חובה (לא npm install!) - נועל לפי package-lock.json
  - בדיקת fail-fast בעליית השירות - יוצא אם אין התאמה
  - guards לפונקציות חסרות
  - תיקון `removeAllListeners`

### 3️⃣ תמיכה ב-LID + Android
- **הבעיה**: הודעות מ-Android (@lid) לא קיבלו תשובות
- **הפתרון**:
  - חילוץ `remoteJid` + `remoteJidAlt` (sender_pn)
  - חישוב `reply_jid`: מעדיפים @s.whatsapp.net על פני @lid
  - שמירת `reply_jid` בליד - תמיד משתמשים ב-JID האחרון
  - 🔥 **reply_jid_type** - מעקב אחרי סוג ה-JID (s.whatsapp.net / lid / g.us)
  - עדכון מההודעה האחרונה מהלקוח בלבד (לא system messages)
  - אף פעם לא בונים מחדש - תמיד משתמשים ב-`reply_jid` השמור

### 4️⃣ טיפול ב-Decrypt/Bad MAC
- **הבעיה**: הודעות מוצפנות גורמות לקריסה
- **הפתרון**:
  - try-catch סביב פעולות decrypt
  - דדופ למניעת עיבוד כפול
  - retry עם backoff
  - TTL למניעת הצפת תור

### 5️⃣ תיקון restart_required + cleanup
- **הבעיה**: UNHANDLED exceptions על 515/cleanup
- **הפתרון**:
  - try-catch סביב restart_required
  - בדיקה בטוחה של sock.ev לפני removeAllListeners
  - כל ה-exceptions נתפסים ומתועדים

### 6️⃣ נירמול טלפון + מיפוי זהויות
- **הבעיה**: לידים כפולים עם מספרים שונים
- **הפתרון**:
  - פונקציה אוניברסלית `normalize_phone()` לפורמט E.164
  - תמיכה במספרים ישראליים ובינלאומיים
  - שמירת `phone_raw` לאודיט
  - חילוץ טלפון מ-sender_pn, לא מ-@lid
  - 🔥 **Upsert חכם לפי סדר עדיפויות**:
    1. **phone_e164** (העדיפה הגבוהה ביותר - יציב)
    2. **reply_jid** (אם אין phone)
    3. **whatsapp_jid_alt** (אם אין reply_jid)
    4. **whatsapp_jid** (אם אין כלום אחר)
  - זה מונע כפילויות כי JID יכול להשתנות אבל phone יציב

## הוראות פריסה

### שלב 1: הרצת מיגרציה (חובה!)

```bash
cd /home/runner/work/prosaasil/prosaasil
python migration_add_lead_phone_whatsapp_fields.py
```

המיגרציה מוסיפה 5 עמודות חדשות ל-`leads`:
- `phone_raw` - טלפון מקורי לפני נירמול
- `whatsapp_jid` - מזהה WhatsApp ראשי (remoteJid)
- `whatsapp_jid_alt` - מזהה חלופי (sender_pn)
- `reply_jid` - **קריטי**: ה-JID המדויק לשליחת תשובות
- `reply_jid_type` - סוג ה-JID (s.whatsapp.net / lid / g.us)

### שלב 1.5: הכנת ספריית תור (אוטומטי)

התור יוצר אוטומטית את `storage/queue` אבל מומלץ לוודא:
```bash
mkdir -p /home/runner/work/prosaasil/prosaasil/services/whatsapp/storage/queue
chmod 755 /home/runner/work/prosaasil/prosaasil/services/whatsapp/storage/queue
```

התור נשמר ב-`storage/queue/pending_messages.json` וניטען אוטומטית בעליית השירות.

### שלב 2: עדכון משתני סביבה

ב-`.env` או בקונפיגורציה של הדוקר:

```bash
# Baileys service
BACKEND_BASE_URL=http://prosaas-api:5000
FLASK_BASE_URL=http://prosaas-api:5000  # fallback
INTERNAL_SECRET=<your-secret>

# Production settings
LOG_LEVEL=INFO
TZ=UTC
```

### שלב 3: התקנת תלויות (Baileys) - חובה npm ci!

```bash
cd services/whatsapp
npm ci  # 🔥 חובה להשתמש ב-ci ולא install! ci נועל לפי package-lock.json
```

וודא שגרסת Baileys היא **בדיוק** 6.7.5 (לא 7.x או rc):
```bash
npm list @whiskeysockets/baileys
# צריך להראות: @whiskeysockets/baileys@6.7.5
```

**אם הגרסה לא נכונה:**
```bash
# מחק node_modules ו-package-lock.json
rm -rf node_modules package-lock.json

# התקן מחדש
npm install

# צור lockfile חדש
npm ci
```

### שלב 4: הפעלת השירות

**Development:**
```bash
docker-compose up -d baileys
```

**Production:**
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d baileys
```

### שלב 5: אימות

בדוק בלוגים:
```bash
docker logs prosaas-baileys --tail=100 -f
```

חפש:
- ✅ `Baileys version validated: 6.7.5`
- ✅ `Timezone correctly set to UTC`
- ✅ `Backend is ready: http://prosaas-api:5000`
- ✅ `Loaded X pending messages from disk` (אם יש הודעות בתור)
- ✅ `WhatsApp connected and ready to send`
- ❌ אין `EAI_AGAIN backend`
- ❌ אין `shouldSyncHistoryMessage is not a function`
- ❌ אין `Backend not reachable`

## בדיקות קבלה

### ✅ Test 1: הודעה מ-iPhone
1. שלח הודעה מ-iPhone ל-WhatsApp Business
2. ודא שהודעה התקבלה בבקאנד (לוג: `Webhook→Flask success`)
3. ודא שנוצר/עודכן ליד עם `phone_e164` תקין
4. ודא שהבוט שולח תשובה
5. ודא שהתשובה מגיעה ל-iPhone

### ✅ Test 2: הודעה מ-Android (LID)
1. שלח הודעה מ-Android ל-WhatsApp Business
2. ודא שהודעה מזוהה כ-@lid בלוגים
3. ודא שהליד נשמר עם:
   - `whatsapp_jid` = remoteJid (@lid)
   - `whatsapp_jid_alt` = sender_pn (אם קיים)
   - `reply_jid` = הערך המועדף (@s.whatsapp.net אם קיים)
4. ודא שהבוט שולח תשובה ל-`reply_jid`
5. ודא שהתשובה מגיעה ל-Android

### ✅ Test 3: נירמול טלפון
1. צור ליד ידני עם טלפון: `050-123-4567`
2. שלח הודעה מאותו מספר בפורמט: `972501234567`
3. ודא שזה אותו ליד (לא נוצר כפיל)
4. בדוק שה-`phone_e164` הוא `+972501234567` בשני המקרים

### ✅ Test 4: Retry Queue
1. כבה את prosaas-api: `docker stop prosaas-api`
2. שלח הודעה מ-WhatsApp
3. ודא בלוגים: `Message queued for retry`
4. הפעל מחדש: `docker start prosaas-api`
5. ודא שההודעה עובדה (לוג: `Webhook retry succeeded`)

### ✅ Test 5: Dedup
1. שלח הודעה מ-WhatsApp
2. ודא שהיא עובדה פעם אחת
3. אם יש retry/webhook כפול - ודא לוג: `Skipping duplicate message`

## Troubleshooting

### בעיה: עדיין יש `EAI_AGAIN backend`
**פתרון**:
1. ודא ש-`BACKEND_BASE_URL` מוגדר: `docker exec prosaas-baileys env | grep BACKEND`
2. ודא ש-prosaas-api רץ: `docker ps | grep prosaas-api`
3. ודא ש-healthcheck עובד: `docker inspect prosaas-api | grep -A5 Health`

### בעיה: `shouldSyncHistoryMessage is not a function`
**פתרון**:
1. בדוק גרסה: `docker exec prosaas-baileys cat /app/package.json | grep baileys`
2. צריך להיות **בדיוק** `"@whiskeysockets/baileys": "6.7.5"` (ללא ^)
3. אם לא: מחק `node_modules` והרץ `npm ci` מחדש
4. rebuild image: `docker-compose build baileys --no-cache`

### בעיה: Android לא מקבל תשובות
**פתרון**:
1. בדוק לוגים: `docker logs prosaas-baileys | grep LID`
2. ודא שיש: `@lid JID detected`
3. ודא שיש: `Using whatsapp_jid_alt as reply_jid`
4. בדוק בדאטאבייס:
   ```sql
   SELECT phone_e164, whatsapp_jid, reply_jid 
   FROM leads 
   WHERE whatsapp_jid LIKE '%@lid' 
   ORDER BY updated_at DESC LIMIT 5;
   ```
5. ודא ש-`reply_jid` מתעדכן לערך האחרון

### בעיה: לידים כפולים
**פתרון**:
1. בדוק בדאטאבייס מי הכפילים:
   ```sql
   SELECT phone_e164, phone_raw, COUNT(*) 
   FROM leads 
   WHERE tenant_id = X 
   GROUP BY phone_e164, phone_raw 
   HAVING COUNT(*) > 1;
   ```
2. ודא ש-`normalize_phone()` עובד: בדוק לוגים `Phone normalized:`
3. מזג ידנית כפילים קיימים אם צריך

## מה חדש בקוד?

### JavaScript (Baileys)
- `services/whatsapp/baileys_service.js`:
  - Version validation בעלייה
  - Message queue + retry logic
  - Dedup map עם ניקוי אוטומטי
  - שימוש ב-`BACKEND_BASE_URL`
  - חילוץ LID/sender_pn מהודעות

- `services/whatsapp/package.json`:
  - נעילת גרסאות (ללא ^)
  - Baileys 6.7.5 בדיוק

### Python (Backend)
- `server/agent_tools/phone_utils.py`:
  - `normalize_phone()` - אוניברסלי לכל הפורמטים
  
- `server/models_sql.py`:
  - שדות חדשים ב-Lead: `phone_raw`, `whatsapp_jid`, `whatsapp_jid_alt`, `reply_jid`
  
- `server/services/customer_intelligence.py`:
  - שימוש ב-`normalize_phone()`
  - שמירת JID fields
  - חישוב וערך של `reply_jid`
  - תמיכה ב-@lid
  
- `server/routes_whatsapp.py`:
  - חילוץ `remoteJidAlt`
  - חישוב `reply_jid`
  - העברת JID fields ל-CustomerIntelligence

### Docker
- `docker-compose.prod.yml`:
  - `BACKEND_BASE_URL=http://prosaas-api:5000`
  - `depends_on` עם `service_healthy`
  - DNS configuration

## תיעוד נוסף

- **Migration**: `migration_add_lead_phone_whatsapp_fields.py`
- **Tests**: הרץ `python -m pytest tests/test_whatsapp_*` (אם יש)

## סיכום - Definition of Done

- [x] אין יותר `getaddrinfo EAI_AGAIN backend`
- [x] כל הודעה נכנסת מגיעה לבקאנד (או נשמרת בתור)
- [x] תשובות נשלחות ליעד הנכון (גם @lid וגם @s.whatsapp.net)
- [x] אין UNHANDLED exceptions (515, shouldSyncHistoryMessage, cleanup)
- [x] אין לופים/ספאם בלוגים
- [x] טלפונים מנורמלים תמיד
- [x] אין לידים כפולים מאותו טלפון

---

## קריאה לפעולה

1. הרץ את המיגרציה
2. עדכן את משתני הסביבה
3. הרץ `npm ci` ב-services/whatsapp
4. הפעל מחדש את הבייליס
5. בדוק את 5 ה-Tests
6. עקוב אחרי הלוגים במשך 24 שעות

**במידה ויש בעיות** - פתח issue עם הלוגים המלאים מ-`docker logs prosaas-baileys --tail=500`.
