# תיקון בעיית "idle in transaction" שחוסמת מיגרציות

## סיכום הבעיה

חיבורי PostgreSQL שתקועים במצב "idle in transaction" מחזיקים locks וחוסמים פעולות DDL (כמו CREATE TABLE), וגורמים למיגרציות להיכשל עם שגיאת `lock_timeout`.

## הפתרון שיושם

### 1. תוקן `check_constraint_exists()`

נוספה פונקציה חדשה שמשתמשת ב-`engine.connect()` במקום `db.session`:

```python
def check_constraint_exists(constraint_name):
    """Check if constraint exists using independent connection"""
    with db.engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 1 FROM pg_constraint 
            WHERE conname = :constraint_name
            LIMIT 1
        """), {"constraint_name": constraint_name})
        return result.fetchone() is not None
```

### 2. נוספה `terminate_idle_in_tx()`

פונקציה שהורגת connections ישנים במצב idle-in-transaction:

```python
def terminate_idle_in_tx(engine, older_than_seconds=30):
    """הורג connections במצב idle-in-transaction ישנים מ-30 שניות"""
    sql = """
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE state = 'idle in transaction'
      AND now() - xact_start > (INTERVAL '1 second' * :secs)
      AND pid <> pg_backend_pid()
    """
    with engine.connect() as conn:
        result = conn.execute(text(sql), {"secs": older_than_seconds})
        # ...
```

### 3. עודכן `exec_ddl()`

הפונקציה עכשיו:
1. **בודקת** כמה connections במצב idle-in-transaction קיימים
2. **רושמת ללוג** את הכמות אם יש כאלה
3. **הורגת** connections ישנים (מעל 30 שניות)
4. **מריצה** את ה-DDL עם timeouts מחמירים

```python
def exec_ddl(engine, sql: str):
    # בודק ורושם כמה idle-in-transaction connections יש
    with engine.connect() as conn:
        result = conn.execute(text("SELECT count(*) FROM pg_stat_activity WHERE state='idle in transaction'"))
        idle_count = result.scalar()
        if idle_count > 0:
            log.warning(f"Found {idle_count} idle-in-transaction connection(s) before DDL")
            terminate_idle_in_tx(engine, 30)
    
    # מריץ DDL עם timeouts...
```

### 4. תוקנה מיגרציה 113

הוחלף `db.session.execute()` ב-`check_constraint_exists()`:

```python
# קוד ישן (שבור)
constraint_check = db.session.execute(text("""
    SELECT 1 FROM pg_constraint 
    WHERE conname='unique_run_lead'
""")).fetchone()

# קוד חדש (תוקן)
if not check_constraint_exists('unique_run_lead'):
    # ... המשך המיגרציה
```

### 5. סקריפט הפריסה

ה-`scripts/deploy_production.sh` כבר כולל את הלוגיקה הנכונה:

```bash
# עוצר שירותים שמחזיקים חיבורי DB
docker compose stop prosaas-api worker scheduler

# מריץ מיגרציות (עם ניקוי אוטומטי של idle-tx)
docker compose run --rm migrate
```

## יתרונות

1. ✅ **אין יותר חסימות**: פונקציות בדיקה לא משאירות טרנזקציות פתוחות
2. ✅ **ניקוי אוטומטי**: טרנזקציות ישנות נהרגות אוטומטית לפני DDL
3. ✅ **לוגים ברורים**: הלוגים מראים מתי נמצאו ונהרגו טרנזקציות
4. ✅ **כישלון מהיר**: פעולות DDL עדיין נכשלות מהר (5s timeout) אם יש בעיות
5. ✅ **בטוח לפרודקשן**: סקריפט פריסה עוצר שירותים לפני מיגרציות

## ווידוא

הרץ את סקריפט הווידוא:

```bash
python verify_idle_transaction_fix.py
```

תוצאה צפויה:
```
================================================================================
Results: 9 passed, 0 failed
================================================================================
```

## פריסה

### פריסה רגילה

```bash
./scripts/deploy_production.sh
```

זה יעשה:
1. יעצור API, worker, scheduler
2. ירוץ מיגרציות (עם ניקוי אוטומטי של idle-tx)
3. יפעיל את כל השירותים

### רק מיגרציות

```bash
./scripts/deploy_production.sh --migrate-only
```

### עם ניקוי ידני של idle transactions

```bash
./scripts/deploy_production.sh --kill-idle-tx
```

## קריטריוני קבלה

- [x] אין יותר שגיאות "Blocking PID ... idle in transaction"
- [x] מיגרציה 115 CREATE TABLE business_calendars עובדת מיד
- [x] מיגרציות ניתנות להרצה מספר פעמים בלי לתקוע
- [x] כל פונקציות ה-check_* משתמשות ב-engine.connect()
- [x] exec_ddl() הורג idle transactions ישנים לפני DDL
- [x] סקריפט הפריסה עוצר שירותים לפני מיגרציות

## קבצים רלוונטיים

- `server/db_migrate.py` - קובץ המיגרציות הראשי עם התיקונים
- `scripts/deploy_production.sh` - סקריפט פריסה לפרודקשן
- `scripts/kill_idle_transactions.py` - ניקוי ידני של idle transactions
- `verify_idle_transaction_fix.py` - סקריפט ווידוא
- `IDLE_TRANSACTION_FIX_README.md` - תיעוד מפורט באנגלית

## למה זה קרה?

הבעיה הייתה שמיגרציה 113 השתמשה ב-`db.session.execute()` כדי לבדוק אם constraint קיים:

```python
# זה השאיר את החיבור במצב "idle in transaction"
constraint_check = db.session.execute(text("""
    SELECT 1 FROM pg_constraint WHERE conname='unique_run_lead'
""")).fetchone()
```

כשהחיבור נשאר פתוח בתוך טרנזקציה, הוא מחזיק locks ומפיל כל DDL שמנסה לגעת באותן טבלאות.

## הפתרון בקצרה

1. **שימוש ב-engine.connect()** - לא משאיר טרנזקציות פתוחות
2. **הרג טרנזקציות ישנות** - לפני כל DDL
3. **עצירת שירותים** - בזמן מיגרציות (כבר היה)
4. **לוגים ברורים** - מראה מה קורה

זה הכל! עכשיו המיגרציות אמורות לעבוד חלק ללא חסימות.
