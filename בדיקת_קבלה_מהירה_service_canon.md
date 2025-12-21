# בדיקת קבלה מהירה - קנוניזציה ומיפוי topic ל-service

## לוגים צפויים (3 לוגים קריטיים)

### בשיחה תקינה עם "פריצת מנעול" תראה:

```
[OFFLINE_STT] ✅ Saved final_transcript (1234 chars) for CAxxxxx

[SERVICE_CANON] ✅ raw='פריצת מנעול' -> canon='מנעולן' (exact match)
[OFFLINE_EXTRACT] ✅ Updated lead 123 service_type: 'פריצת מנעול' → 'מנעולן'

[TOPIC_CLASSIFY] 🚀 enabled for business 1 | threshold=0.78 | top_k=3
[TOPIC_CLASSIFY] Running classification for call CAxxxxx | source=final_transcript (from recording) | length=1234 chars
[TOPIC_CLASSIFY] ✅ LAYER 1 (keyword) matched in 15ms
[TOPIC_CLASSIFY] ✅ Detected topic: 'locksmith_emergency' (confidence=0.950, method=keyword)
[TOPIC_CLASSIFY] ✅ Tagged call CAxxxxx with topic 45
[TOPIC_CLASSIFY] ✅ Tagged lead 123 with topic 45

[TOPIC→SERVICE] ✅ enabled=True topic.canon='מנעולן' conf=0.950>=0.75 override=True old='מנעולן' new='מנעולן' reason=service_type is empty

[WEBHOOK] ✅ Webhook queued for call CAxxxxx (direction=inbound)
```

### אם אין keyword match - יראה embedding:

```
[TOPIC_CLASSIFY] 🚀 enabled for business 1 | threshold=0.78 | top_k=3
[TOPIC_CLASSIFY] Running classification for call CAxxxxx | source=final_transcript (from recording) | length=1456 chars
📭 No keyword match, trying embeddings (Layer 2)...
🔢 Generated 1 topic embeddings in 250ms
[TOPIC_CLASSIFY] ✅ Detected topic: 'locksmith_general' (confidence=0.830, method=embedding)
[TOPIC→SERVICE] ✅ enabled=True topic.canon='מנעולן' conf=0.830>=0.75 override=True old='None' new='מנעולן' reason=service_type is empty
```

## 5 נקודות קריטיות - ✅ Checklist

### ✅ 1. סדר פעולות נכון
```
1. Whisper transcription → final_transcript
2. LLM extraction → "פריצת מנעול"
3. canonicalize_service() → "מנעולן"
4. Save to lead.service_type
5. Topic classification (uses final_transcript)
6. Topic→Service mapping (if enabled)
```

**איך לבדוק**: חפש בלוגים את הסדר הזה. `[SERVICE_CANON]` צריך להופיע **לפני** `[TOPIC_CLASSIFY]`.

### ✅ 2. לא לדרוס ערך "טוב" שכבר נקבע
**הקוד בודק 3 תנאים לפני override**:

```python
should_override = (
    not lead.service_type OR                           # ריק
    not is_canonical_service(lead.service_type) OR     # לא קאנוני
    (confidence >= 0.85 AND value_is_different)        # ביטחון גבוה מאוד
)
```

**איך לבדוק**: 
```sql
-- יצור lead עם service_type='מנעולן' (קאנוני)
INSERT INTO leads (tenant_id, phone_e164, service_type) 
VALUES (1, '+972501234567', 'מנעולן');

-- הרץ שיחה עם topic שמנסה להמיר ל-'חשמלאי' (confidence < 0.85)
-- צפוי: [TOPIC→SERVICE] override=False reason=service_type 'מנעולן' is already canonical
```

### ✅ 3. לוודא שיש canonical_service_type על ה-topic

**בדיקה ב-DB**:
```sql
-- בדוק אילו topics יש להם mapping
SELECT id, name, canonical_service_type, is_active
FROM business_topics
WHERE business_id = 1 AND canonical_service_type IS NOT NULL;
```

**אם התוצאה ריקה** → אין מיפויים! צריך להוסיף:
```sql
UPDATE business_topics 
SET canonical_service_type = 'מנעולן' 
WHERE business_id = 1 
  AND name IN ('locksmith_emergency', 'locksmith_general', 'door_break_in');
```

**לוג צפוי אם אין mapping**:
```
[TOPIC→SERVICE] ℹ️ Topic 45 ('some_topic') has no canonical_service_type mapping
```

### ✅ 4. Migration 43 - defaults ו-nullability

**בדוק שה-migration רץ**:
```sql
-- בדוק שהעמודות קיימות
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'business_topics' 
  AND column_name = 'canonical_service_type';

SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'business_ai_settings' 
  AND column_name IN ('map_topic_to_service_type', 'service_type_min_confidence');
```

**תוצאה צפויה**:
```
canonical_service_type | character varying(255) | NULL
map_topic_to_service_type | boolean | false
service_type_min_confidence | double precision | 0.75
```

**אם העמודות לא קיימות** → הרץ migration:
```bash
python -m server.db_migrate
```

### ✅ 5. 3 לוגים קריטיים

**חייב להופיע בסדר הזה**:

#### A. SERVICE_CANON (מ-LLM extraction)
```
[SERVICE_CANON] ✅ raw='פריצת מנעול' -> canon='מנעולן' (exact match)
```

#### B. TOPIC_CLASSIFY (embedding/keyword)
```
[TOPIC_CLASSIFY] 🚀 enabled for business 1 | threshold=0.78 | top_k=3
[TOPIC_CLASSIFY] Running classification for call CAxxxxx | source=final_transcript (from recording) | length=1234 chars
[TOPIC_CLASSIFY] ✅ Detected topic: 'locksmith_emergency' (confidence=0.950, method=keyword)
```

#### C. TOPIC→SERVICE (mapping)
```
[TOPIC→SERVICE] ✅ enabled=True topic.canon='מנעולן' conf=0.950>=0.75 override=True old='מנעולן' new='מנעולן' reason=service_type is empty
```

**אם לא רואה את 3 הלוגים** → בעיה!

## בדיקות ספציפיות (5 דקות)

### בדיקה 1: שיחה עם "פריצת מנעול" → lead.service_type = "מנעולן"

**Setup**:
```sql
-- הפעל embedding + mapping
UPDATE business_ai_settings 
SET embedding_enabled = TRUE,
    map_topic_to_service_type = TRUE,
    service_type_min_confidence = 0.75
WHERE business_id = 1;

-- הגדר topic mapping
UPDATE business_topics 
SET canonical_service_type = 'מנעולן' 
WHERE business_id = 1 AND name = 'locksmith_emergency';
```

**פעולה**: עשה שיחה שמזכירה "פריצת מנעול"

**תוצאה צפויה**:
```sql
SELECT service_type FROM leads WHERE id = [lead_id];
-- צריך להיות: מנעולן
```

**לוג צפוי**:
```
[SERVICE_CANON] ✅ raw='פריצת מנעול' -> canon='מנעולן'
[TOPIC_CLASSIFY] ✅ Detected topic: 'locksmith_emergency' (confidence=0.950, method=keyword)
[TOPIC→SERVICE] ✅ enabled=True ... override=True old='None' new='מנעולן'
```

### בדיקה 2: confidence נמוך → אסור override

**Setup**:
```sql
UPDATE business_ai_settings 
SET service_type_min_confidence = 0.90  -- גבוה מאוד
WHERE business_id = 1;
```

**פעולה**: עשה שיחה עם טקסט מעורפל/רעש

**תוצאה צפויה**: אם confidence < 0.90 → לא יעדכן service_type

**לוג צפוי**:
```
[TOPIC_CLASSIFY] ✅ Detected topic: '...' (confidence=0.750, method=embedding)
[TOPIC→SERVICE] ℹ️ Confidence 0.750 below threshold 0.900 for service_type mapping
```

### בדיקה 3: שינוי threshold משפיע

**Setup**:
```sql
-- נסה עם threshold נמוך
UPDATE business_ai_settings 
SET service_type_min_confidence = 0.50
WHERE business_id = 1;
```

**פעולה**: אותה שיחה מבדיקה 2

**תוצאה צפויה**: עכשיו confidence=0.75 **יעדכן** כי 0.75 > 0.50

**לוג צפוי**:
```
[TOPIC→SERVICE] ✅ enabled=True ... conf=0.750>=0.50 override=True ...
```

## דגלים חשובים להפעלה

### הפעל classification:
```sql
UPDATE business_ai_settings 
SET embedding_enabled = TRUE
WHERE business_id = 1;
```

### הפעל topic→service mapping:
```sql
UPDATE business_ai_settings 
SET map_topic_to_service_type = TRUE,
    service_type_min_confidence = 0.75
WHERE business_id = 1;
```

### בדוק שההגדרות נשמרו:
```sql
SELECT embedding_enabled, 
       map_topic_to_service_type, 
       service_type_min_confidence,
       embedding_threshold
FROM business_ai_settings 
WHERE business_id = 1;
```

**תוצאה צפויה**:
```
embedding_enabled: true
map_topic_to_service_type: true
service_type_min_confidence: 0.75
embedding_threshold: 0.78
```

## מה המערכת תשתמש - הבהרה

### טקסט ל-classification:
**עדיפות**:
1. `final_transcript` (Whisper מההקלטה) - **גבוה ביותר**
2. `transcription` (Google STT realtime) - fallback

**לוג שמראה מה נשלח**:
```
[TOPIC_CLASSIFY] Running classification for call CAxxxxx | source=final_transcript (from recording) | length=1234 chars
```

### שיטת classification:
**2 שכבות**:
1. **LAYER 1**: מילות מפתח + סינונימים (מהיר, חינמי, מדויק)
   - בודק אם שם ה-topic מופיע בטקסט
   - בודק synonyms
   - בודק multi-keyword match
2. **LAYER 2**: Embeddings (הבנת הקשר סמנטית)
   - רק אם LAYER 1 לא מצא
   - משתמש ב-OpenAI embeddings
   - cosine similarity

**לוג LAYER 1**:
```
[TOPIC_CLASSIFY] ✅ LAYER 1 (keyword) matched in 15ms
✅ LAYER 1 SUCCESS | method=keyword | topic='locksmith_emergency' | score=0.950
```

**לוג LAYER 2**:
```
📭 No keyword match, trying embeddings (Layer 2)...
🔢 Generated 1 topic embeddings in 250ms
[TOPIC_CLASSIFY] ✅ LAYER 2 SUCCESS | method=embedding | topic='locksmith_general' | score=0.830
```

## תיקון בעיות נפוצות

### בעיה: לא רואה [SERVICE_CANON]
**סיבה**: LLM לא חילץ service_category
**פתרון**: בדוק שהסיכום מזכיר שירות, שפר prompt

### בעיה: לא רואה [TOPIC_CLASSIFY]
**סיבה**: embedding_enabled = FALSE
**פתרון**: 
```sql
UPDATE business_ai_settings SET embedding_enabled = TRUE WHERE business_id = 1;
```

### בעיה: לא רואה [TOPIC→SERVICE]
**סיבות אפשריות**:
1. `map_topic_to_service_type = FALSE` → הפעל
2. confidence < threshold → הורד threshold
3. topic אין לו canonical_service_type → הוסף mapping
4. service_type כבר קאנוני → זה OK! (לא צריך override)

### בעיה: source=transcription (realtime) במקום final_transcript
**סיבה**: final_transcript לא נשמר או ריק
**פתרון**: בדוק שההקלטה תקינה והתמלול הצליח
```sql
SELECT call_sid, 
       LENGTH(final_transcript) as ft_len,
       LENGTH(transcription) as tr_len,
       transcript_source
FROM call_log 
WHERE call_sid = 'CAxxxxx';
```

## סיכום - לוגים מושלמים

```
=== TRANSCRIPTION ===
[OFFLINE_STT] ✅ Saved final_transcript (1234 chars) for CAxxxxx

=== LLM EXTRACTION + CANONICALIZATION ===
[OFFLINE_EXTRACT] ✅ Extracted from summary: city='תל אביב', service='פריצת מנעול', conf=0.92
[SERVICE_CANON] ✅ raw='פריצת מנעול' -> canon='מנעולן' (exact match)
[OFFLINE_EXTRACT] ✅ Updated lead 123 service_type: 'פריצת מנעול' → 'מנעולן'

=== TOPIC CLASSIFICATION ===
[TOPIC_CLASSIFY] 🚀 enabled for business 1 | threshold=0.78 | top_k=3
[TOPIC_CLASSIFY] Running classification for call CAxxxxx | source=final_transcript (from recording) | length=1234 chars
✅ LAYER 1 (keyword) matched in 15ms
[TOPIC_CLASSIFY] ✅ Detected topic: 'locksmith_emergency' (confidence=0.950, method=keyword)
[TOPIC_CLASSIFY] ✅ Tagged call CAxxxxx with topic 45
[TOPIC_CLASSIFY] ✅ Tagged lead 123 with topic 45

=== TOPIC→SERVICE MAPPING ===
[TOPIC→SERVICE] ✅ enabled=True topic.canon='מנעולן' conf=0.950>=0.75 override=True old='מנעולן' new='מנעולן' reason=service_type is empty

=== WEBHOOK ===
[WEBHOOK] ✅ Webhook queued for call CAxxxxx (direction=inbound)
```

**אם רואים את כל הלוגים האלה בסדר הזה → המערכת עובדת מושלם! ✅**
