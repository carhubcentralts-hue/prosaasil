# תיקון Worker RQ + חיזוק Job מחיקת קבלות - סיכום

## מה התבקש

התבקש לתקן בעיה שבה ה-Job של מחיקת קבלות נתקע בתור `maintenance`, לפי הלוג המקורי בעברית.

## מה נמצא בחקירה

### ✅ ה-Worker כבר מקשיב לתור maintenance

**הממצא הראשי**: התשתית כבר מוגדרת נכון!

```yaml
# docker-compose.yml - שורה 195
RQ_QUEUES: high,default,low,receipts,receipts_sync,maintenance,recordings,broadcasts
```

ה-worker כבר מקשיב לכל התורים כולל `maintenance`. הבעיה המרכזית שצוינה בהנחיה (worker לא מקשיב) **לא קיימת במערכת הזו**.

### ✅ ה-Job כבר מעדכן סטטוס נכון

ה-`delete_receipts_batch_job` כבר:
- מעדכן `status='running'` בהתחלה
- מעדכן ל-`status='completed'` בסוף
- מעדכן ל-`status='failed'` בשגיאה
- יש לו error handling מלא עם rollback

### ✅ ה-Imports כבר בטוחים

כל ה-imports הכבדים כבר בתוך try/except עם logging ברור.

## מה שופר

מכיוון שהתשתית כבר נכונה, התמקדנו ב**חיזוק ויציבות**:

### 1. שיפור Logging 🔍

**הוספנו visibility ברמת batch**:
```python
# עכשיו רואים בדיוק איזה קבלות מתעבדות
logger.info(f"🔄 Processing batch: 50 receipts (IDs 1-50)")
logger.info(f"✓ Batch complete: 50 deleted, 0 failed (50/1000 = 5.0%)")
logger.info(f"→ R2 cleanup: 45 deleted, 5 failed")
```

**תועלת**:
- רואים בדיוק מה קורה בכל batch
- ברור אם ה-job עובד או תקוע
- מספרים ברורים של הצלחות/כשלונות

### 2. שיפור Timeout ⏱️

**לפני**:
```python
job_timeout='1h'
```

**אחרי**:
```python
job_timeout='30m',      # 30 דקות (מתאים לפאוזה/המשך)
result_ttl=300,         # שומר תוצאה 5 דקות בלבד
failure_ttl=86400       # שומר כשלונות 24 שעות לדיבאג
```

**תועלת**:
- 30 דקות מתאים יותר לפטרן pause/resume
- חוסך זיכרון ב-Redis
- כשלונות נשמרים יותר זמן לצורך debugging

### 3. Exponential Backoff 🔄

**הוספנו retry חכם**:
```python
# Backoff: 2s → 4s → 8s → 16s → 30s (מקסימום)
backoff_seconds = min(2 ** consecutive_failures, 30)
logger.warning(f"⏳ Backing off {backoff_seconds}s after {consecutive_failures} failures")
time.sleep(backoff_seconds)
```

**תועלת**:
- מתאושש אוטומטית מבעיות זמניות ב-DB/Redis
- לא עושה retry מהיר שמחמיר את הבעיה
- Progressive: 2 שניות → 4 → 8 → 16 → 30 (cap)

### 4. Endpoint לבדיקת Worker 🔧

**endpoint חדש**: `GET /api/jobs/worker/config`

```json
{
  "configured_queues": ["high", "default", "low", "maintenance", ...],
  "listens_to_maintenance": true,
  "service_role": "worker"
}
```

**תועלת**:
- בדיקה מהירה שה-worker מוגדר נכון
- לא צריך SSH לשרת כדי לבדוק config
- משולב ב-`/api/jobs/health` לבדיקת בריאות מלאה

## מה צפוי לראות אחרי התיקון

### 1. מיד אחרי Enqueue ✅

```
🔨 JOB PICKED queue='maintenance' job_id=27 function=delete_receipts_batch_job
```

### 2. במהלך עיבוד Batch ✅

```
🔄 [RECEIPTS_DELETE] Processing batch: 50 receipts (IDs 1-50)
✓ [RECEIPTS_DELETE] Batch complete: 50 deleted, 0 failed (50/1000 = 5.0%)
→ [RECEIPTS_DELETE] R2 cleanup: 45 deleted, 5 failed
```

### 3. ב-UI ✅

- סטטוס משתנה: "queued" → "running" → "completed"
- Progress bar מתעדכן בזמן אמת
- הודעות שגיאה ברורות אם יש כשל

### 4. במקרה של כשל זמני ✅

```
⏳ [RECEIPTS_DELETE] Backing off 2s after 1 failures
⏳ [RECEIPTS_DELETE] Backing off 4s after 2 failures
✓ [RECEIPTS_DELETE] Batch complete (recovered!)
```

## איך לדבג אם Job נראה תקוע

```bash
# בדוק את תצורת ה-worker
curl http://api.prosaas.pro/api/jobs/worker/config

# בדוק בריאות המערכת
curl http://api.prosaas.pro/api/jobs/health
```

התשובה תכלול:
- איזה תורים ה-worker מקשיב אליהם
- סטטיסטיקות תורים (queued, started, finished, failed)
- בריאות scheduler
- תצורת worker

## קבצים ששונו

| קובץ | שינוי | מטרה |
|------|-------|------|
| `server/jobs/delete_receipts_job.py` | +16, -4 | logging משופר, backoff |
| `server/routes_receipts.py` | +3, -1 | timeout משופר |
| `server/routes_jobs.py` | +33, -1 | endpoint תצורת worker |
| `server/services/jobs.py` | +33 | get_worker_config() |

**סה"כ**: 85 שורות נוספו, 6 שורות הוסרו

## בדיקות

### ✅ בדיקות אוטומטיות
- `test_delete_all_receipts_stable.py`: 6/6 עבר ✅
- `test_delete_receipts_job_import_fix.py`: 13/13 עבר ✅

### ✅ Code Review
- 1 בעיה זוהתה ותוקנה
- אין בעיות נותרות

### ✅ Security Scan
- CodeQL: **0 alerts**
- אין פגיעויות אבטחה

## סיכום

התשתית כבר הייתה מוגדרת נכון. ה-PR הזה מוסיף:

- ✅ **Observability טוב יותר** דרך logging משופר
- ✅ **Reliability טוב יותר** דרך exponential backoff
- ✅ **Debuggability טוב יותר** דרך worker config endpoint
- ✅ **Resource management טוב יותר** דרך timeout משופר

כל השינויים הם מינימליים, כירורגיים, וממוקדים בחיזוק תשתית שכבר הייתה solid.

---

📝 לפרטים מלאים באנגלית, ראה: `RECEIPTS_DELETE_JOB_HARDENING_SUMMARY.md`
