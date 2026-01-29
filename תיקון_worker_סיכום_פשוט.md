# תיקון Worker Maintenance - סיכום סופי פשוט

## מה עשינו

**שינוי אחד פשוט**: הוספנו logging ברור ב-`server/worker.py` שמראה האם ה-worker מקשיב ל-`maintenance` או לא.

## הקוד החדש

```python
logger.info(f"📍 CRITICAL: Worker WILL process jobs from 'maintenance' queue: {'maintenance' in LISTEN_QUEUES}")
if 'maintenance' not in LISTEN_QUEUES:
    logger.error("❌❌❌ CRITICAL ERROR: 'maintenance' NOT IN QUEUE LIST!")
    logger.error("❌ This means delete_receipts and other maintenance jobs will NEVER run!")
```

## מה זה נותן

עכשיו כשה-worker מתחיל, הוא יגיד **בפירוש**:
- ✅ `Worker WILL process jobs from 'maintenance' queue: True` → הכל טוב!
- ❌ `Worker WILL process jobs from 'maintenance' queue: False` → יש בעיה!

## הקונפיג (כבר נכון!)

```yaml
# docker-compose.yml
RQ_QUEUES: high,default,low,receipts,receipts_sync,maintenance,recordings,broadcasts
```

ה-`maintenance` **כבר בתוך הרשימה**.

## איך לבדוק שזה עובד

### 1. הרץ את ה-worker

```bash
docker-compose up worker
```

או אם רץ כבר:

```bash
docker-compose logs worker | grep "CRITICAL.*maintenance"
```

### 2. חפש את השורה הזו בלוג

```
📍 CRITICAL: Worker WILL process jobs from 'maintenance' queue: True
```

אם רואים **True** → הכל בסדר!

### 3. נסה להריץ delete_all

```bash
curl -X POST http://localhost:5000/api/receipts/delete_all \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4. בדוק שה-worker תפס את ה-job

חפש בלוג:

```
🔨 JOB PICKED: queue=maintenance function=delete_receipts_batch_job job_id=27
🧾 JOB start type=delete_receipts business_id=123 job_id=27
```

## אם זה עדיין לא עובד

יש רק 3 אפשרויות:

### אפשרות 1: ה-worker לא רץ בכלל
```bash
docker-compose ps | grep worker
```

אם לא רואים worker → תריץ:
```bash
docker-compose up -d worker
```

### אפשרות 2: יש שגיאה בהפעלת ה-worker
```bash
docker-compose logs worker | tail -50
```

חפש שגיאות אדומות.

### אפשרות 3: ה-RQ_QUEUES לא נטען נכון
```bash
docker-compose exec worker env | grep RQ_QUEUES
```

צריך לראות:
```
RQ_QUEUES=high,default,low,receipts,receipts_sync,maintenance,recordings,broadcasts
```

## סיכום

- ✅ הקוד תקין
- ✅ הקונפיג תקין
- ✅ הלוגים עכשיו ברורים

אם זה עדיין לא עובד, הבעיה היא **לא בקוד אלא בהרצה** - צריך לבדוק שה-worker באמת רץ ושולף את המשתנה RQ_QUEUES.
