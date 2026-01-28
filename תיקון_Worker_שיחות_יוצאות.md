# תיקון מערכת ה-Worker לשיחות יוצאות - מדריך פריסה

## תיאור הבעיה

היתה בעיה של "שתי מערכות רקע במקביל" - גם Threads בתוך ה-API וגם Worker של RQ, מה שגרם ל:

1. **כפילויות** - אותו Run נכנס לתור פעמיים / מתעדכן פעמיים
2. **ה-UI תקוע** - מציג "פרוגרס=3" גם כשאין שיחות
3. **Runs תקועים** - אחרי ריסטארט נשארים ב-DB/Redis כי ה-cleanup נכשל
4. **לוגים כפולים** - אותן פעולות מתבצעות פעמיים

## הפתרון שיושם

### 1. ביטול Thread בתוך ה-API ✅

**מה שינינו**: קובץ `server/routes_outbound.py` שורה 2796

**לפני**:
```python
# השתמש ב-Thread כדי לעבד את הג'וב הבא
threading.Thread(
    target=process_next_queued_job,
    args=(next_job_id, run_id),
    daemon=True,
    name=f"ProcessNext-{next_job_id}"
).start()
```

**אחרי**:
```python
# 🔥 תיקון: השתמש ב-RQ worker במקום Thread
queue.enqueue(
    'server.routes_outbound.process_next_queued_job',
    next_job_id,
    run_id,
    job_timeout='10m',
    job_id=f"process_next_{next_job_id}"
)
```

**תוצאה**: 
- ✅ אין יותר Threads
- ✅ הכל רץ רק דרך RQ worker
- ✅ אין כפילויות

### 2. תיקון ה-Cleanup שנכשל ✅

**הבעיה**: ה-cleanup רץ לפני `db.init_app()` וזה גרם לשגיאה:
```
Flask app is not registered with this 'SQLAlchemy' instance
```

**הפתרון**: העברנו את ה-cleanup להתבצע אחרי `db.init_app()` ובתוך `app.app_context()`

**קובץ**: `server/app_factory.py` שורה 1085

**קוד חדש**:
```python
# אתחול SQLAlchemy
db.init_app(app)

# נקה Runs תקועים רק ב-API service (לא ב-Worker)
service_role = os.getenv('SERVICE_ROLE', 'api').lower()
if service_role != 'worker':
    with app.app_context():
        cleanup_stuck_dialing_jobs()
        cleanup_stuck_runs(on_startup=True)
```

**תוצאה**:
- ✅ Cleanup עובד בלי שגיאות
- ✅ רק ה-API מריץ cleanup, לא ה-Worker
- ✅ גם Redis מנוקה אחרי ריסטארט

### 3. הוספת לוגים מפורטים ✅

**קובץ**: `server/logging_config.py`

**מה הוספנו**: במצב DEBUG (פיתוח) - לוגים מפורטים למודולים של outbound:
- `server.routes_outbound`
- `server.jobs.enqueue_outbound_calls_job`
- `server.services.outbound_semaphore`
- `server.worker`
- `rq.worker`

**איך להפעיל**:
```bash
LOG_LEVEL=DEBUG
```

## איך זה עובד עכשיו?

### תהליך שיחה יוצאת (לאחר התיקון)

```
משתמש לוחץ "התחל שיחות"
    ↓
API: יוצר OutboundCallRun + Jobs
    ↓
API: שולח ל-RQ worker (תור)
    ↓
RQ Worker: מעבד את הג'וב
    ↓
RQ Worker: לולאה ראשית:
    - לוקח ג'וב הבא מה-DB
    - תופס slot ב-Redis (מקסימום 3 במקביל)
    - יוצר שיחה ב-Twilio
    - שומר call_sid
    ↓
Webhook מ-Twilio: שיחה הסתיימה
    ↓
API: מקבל webhook, משחרר slot
    ↓
API: שולח את הג'וב הבא ל-RQ worker  ← 🔥 תיקון: לא Thread
    ↓
RQ Worker: מעבד את הג'וב הבא
```

### עקרונות מרכזיים

1. **RQ Worker בלבד** - כל העיבוד דרך RQ
2. **אין Threads** - בוטלו לגמרי
3. **Consumer יחיד** - רק worker אחד מעבד כל run
4. **Semaphore ב-Redis** - מגבלה של 3 שיחות במקביל
5. **Heartbeat** - ניטור של 5 דקות כדי לזהות workers מתים
6. **Cleanup בהפעלה** - מסמן runs "תקועים" כ-failed

## משתני סביבה נדרשים

### הגדרות .env

```bash
# Redis - חובה לעבודה עם RQ
REDIS_URL=redis://redis:6379/0

# זיהוי סוג השירות
SERVICE_ROLE=api          # עבור API service
SERVICE_ROLE=worker       # עבור Worker service

# רמת לוגים
LOG_LEVEL=DEBUG           # פיתוח: לוגים מלאים
LOG_LEVEL=INFO            # פרודקשן: לוגים מינימליים
PYTHONUNBUFFERED=1        # מונע באפר של לוגים
```

### docker-compose.yml

**API Service**:
```yaml
environment:
  SERVICE_ROLE: api
  LOG_LEVEL: ${LOG_LEVEL:-INFO}
  REDIS_URL: redis://redis:6379/0
```

**Worker Service**:
```yaml
environment:
  SERVICE_ROLE: worker
  LOG_LEVEL: ${LOG_LEVEL:-DEBUG}
  REDIS_URL: redis://redis:6379/0
  RQ_QUEUES: high,default,low,receipts,receipts_sync,maintenance,recordings,broadcasts
```

## צ'קליסט לבדיקה

- [ ] התחל שיחות יוצאות - וודא ש-RQ מקבל (לא Thread)
- [ ] בדוק לוגים עבור "enqueuing next job to RQ worker"
- [ ] עשה ריסטארט ל-API - וודא ש-cleanup עובד בלי שגיאת SQLAlchemy
- [ ] בדוק ש-Runs תקועים מסומנים "failed" אחרי ריסטארט
- [ ] וודא שאין עיבוד כפול של שיחות
- [ ] בדוק ש-Redis slots מנוקים כמו שצריך
- [ ] בדוק שביטול עובד
- [ ] וודא ש-LOG_LEVEL=DEBUG מפעיל לוגים מפורטים
- [ ] בדוק ש-Worker לא מריץ cleanup

## שלבי הפריסה

### 1. עדכון משתני סביבה

עדכן את קובץ `.env`:
```bash
LOG_LEVEL=INFO          # או DEBUG לאבחון בעיות
REDIS_URL=redis://redis:6379/0
PYTHONUNBUFFERED=1
```

### 2. ריסטארט לשירותים

```bash
# עצור את כל השירותים
docker compose down

# הרם מחדש עם build
docker compose up -d --build
```

או אם משתמש בפרופיל production:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

### 3. בדוק לוגים

```bash
# לוגים של API - וודא שה-cleanup עובד
docker compose logs -f prosaas-api | grep "STARTUP"

# לוגים של Worker - וודא שעובד עם RQ
docker compose logs -f worker | grep "ProcessNext"

# לוגים כלליים
docker compose logs -f
```

### 4. וודא שהכל עובד

בדוק בלוגים:
- ✅ "STARTUP] Running outbound cleanup" - הופיע
- ✅ "STARTUP] ✅ Outbound cleanup complete" - הופיע
- ✅ "enqueuing next job to RQ worker" - הופיע במקום "starting in thread"
- ❌ "Flask app is not registered" - לא צריך להופיע יותר
- ❌ "starting next job in thread" - לא צריך להופיע יותר

## פתרון בעיות

### שגיאה: "Flask app is not registered with SQLAlchemy"
**פתרון**: התיקון שלנו צריך לפתור את זה. אם עדיין קורה:
1. וודא שהקוד המעודכן נטען (עשה `git pull`)
2. עשה rebuild: `docker compose up -d --build`

### לא רואה לוגים מפורטים
**פתרון**: הגדר `LOG_LEVEL=DEBUG` ב-`.env` ועשה ריסטארט

### שיחות מתעבדות פעמיים
**פתרון**: 
1. בדוק שה-REDIS_URL מוגדר נכון
2. וודא שה-Worker service רץ
3. בדוק בלוגים אם יש "starting in thread" (לא צריך)

### Runs נשארים תקועים אחרי ריסטארט
**פתרון**:
1. בדוק שה-SERVICE_ROLE=api מוגדר ב-API service
2. וודא שה-cleanup רץ בהפעלה (חפש "Running outbound cleanup")
3. אם צריך, הרץ ידנית: POST `/api/outbound/cleanup-stuck-jobs`

## ביטול שיחות (Cancel)

הפונקציונליות כבר קיימת ועובדת:

**Soft Cancel** - בקשת ביטול (Worker יעצור בקרוב):
```http
POST /api/outbound_calls/jobs/{job_id}/cancel
```

**Force Cancel** - ביטול מיידי (גם אם Worker מת):
```http
POST /api/outbound_calls/jobs/{job_id}/force-cancel
```

## קבצים ששונו

1. `server/routes_outbound.py` - הסרת Thread, שימוש ב-RQ
2. `server/app_factory.py` - תיקון זמני cleanup והקשר
3. `server/logging_config.py` - שיפור לוגים ל-DEBUG mode
4. `docker-compose.yml` - כבר מוגדר נכון (אין צורך בשינוי)

## סיכום אבטחה

אין פגיעות אבטחה חדשות:
- RQ worker enqueue הוא פנימי (לא חשוף למשתמשים)
- Cleanup עדיין שומר על בידוד עסקים
- לא נוספו endpoints חיצוניים
- כל בדיקות האבטחה הקיימות נשארות במקום

## תמיכה

אם יש בעיות:
1. בדוק לוגים: `docker compose logs -f`
2. בדוק משתני סביבה ב-`.env`
3. וודא ש-Redis רץ: `docker compose ps redis`
4. בדוק healthcheck: `curl http://localhost/api/health`
