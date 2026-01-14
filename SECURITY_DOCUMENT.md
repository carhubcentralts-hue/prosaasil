# מסמך אבטחת מידע - מערכת ProSaaS

**גרסה:** 1.0  
**תאריך:** ינואר 2026  
**מצב:** ייצור (Production)

---

## 1. תקציר מנהלים

מערכת ProSaaS היא פלטפורמת SaaS לניהול קשרי לקוחות ושיחות AI בעברית, המיועדת לעסקים קטנים ובינוניים. המערכת מיושמת כשירות ענן עם ארכיטקטורת multi-tenant, המאפשרת לעסקים מרובים לפעול בצורה מבודדת על תשתית משותפת.

### רמת אבטחה כוללת

המערכת מיישמת עקרונות אבטחה סטנדרטיים של SaaS, כולל:
- **הפרדת נתונים בין לקוחות** - הפרדה לוגית ברמת מסד הנתונים
- **אימות משתמשים** - מערכת התחברות מבוססת tokens עם timeout אוטומטי
- **תקשורת מוצפנת** - HTTPS/TLS לכל התקשורת החיצונית
- **ניהול סודות** - שימוש במשתני סביבה ואבטחת API keys
- **אימות webhooks** - חתימות דיגיטליות לאימות בקשות מ-Twilio
- **לוגים ומעקב** - רישום פעולות קריטיות למעקב ובקרה

### נקודות חוזק

1. **הפרדה ברורה בין לקוחות** - כל עסק מזוהה באמצעות business_id ומבודד מעסקים אחרים
2. **שימוש בספקי שירות מוכרים** - PostgreSQL, OpenAI, Twilio - ספקים מבוססים עם תקני אבטחה גבוהים
3. **ארכיטקטורת containers** - פריסת Docker עם Nginx כ-reverse proxy, הפרדה בין שירותים
4. **ניהול זהויות מובנה** - תמיכה במספר תפקידי משתמש עם הרשאות מותאמות
5. **אימות webhooks** - אבטחת נקודות קצה חיצוניות באמצעות סודות משותפים וחתימות

### נקודות חולשה

1. **אין הצפנת נתונים במנוחה** - נתונים במסד הנתונים לא מוצפנים ברמת השדה
2. **הסתמכות על ספקי צד שלישי** - תלות ב-OpenAI, Twilio לפונקציונליות ליבה
3. **לוגים עשויים להכיל מידע רגיש** - תמלילי שיחות, מספרי טלפון עשויים להישמר בלוגים
4. **אין audit trail מלא** - מעקב חלקי אחר שינויים במערכת
5. **אין 2FA/MFA** - אימות דו-שלבי לא מיושם

---

## 2. ארכיטקטורת המערכת

### 2.1 מבנה כללי

המערכת בנויה מ-4 רכיבים עיקריים:

```
┌─────────────────────────────────────────┐
│         NGINX Reverse Proxy             │
│         (Port 80/443 - HTTPS)           │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────┴─────────┬──────────────┐
        │                   │              │
┌───────▼───────┐  ┌────────▼─────┐  ┌────▼─────┐
│   Frontend    │  │   Backend    │  │   n8n    │
│  (React SPA)  │  │  (Python/    │  │ (Workflow│
│               │  │   Flask)     │  │ Platform)│
└───────────────┘  └────────┬─────┘  └──────────┘
                            │
                   ┌────────┴─────────┐
                   │   PostgreSQL DB   │
                   │   (Managed/       │
                   │    External)      │
                   └──────────────────┘
```

**רכיבים נוספים:**
- **Baileys** - שירות WhatsApp (Node.js) - תקשורת פנימית
- **Recording Worker** - עיבוד הקלטות (Python background job)

### 2.2 תקשורת בין רכיבים

- **Frontend ↔ Backend**: HTTPS, JSON API, WebSocket למדיה (Twilio)
- **Backend ↔ Database**: PostgreSQL protocol (מוצפן באמצעות SSL במידת הצורך)
- **Backend ↔ OpenAI**: HTTPS REST API, API key authentication
- **Backend ↔ Twilio**: HTTPS webhooks עם אימות חתימה דיגיטלית
- **Baileys ↔ Backend**: HTTP פנימי (תוך רשת Docker), אימות באמצעות INTERNAL_SECRET
- **Backend ↔ n8n**: HTTPS webhooks (אופציונלי)

### 2.3 סביבת הפריסה

המערכת פרוסה באמצעות Docker Compose עם:
- **ניתוב יחיד**: Nginx כנקודת כניסה אחת
- **רשת פנימית**: כל הרכיבים ברשת Docker סגורה (`prosaas-network`)
- **חשיפה חיצונית מינימלית**: רק Nginx על פורטים 80/443
- **Volumes מתמשכים**: נתונים נשמרים ב-Docker volumes (הקלטות, auth WhatsApp, n8n)

---

## 3. הפרדת לקוחות ונתונים (Multi-Tenancy)

### 3.1 מודל ההפרדה

המערכת משתמשת ב-**הפרדה לוגית ברמת מסד הנתונים**:
- כל עסק מיוצג על ידי רשומה בטבלת `business` עם `business_id` ייחודי
- כל טבלה במסד הנתונים מכילה עמודה `business_id` או `tenant_id`
- שאילתות לבסיס הנתונים מסוננות אוטומטית לפי העסק המחובר

### 3.2 אבטחת ההפרדה

**שכבת האימות:**
```python
# כל בקשת API עוברת דרך @require_auth או @require_api_auth
# הדקורטור מזהה את העסק מ-session/token ושומר ב-g.tenant

@require_auth
def my_endpoint():
    tenant_id = get_current_tenant()  # מחזיר business_id מאומת
    # כל שאילתה מסוננת לפי tenant_id
```

**שכבת מסד הנתונים:**
```python
# דוגמה: קבלת לידים
leads = Lead.query.filter_by(business_id=tenant_id).all()
```

**תכנון טבלאות:**
- `business` - מידע על כל עסק
- `users` - משתמשים + `business_id` (FK)
- `customer`, `leads`, `call_log` - כל הרשומות כוללות `business_id`
- `business_contact_channels` - מיפוי מספרי טלפון/מזהים לעסקים

### 3.3 מניעת data leakage בין לקוחות

**מנגנוני ההגנה:**
1. **אימות מחייב** - כל endpoint דורש התחברות
2. **סינון אוטומטי** - קוד מסנן תמיד לפי `tenant_id` מה-session
3. **אין גישה ישירה לעסקים אחרים** - אין API שמאפשר לבחור `business_id` שרירותי
4. **system_admin role** - רק לאדמין מערכת יש גישה לעסקים מרובים (עם impersonation מפורש)

**דוגמה לזרימה:**
```
1. משתמש מתחבר → מקבל session עם business_id=5
2. בקשה ל-GET /api/leads → הדקורטור מוודא business_id=5
3. השאילתה: SELECT * FROM leads WHERE business_id=5
4. התשובה מכילה רק לידים של עסק 5
```

### 3.4 זיהוי tenant בשיחות ו-WhatsApp

**שיחות קוליות (Twilio):**
- טבלת `business_contact_channels` ממפה מספרי Twilio לעסקים
- כל שיחה נכנסת מזוהה לפי מספר היעד (`To`) → מציאת `business_id`

**WhatsApp:**
- Baileys שולח `tenantId` בכל webhook
- המערכת מאמתת את ה-tenant בעת קבלת הודעות

---

## 4. ניהול זהויות והרשאות

### 4.1 מנגנון התחברות

**תהליך Login:**
1. משתמש שולח `email` ו-`password` ל-`POST /api/auth/login`
2. המערכת מחפשת את המשתמש במסד הנתונים (`users` table)
3. **אימות סיסמה:** השוואת hash מול `password_hash` (werkzeug/pbkdf2)
4. אם תקין: יצירת **refresh token** (SHA-256 hash) + שמירת session
5. התשובה: פרטי משתמש + token
6. הדפדפן שומר token/session ושולח בכל בקשה

**טכנולוגיות:**
- **Password hashing**: werkzeug's `generate_password_hash` (pbkdf2:sha256)
- **Session management**: Flask session (cookie-based)
- **Refresh tokens**: טבלת `refresh_tokens` עם hash SHA-256

### 4.2 מחזור חיי Token

**Access Token:**
- **תוקף:** 90 דקות
- **שימוש:** כל בקשת API
- **אחסון:** Browser session/localStorage

**Refresh Token:**
- **תוקף רגיל:** 24 שעות
- **תוקף "זכור אותי":** 30 יום
- **שימוש:** חידוש access token
- **אחסון:** מסד נתונים (hashed) + cookie

**Idle Timeout:**
- **תוקף:** 75 דקות חוסר פעילות
- **מנגנון:** `last_activity_at` מתעדכן בכל פעילות
- **אכיפה:** בדיקה בכל בקשה אם עבר timeout

### 4.3 ניהול סיסמאות

**יצירת סיסמה:**
- Hash באמצעות `werkzeug.security.generate_password_hash`
- אלגוריתם: pbkdf2:sha256 (מובנה, מאובטח)
- השדה `password_hash` מכיל את ה-hash המלא (כולל salt)

**איפוס סיסמה:**
1. משתמש מבקש איפוס → מערכת יוצרת `reset_token` אקראי
2. Token נשמר כ-hash SHA-256 ב-`reset_token_hash`
3. שליחת מייל עם קישור המכיל token מקורי
4. **תוקף:** 60 דקות
5. **שימוש חד-פעמי:** `reset_token_used=true` אחרי שימוש ראשון

**שדות באבטחה:**
- `password_hash` - Hash של סיסמת המשתמש
- `reset_token_hash` - Hash של token איפוס זמני
- `reset_token_expiry` - תאריך תפוגה
- `reset_token_used` - דגל חד-פעמי

### 4.4 תפקידי משתמש

**Role-Based Access Control (RBAC):**

| תפקיד | הרשאות | טווח גישה |
|------|---------|-----------|
| **system_admin** | ניהול כל העסקים, גישה מלאה למערכת | כל העסקים |
| **owner** | ניהול מלא של העסק שלו, הגדרות, משתמשים, נתונים | עסק אחד |
| **admin** | ניהול נתונים, לידים, שיחות (בלי הגדרות קריטיות) | עסק אחד |
| **agent** | גישה לשיחות ולידים בלבד, בלי ניהול | עסק אחד |

**אכיפת הרשאות:**
```python
@require_api_auth(allowed_roles=["owner", "system_admin"])
def sensitive_endpoint():
    # רק owner או system_admin יכולים לגשת
```

### 4.5 גישה לפעולות רגישות

**פעולות רגישות מוגבלות ל-owner/system_admin:**
- שינוי הגדרות עסק (business settings)
- עדכון webhook URLs
- ניהול משתמשים (הוספה/הסרה)
- עדכון system_prompt (ה-AI prompt)
- שינוי webhook_secret

**הפרדת הרשאות במסד הנתונים:**
- אין API ישיר לשליפת נתונים ללא tenant context
- כל משתמש רואה רק את העסק שלו
- system_admin יכול ל-impersonate עסק אחר (מתועד)

---

## 5. אבטחת תקשורת

### 5.1 פרוטוקולי תקשורת

**HTTPS/TLS:**
- כל התקשורת עם הדפדפן דרך HTTPS (פורט 443)
- Nginx מטפל ב-SSL termination
- תעודת SSL נדרשת לפריסה (לא כלולה במאגר)
- **המלצה:** שימוש ב-Let's Encrypt לתעודות חינמיות

**WebSocket Secure (WSS):**
- שיחות קוליות משתמשות ב-WebSocket למדיה
- תקשורת מוצפנת דרך TLS (wss://)
- Nginx מעביר את החיבור לשירות Backend

### 5.2 הגנה על API

**אימות בקשות:**
- כל endpoint מוגן באמצעות decorators (`@require_auth`)
- Session/token נבדק בכל בקשה
- החזרת 401 Unauthorized במקרה של כשלון

**CSRF Protection:**
- שימוש ב-Flask-SeaSurf
- Token ב-cookie + header (`X-CSRF-Token`)
- אכיפה על כל בקשות POST/PUT/DELETE
- פטור מפורש ל-webhooks חיצוניים

**Rate Limiting:**
- מימוש חלקי - `rate_limiter.py`
- הגבלת מספר שיחות במקביל לכל עסק
- **חסר:** rate limiting גלובלי על endpoints

### 5.3 Webhooks ואינטגרציות חיצוניות

**Twilio Webhooks:**
```python
# אימות חתימה דיגיטלית
@require_twilio_signature
def twilio_webhook():
    # Twilio חותם כל בקשה עם HMAC-SHA1
    # המערכת מאמתת באמצעות TWILIO_AUTH_TOKEN
```

**מנגנון אימות:**
1. Twilio חותם URL + parameters עם HMAC-SHA1
2. שולח את החתימה ב-header `X-Twilio-Signature`
3. השרת מחשב מחדש את החתימה ומשווה
4. אם לא תואם → 403 Forbidden

**WhatsApp (Baileys):**
```python
# אימות באמצעות INTERNAL_SECRET
def validate_internal_secret():
    received = request.headers.get('X-Internal-Secret')
    if received != INTERNAL_SECRET:
        return 401
```

**n8n/Zapier Webhooks:**
- שימוש ב-`webhook_secret` ייחודי לכל עסק
- format: `wh_n8n_<random_hex>`
- אימות בעת קבלת בקשה מחיצונית

### 5.4 הגנה מפני מתקפות נפוצות

**SQL Injection:**
- שימוש ב-SQLAlchemy ORM
- Parameterized queries בלבד
- אין concatenation של SQL ישיר

**XSS (Cross-Site Scripting):**
- React escaping אוטומטי של תוכן
- Sanitization של inputs בצד שרת
- **חסר:** הגדרת Content-Security-Policy headers מפורשת

**CSRF:**
- הגנה מובנית עם Flask-SeaSurf
- Token validation בכל מוטציה

**Path Traversal:**
- אין גישה ישירה לקבצים מהמשתמש
- הקלטות מוגשות דרך API מאובטח

---

## 6. אבטחת נתונים

### 6.1 אחסון נתונים

**מסד נתונים - PostgreSQL:**
- **סוג:** Relational database (מנוהל/חיצוני או Docker local)
- **חיבור:** באמצעות `DATABASE_URL` מוצפן (SSL אופציונלי)
- **גישה:** רק Backend service
- **גיבוי:** תלוי בספק (Supabase, Railway, Neon, וכו')

**מבנה טבלאות עיקריות:**
- `business` - פרטי עסקים
- `users` - משתמשים (עם password_hash)
- `customer` - לקוחות של עסקים
- `leads` - לידים מעסקאות
- `call_log` - רישום שיחות (call_sid, duration, status)
- `whatsapp_message` - הודעות WhatsApp
- `faqs` - שאלות ותשובות
- `outbound_call_templates` - תבניות לשיחות יוצאות
- `refresh_tokens` - tokens מחוברים למשתמשים

### 6.2 הצפנת נתונים

**בעת תקשורת (In-Transit):**
- ✅ HTTPS/TLS לכל תקשורת חיצונית
- ✅ PostgreSQL SSL (אם מוגדר ב-DATABASE_URL)
- ✅ OpenAI API - HTTPS

**במנוחה (At-Rest):**
- ❌ **אין הצפנה ברמת השדה** במסד הנתונים
- ❌ סיסמאות מאוחסנות כ-hash (לא הצפנה הפיכה)
- ❌ נתונים רגישים (שמות, טלפונים, תמלילים) לא מוצפנים
- ✅ הסתמכות על הצפנה ברמת הדיסק של ספק ה-DB (Supabase, וכו')

**הקלטות:**
- נשמרות ב-Docker volume `recordings_data`
- גישה דרך Backend API בלבד
- **פורמט:** MP3/WAV (לא מוצפנות)
- **גישה:** מוגבלת לפי tenant

### 6.3 גישה למסד הנתונים

**מי יכול לגשת:**
- רק שירות Backend (Flask)
- אין גישה ישירה למשתמשים
- אין חשיפה של פורט PostgreSQL החוצה

**אמצעי אבטחה:**
- **Credentials:** `DATABASE_URL` מוגדר כמשתנה סביבה
- **Network isolation:** DB נמצא ברשת פנימית או managed service מרוחק
- **No raw queries:** שימוש ב-ORM בלבד

### 6.4 מניעת חשיפה חיצונית

**דליפות מידע:**
- אין הדפסת סיסמאות ב-logs
- session tokens מסוננים מלוגים
- Error messages לא חושפים פרטי DB

**גיבויים:**
- תלוי בספק (Supabase → automatic backups)
- **חסר:** מדיניות גיבוי מפורשת במסמך

---

## 7. שימוש ב-AI ואבטחת מידע

### 7.1 אינטגרציות AI

**OpenAI:**
- **שימוש:** שיחות קוליות (Realtime API), תמלול (Whisper), תקצור, עיבוד שפה טבעית
- **חיבור:** HTTPS API עם `OPENAI_API_KEY`
- **נתונים נשלחים:**
  - תמלילי שיחות (audio → text)
  - system_prompt (הוראות להתנהגות ה-AI)
  - היסטוריית שיחה (context)
  - פרטי לקוח (שם, מספר טלפון - במידת הצורך)

**Twilio:**
- **שימוש:** שיחות קוליות, WebSocket streaming
- **נתונים נשלחים:**
  - אודיו בזמן אמת (mulaw encoded)
  - מספרי טלפון (caller/callee)

### 7.2 הגבלת גישת ה-AI

**OpenAI מקבל:**
- תמלילי שיחות (audio → text) - **נדרש לפונקציונליות**
- System prompts מותאמים אישית - **נדרש לפונקציונליות**
- היסטוריית שיחה לקונטקסט - **נדרש לפונקציונליות**

**OpenAI לא מקבל:**
- סיסמאות, payment info (אין כזה במערכת)
- נתוני עסקים רגישים (database structure, business logic)

**מגבלות:**
- ✅ אין שליחת תוכן DB שלם
- ✅ רק נתונים שנדרשים לשיחה הנוכחית
- ❌ **חסר:** data retention policy מפורש עם OpenAI
- ❌ **חסר:** Data Processing Agreement (DPA) מתועד

### 7.3 שמירת מידע רגיש

**מה נשמר במערכת:**
- תמלילי שיחות (`call_log.final_transcript`)
- הקלטות שמע (`recordings_data` volume)
- הודעות WhatsApp מלאות (`whatsapp_message.body`)
- פרטי לקוח (שם, טלפון, מייל) ב-`customer` ו-`leads`

**מה נשלח ל-OpenAI:**
- תמלילים בזמן אמת (לא נשמרים אצלם לפי מדיניותם)
- System prompts
- **הערה:** OpenAI Zero Data Retention policy - לא שומרים נתונים מה-API (צריך לאמת בחוזה)

**מה נשלח ל-Twilio:**
- שמע בזמן אמת (streaming)
- הקלטות שיחות (אופציונלי)
- **הערה:** Twilio שומר call metadata + recordings (לפי תנאי השירות)

### 7.4 בקרה על זרימת נתונים

**הגבלות ברמת הקוד:**
- system_prompt מוגבל באורך (לא ניתן לשלוח כל ה-DB)
- Context window מוגבל (רק 5-10 הודעות אחרונות)
- לא נשלחים נתונים מעסקים אחרים

**Sanitization:**
- ✅ אין שליחת raw SQL results
- ✅ רק שדות רלוונטיים (שם, טלפון, נושא)
- ❌ **חסר:** סינון אוטומטי של PII לפני שליחה ל-AI

---

## 8. לוגים, ניטור ובקרה

### 8.1 רישום פעולות

**מנגנון Logging:**
- **ספרייה:** Python `logging` + custom JSON formatter
- **קבצים:** `logging_setup.py`, `logging_async.py`
- **פורמט:** JSON structured logs
- **רמות:** INFO, WARNING, ERROR, DEBUG

**מה נרשם:**
- התחברויות (login success/failure)
- שיחות (call_start, call_end, duration)
- הודעות WhatsApp (incoming/outgoing)
- שגיאות קריטיות
- ביצועים (latency metrics)

### 8.2 ניטור חריגות

**Event logging:**
```python
# דוגמה - רישום פעילות
logger.info(f"User {user.id} logged in from {ip}")
logger.error(f"Failed login attempt: {email}")
```

**מעקב אחר:**
- ניסיונות התחברות כושלים
- שגיאות API (500, 403, 401)
- שיחות כושלות
- תקלות באינטגרציות (Twilio, OpenAI)

**אזעקות:**
- ❌ **חסר:** מערכת alerting אוטומטית
- ❌ **חסר:** dashboard לניטור בזמן אמת

### 8.3 Traceability

**מעקב אחר פעולות:**
- כל שיחה יש `call_sid` ייחודי
- כל הודעת WhatsApp יש `id` ייחודי
- Logs כולל timestamps מדויקים

**Audit Trail:**
- ✅ טבלת `prompt_revisions` - מעקב אחר שינויים ב-system_prompt
- ✅ `updated_by`, `updated_at` על טבלאות
- ❌ **חסר:** audit log גלובלי לכל שינויים במערכת
- ❌ **חסר:** מי עשה מה ומתי (user action logging)

### 8.4 מדיניות שמירת לוגים

**Production policy:**
- DEBUG=1 (production) - לוגים מינימליים בלבד
- אין הדפסת נתונים רגישים בלוגים (סיסמאות, tokens)
- Rate limiting על לוגים חוזרים

**Retention:**
- ❌ **לא מוגדר** - כמה זמן שומרים לוגים
- ❌ **לא מוגדר** - rotation policy לקבצי log

---

## 9. ניהול סודות ומפתחות

### 9.1 אחסון API Keys

**Environment Variables:**
- כל ה-secrets נשמרים בקובץ `.env` (לא commited ל-git)
- `.env.example` מכיל תבנית ללא ערכים אמיתיים
- **קריטי:** אין commits של `.env` למאגר

**Secrets נדרשים:**
```bash
OPENAI_API_KEY=sk-...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
FLASK_SECRET_KEY=...
DATABASE_URL=postgresql://...
INTERNAL_SECRET=...
BAILEYS_WEBHOOK_SECRET=...
WHATSAPP_WEBHOOK_SECRET=...
SENDGRID_API_KEY=...
```

### 9.2 שימוש ב-Environment Variables

**בקוד:**
```python
import os
api_key = os.getenv("OPENAI_API_KEY")
```

**ב-Docker:**
```yaml
services:
  backend:
    env_file:
      - .env
```

**יתרונות:**
- אין hardcoding של secrets
- פשוט לעדכן בסביבות שונות (dev/prod)
- תואם ל-12-factor app

### 9.3 מניעת חשיפה בקוד

**אמצעים:**
- ✅ `.gitignore` כולל `.env`
- ✅ `.env.example` ללא ערכים אמיתיים
- ✅ אין הדפסת secrets בלוגים
- ✅ Error messages לא חושפים credentials

**בדיקות:**
```python
# טוב
api_key = os.getenv("OPENAI_API_KEY")

# רע
api_key = "sk-proj-abcd1234..."  # ❌ לעולם לא!
```

### 9.4 רוטציה של מפתחות

**מדיניות:**
- ❌ **חסר:** תהליך רוטציה תקופתי מוגדר
- ❌ **חסר:** תיעוד כיצד להחליף מפתחות בפרודקשן
- ✅ ניתן לעדכן ב-`.env` ולהפעיל מחדש את הקונטיינרים

**המלצה:**
- החלף FLASK_SECRET_KEY כל 6-12 חודשים
- החלף INTERNAL_SECRET אם חשוד לחשיפה
- OpenAI/Twilio - לפי מדיניות הספק

---

## 10. נקודות חולשה וסיכונים

### 10.1 סיכונים קיימים

**1. אין הצפנה ברמת השדה (Field-Level Encryption)**
- **השפעה:** נתונים רגישים (שמות, טלפונים, תמלילים) נשמרים בטקסט פשוט
- **מיתון:** הסתמכות על encryption at rest של ספק ה-DB
- **סיכון:** במקרה של data breach → חשיפה מלאה של נתונים

**2. תלות בספקי צד שלישי**
- **OpenAI:** נפילה = אין AI בשיחות
- **Twilio:** נפילה = אין שיחות בכלל
- **מיתון:** אין fallback מיושם

**3. לוגים עשויים להכיל מידע רגיש**
- **השפעה:** תמלילי שיחות, מספרי טלפון בלוגים
- **מיתון:** DEBUG=1 מפחית logs, אך לא מונע לחלוטין
- **סיכון:** חשיפת logs = חשיפת PII

**4. אין Audit Trail מלא**
- **השפעה:** קשה לעקוב אחר כל שינוי במערכת
- **מיתון:** logging חלקי של פעולות קריטיות
- **סיכון:** קושי לחקור תקלות אבטחה

**5. אין 2FA/MFA**
- **השפעה:** אימות תלוי בסיסמה בלבד
- **מיתון:** idle timeout, token expiry
- **סיכון:** פריצה בסיסמה = גישה מלאה

**6. Rate Limiting חלקי**
- **השפעה:** חשוף ל-DoS, brute force
- **מיתון:** rate limiting על שיחות בלבד
- **סיכון:** ניתן לבצע מתקפת brute force על login

**7. אין Data Loss Prevention (DLP)**
- **השפעה:** לא ניתן למנוע שליחת PII ל-AI
- **מיתון:** תכנות זהיר של system prompts
- **סיכון:** דליפת מידע רגיש ל-OpenAI

### 10.2 מגבלות אבטחה

**מה לא מכוסה כרגע:**
- ❌ Penetration testing
- ❌ Security audits חיצוניים
- ❌ Compliance certifications (ISO 27001, SOC 2)
- ❌ GDPR compliance מלא (אין data retention policy מפורש)
- ❌ Incident response plan
- ❌ Disaster recovery plan
- ❌ Encryption key management
- ❌ Network segmentation מתקדם
- ❌ Web Application Firewall (WAF)
- ❌ Intrusion Detection System (IDS)

### 10.3 תרחישי איום

**תרחיש 1: פריצה למשתמש**
- **איום:** attacker מנחש סיסמה
- **השפעה:** גישה לנתוני העסק
- **מיתון:** password hashing, idle timeout
- **חסר:** 2FA, account lockout

**תרחיש 2: SQL Injection**
- **איום:** attacker מנסה להזריק SQL
- **השפעה:** גישה למסד הנתונים
- **מיתון:** SQLAlchemy ORM, parameterized queries
- **סיכון:** נמוך (מוגן טוב)

**תרחיש 3: Man-in-the-Middle (MITM)**
- **איום:** attacker מיירט תקשורת
- **השפעה:** גניבת credentials/tokens
- **מיתון:** HTTPS/TLS
- **סיכון:** נמוך (מוגן טוב)

**תרחיש 4: Data Breach ב-DB**
- **איום:** חשיפת database
- **השפעה:** כל הנתונים ברורים (לא מוצפנים)
- **מיתון:** הגבלת גישה, DB credentials
- **סיכון:** גבוה (אין encryption at rest ברמת השדה)

**תרחיש 5: Compromised API Key**
- **איום:** חשיפת OPENAI_API_KEY
- **השפעה:** שימוש לרעה, חיוב יתר
- **מיתון:** environment variables, no commits
- **סיכון:** בינוני (תלוי בזהירות)

---

## 11. המלצות לשיפור

### 11.1 שיפורים קריטיים (גבוה)

**1. הוספת 2FA/MFA**
- יישום אימות דו-שלבי (SMS, TOTP, Email)
- הגנה מפני פריצת סיסמאות
- **מאמץ:** בינוני | **השפעה:** גבוהה

**2. Field-Level Encryption**
- הצפנת שדות רגישים (שם, טלפון, תמלול)
- שימוש ב-encryption keys מנוהלים
- **מאמץ:** גבוה | **השפעה:** גבוהה מאוד

**3. Comprehensive Audit Trail**
- רישום כל פעולה במערכת (מי, מה, מתי)
- טבלת audit_log גלובלית
- **מאמץ:** בינוני | **השפעה:** גבוהה

**4. Rate Limiting גלובלי**
- הגבלה על login attempts
- הגבלה על כל ה-endpoints
- **מאמץ:** נמוך | **השפעה:** בינונית

### 11.2 שיפורים חשובים (בינוני)

**5. Data Retention Policy**
- מדיניות מפורשת לשמירת נתונים
- מחיקה אוטומטית של נתונים ישנים
- **מאמץ:** נמוך | **השפעה:** בינונית (GDPR)

**6. Alerting & Monitoring**
- מערכת התראות על חריגות
- Dashboard לניטור בזמן אמת
- **מאמץ:** בינוני | **השפעה:** בינונית

**7. WAF (Web Application Firewall)**
- הגנה מתקדמת מפני מתקפות web
- סינון של בקשות חשודות
- **מאמץ:** בינוני | **השפעה:** בינונית

**8. Secrets Management Platform**
- שימוש ב-HashiCorp Vault או AWS Secrets Manager
- רוטציה אוטומטית של מפתחות
- **מאמץ:** בינוני | **השפعה:** בינונית

### 11.3 שיפורים רצויים (נמוך)

**9. Penetration Testing**
- בדיקת חדירה מקצועית
- זיהוי פרצות אבטחה
- **מאמץ:** נמוך (outsource) | **השפעה:** גבוהה (מניעתית)

**10. GDPR Compliance**
- Right to be forgotten
- Data portability
- Privacy by design
- **מאמץ:** גבוה | **השפעה:** קריטית (משפטית)

**11. Backup & Disaster Recovery**
- תוכנית גיבוי מפורטת
- נהלי שחזור מאסון
- **מאמץ:** בינוני | **השפעה:** קריטית בתקלה

**12. Security Headers**
- Content-Security-Policy
- X-Frame-Options
- X-Content-Type-Options
- **מאמץ:** נמוך | **השפעה:** נמוכה

### 11.4 סדר עדיפויות מומלץ

**Phase 1 (חודשים 1-3):**
1. Rate Limiting גלובלי
2. 2FA/MFA
3. Audit Trail מלא

**Phase 2 (חודשים 4-6):**
4. Field-Level Encryption
5. Data Retention Policy
6. Monitoring & Alerting

**Phase 3 (חודשים 7-12):**
7. WAF
8. Penetration Testing
9. GDPR Compliance
10. Secrets Management Platform

---

## סיכום

מערכת ProSaaS מיישמת **אבטחה סטנדרטית ברמת SaaS**, המתאימה לעסקים קטנים ובינוניים. המערכת כוללת הפרדה נכונה בין לקוחות, אימות משתמשים, תקשורת מוצפנת, וניהול סודות בסיסי.

**נקודות חוזק עיקריות:**
- הפרדת tenants מובנית ומאובטחת
- שימוש בספקי שירות מוכרים ומאובטחים
- ארכיטקטורת microservices עם Nginx כשער אבטחה
- אימות webhooks חזק (Twilio signature)

**נקודות לשיפור עיקריות:**
- הצפנת נתונים במנוחה (field-level)
- 2FA/MFA
- Audit trail מלא
- Rate limiting גלובלי
- מדיניות GDPR מלאה

**המלצה כללית:**  
המערכת מתאימה לשימוש בפרודקשן עבור עסקים שלא מטפלים בנתונים רגולטוריים קריטיים (פיננסים, רפואה). לעסקים עם דרישות אבטחה מחמירות, מומלץ ליישם את השיפורים בפאזה 1-2 לפני שימוש בייצור.

---

**תאריך עדכון אחרון:** ינואר 2026  
**גרסת מסמך:** 1.0  
**נוצר על ידי:** AI Security Audit Agent  
