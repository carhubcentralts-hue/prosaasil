# תיקון: קנוניזציה של service_type ומיפוי מ-topic לשירות

## סיכום התיקון

### בעיות שנפתרו:

1. **"דריסה" של service_type עם ערכים גולמיים מה-LLM** ✅
   - לפני: "פריצת מנעול", "פריצת דלת", "החלפת צילינדר" - כל אחד ערך שונה
   - אחרי: כולם → "מנעולן" (קאנוני)

2. **embedding לא קבע service_type** ✅
   - לפני: topic classification רק קבע `detected_topic_id`
   - אחרי: יכול גם לקבוע `service_type` לפי mapping

3. **תמלול לא מוצג נכון** ✅
   - בדיקה הראתה שהקוד **כבר עובד נכון**!
   - `final_transcript` (מהקלטה) בעדיפות ראשונה
   - נשלח גם ב-webhook

## מה השתנה?

### 1. פונקציית קנוניזציה (lead_extraction_service.py)

```python
def canonicalize_service(service_category: str, business_id: int = None):
    """
    מנרמל קטגוריות שירות לקאנוניות.
    
    דוגמאות:
    - "פריצת מנעול" → "מנעולן"  
    - "פריצת דלת" → "מנעולן"
    - "תיקון חשמל" → "חשמלאי"
    """
```

**מפת המרה**:
```python
SERVICE_CANONICALIZATION_MAP = {
    "פריצת מנעול": "מנעולן",
    "פריצת דלת": "מנעולן",
    "החלפת צילינדר": "מנעולן",
    "תיקון מנעול": "מנעולן",
    "פורץ מנעולים": "מנעולן",
    
    "תיקון חשמל": "חשמלאי",
    "התקנת גוף תאורה": "חשמלאי",
    
    "תיקון צינור": "שרברב",
    "אינסטלטור": "שרברב",
}
```

### 2. שדות חדשים ב-DB (models_sql.py + db_migrate.py)

#### BusinessTopic
```sql
ALTER TABLE business_topics 
ADD COLUMN canonical_service_type VARCHAR(255);
```

**שימוש**: מיפוי topic ל-service_type
- Topic "locksmith" → `canonical_service_type = "מנעולן"`

#### BusinessAISettings
```sql
ALTER TABLE business_ai_settings 
ADD COLUMN map_topic_to_service_type BOOLEAN DEFAULT FALSE,
ADD COLUMN service_type_min_confidence FLOAT DEFAULT 0.75;
```

**הגדרות**:
- `map_topic_to_service_type`: הפעל מיפוי topic ל-service
- `service_type_min_confidence`: סף ביטחון מינימלי (ברירת מחדל 0.75)

### 3. אינטגרציה (tasks_recording.py)

#### A. מסלול חילוץ LLM

```python
if update_service:
    # 🔥 קנוניזציה לפני שמירה
    canonical_service = canonicalize_service(extracted_service, business_id)
    lead.service_type = canonical_service
    log.info(f"✅ Updated: '{extracted_service}' → '{canonical_service}'")
```

#### B. מסלול topic classification

```python
# אחרי שמזהים topic
if ai_settings.map_topic_to_service_type and confidence >= threshold:
    topic = BusinessTopic.query.get(topic_id)
    if topic and topic.canonical_service_type:
        # עדכן רק אם ריק או ביטחון גבוה
        if not lead.service_type or confidence >= 0.85:
            lead.service_type = topic.canonical_service_type
```

## איך זה עובד?

### זרימה מלאה של שיחה:

```
שיחה מסתיימת
    ↓
Whisper מתמלל (final_transcript) 
    ↓
┌─────────────┬──────────────┬─────────────────┐
│             │              │                 │
│  LLM חולץ   │   סיכום GPT  │  Topic          │
│  "פריצת מנעול"│             │  Classification │
│             │              │  "locksmith"    │
│             │              │  confidence=0.89│
↓             ↓              ↓                 │
canonicalize_service()                        │
"פריצת מנעול" → "מנעולן"                      │
    │                                          │
    │ ◄────────────────────────────────────────┘
    │
    ↓
עדכון lead.service_type = "מנעולן"
```

### עדיפויות עדכון service_type:

1. **Topic mapping** (אם מופעל + confidence ≥ סף)
2. **חילוץ LLM מקונן** (אם החילוץ הצליח)
3. **ערך קיים** (אם אין עדכונים)

## תנאים לעדכון service_type

### מחילוץ LLM:
- ליד **אין** `service_type` → עדכן תמיד
- ליד **יש** `service_type` + ביטחון חילוץ > 0.8 → דרוס

### מ-topic classification:
1. **מיפוי מופעל** (`map_topic_to_service_type = TRUE`)
2. **סף ביטחון** (confidence ≥ `service_type_min_confidence`)
3. **ל-topic יש mapping** (`canonical_service_type` לא NULL)
4. **תנאי ליד**: ריק **או** confidence ≥ 0.85

## הגדרת המערכת

### 1. הרצת Migration

```bash
python -m server.db_migrate
```

זה מוסיף את השדות החדשים אוטומטית.

### 2. הפעלת מיפוי topic ל-service

```sql
UPDATE business_ai_settings 
SET map_topic_to_service_type = TRUE,
    service_type_min_confidence = 0.75
WHERE business_id = 1;
```

### 3. הגדרת mappings ל-topics

```sql
-- מנעולן
UPDATE business_topics 
SET canonical_service_type = 'מנעולן' 
WHERE business_id = 1 
  AND name IN ('פורץ מנעולים', 'locksmith_emergency', 'door_break_in');

-- חשמלאי
UPDATE business_topics 
SET canonical_service_type = 'חשמלאי' 
WHERE business_id = 1 
  AND name IN ('electrical_issue', 'power_fault');

-- שרברב
UPDATE business_topics 
SET canonical_service_type = 'שרברב' 
WHERE business_id = 1 
  AND name IN ('plumber', 'water_leak');
```

## בדיקות

### 1. לוגים צפויים אחרי שיחה:

```
[OFFLINE_STT] ✅ Saved final_transcript (1234 chars) for CAxxxxx
[OFFLINE_EXTRACT] ✅ Extracted from summary: city='תל אביב', service='פריצת מנעול', conf=0.92
[CANONICALIZE] 'פריצת מנעול' → 'מנעולן' (exact match)
[OFFLINE_EXTRACT] ✅ Updated lead 123 service_type: 'פריצת מנעול' → 'מנעולן'

[TOPIC_CLASSIFY] enabled, threshold=0.78, top_k=3
[TOPIC_CLASSIFY] ✅ LAYER 1 (keyword) matched in 15ms
[TOPIC_CLASSIFY] ✅ Detected topic: 'locksmith_emergency' (confidence=0.950, method=keyword)
[TOPIC_CLASSIFY] ✅ Tagged call CAxxxxx with topic 45
[TOPIC_CLASSIFY] ✅ Tagged lead 123 with topic 45
[TOPIC_CLASSIFY] ✅ Mapped topic 'locksmith_emergency' to service_type: 'מנעולן' → 'מנעולן' (confidence=0.950)

[WEBHOOK] ✅ Webhook queued for call CAxxxxx (direction=inbound)
```

### 2. בדיקת DB:

```sql
-- בדוק שה-leads קיבלו service_type קאנוני
SELECT id, service_type, detected_topic_id, detected_topic_confidence
FROM leads
WHERE service_type = 'מנעולן'
ORDER BY id DESC
LIMIT 10;

-- בדוק mappings של topics
SELECT id, name, canonical_service_type, is_active
FROM business_topics
WHERE business_id = 1 AND canonical_service_type IS NOT NULL;

-- בדוק שתמלול נשמר
SELECT call_sid, 
       LENGTH(final_transcript) as transcript_len,
       LENGTH(summary) as summary_len,
       extracted_service,
       transcript_source
FROM call_log
WHERE final_transcript IS NOT NULL
ORDER BY created_at DESC
LIMIT 5;
```

## תמלול וסיכום - לא שונה דבר! ✅

הקוד שמציג תמלול וסיכום **לא שונה** והמשיך לעבוד נכון:

### 1. API מחזיר תמלול (`server/routes_calls.py`):
```python
# עדיפות: final_transcript > transcription
best_transcript = getattr(call, 'final_transcript', None) or call.transcription
```

### 2. Webhook שולח תמלול (`server/tasks_recording.py`):
```python
transcript=final_transcript or transcription or "",
summary=summary or "",
```

### 3. שמירה ב-DB:
- `call_log.final_transcript` - תמלול Whisper מהקלטה (איכות גבוהה)
- `call_log.transcription` - תמלול realtime Google STT (fallback)
- `call_log.summary` - סיכום AI

### לוגים שמוודאים שמירה:
```
[OFFLINE_STT] ✅ Saved final_transcript (1234 chars) for CAxxxxx
[BUILD 342] ✅ Recording metadata: bytes=524288, duration=45.2s, source=recording
```

## יתרונות

1. ✅ **עקביות**: כל שירותי מנעולן → "מנעולן"
2. ✅ **גמישות**: שירותים חדשים ללא mapping נשמרים כמו שהם
3. ✅ **הגדרות לכל עסק**: כל business יכול להגדיר mappings משלו
4. ✅ **2 מקורות**: גם LLM וגם embeddings יכולים לקבוע service_type
5. ✅ **בטוח**: סף ביטחון מונע עדכונים שגויים
6. ✅ **ניפוי באגים**: לוגים מפורטים בכל שלב
7. ✅ **ללא breaking changes**: תצוגת תמלול/סיכום לא השתנתה

## נקודות חשובות

### האם צריך להגדיר mappings ידנית?
**כן**, אבל רק אם רוצים שגם topic classification יקבע service_type.
- חילוץ LLM + קנוניזציה עובד **אוטומטית** עם ה-`SERVICE_CANONICALIZATION_MAP`
- topic mapping דורש **הגדרה ידנית** ב-DB (ראה למעלה)

### מה קורה אם אין mapping?
- **חילוץ LLM**: מחזיר את הערך המקורי (לא דורס)
- **Topic**: לא מעדכן service_type (רק detected_topic_id)

### איך להוסיף mapping חדש?
**אופציה 1: עדכן קוד** (למיפוי גלובלי)
```python
# בקובץ lead_extraction_service.py
SERVICE_CANONICALIZATION_MAP = {
    # ... mappings קיימים
    "שירות חדש": "קטגוריה קאנונית",
}
```

**אופציה 2: עדכן DB** (למיפוי topic ספציפי)
```sql
UPDATE business_topics 
SET canonical_service_type = 'קטגוריה קאנונית' 
WHERE id = [topic_id];
```

## בעיות אפשריות ופתרונות

### בעיה: service_type לא מתעדכן
**בדוק**:
1. הלוגים מראים קנוניזציה? `[CANONICALIZE]`
2. התנאים מתקיימים? (ליד ריק או confidence > 0.8)
3. mapping קיים ב-DB?

### בעיה: topic לא מעדכן service_type
**בדוק**:
1. `map_topic_to_service_type = TRUE`?
2. confidence ≥ `service_type_min_confidence`?
3. `topic.canonical_service_type` מוגדר?
4. הלוגים מראים `[TOPIC_CLASSIFY] ✅ Mapped topic`?

### בעיה: תמלול לא מוצג
**לא אמור לקרות** - הקוד לא שונה!
אבל אם כן:
1. בדוק `call_log.final_transcript` ב-DB
2. בדוק הלוגים: `[OFFLINE_STT] ✅ Saved final_transcript`
3. בדוק שההקלטה קיימת והתמלול הצליח

## סיכום

התיקון מוסיף שכבת נרמול לפני שמירת `lead.service_type`:
1. **LLM חולץ** → **קנוניזציה** → **שמירה לליד**
2. **Topic מזוהה** → **mapping (אם מוגדר)** → **עדכון service_type**

כל השינויים **אחורה-תואמים** - אין breaking changes. התמלול והסיכום ממשיכים לעבוד בדיוק כמו קודם.
