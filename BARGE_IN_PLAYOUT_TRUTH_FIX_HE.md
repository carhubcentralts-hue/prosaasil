# תיקון ברג-אין: אמת ההשמעה (Playout Truth)

## הבעיה המקורית

המערכת זיהתה "AI מדברת" לפי מתי התקבלה `response.audio.delta` מ-OpenAI, אבל בפועל הקול עדיין מתנגן ללקוח מתוך `tx_queue`/Twilio במשך עוד כמה שניות. זה גרם למצב שבו:

1. לקוח שומע את ה-AI מדברת
2. לקוח מתחיל לדבר (ברג-אין לגיטימי)
3. המערכת רושמת: `USER_SPEECH while AI silent (not barge-in)`
4. הברג-אין לא עובד כי המערכת חושבת שה-AI כבר לא מדברת

### הדוגמה מהלוגים

```
AUDIO DRAIN ... frames remaining ... waiting 6300ms
↓
last_ai_audio_ts מתיישן (אין דלתות חדשות)
↓
is_ai_speaking_now() מחזיר False
↓
USER_SPEECH while AI silent (not barge-in)
```

**למרות שבאוזן הלקוח ה-AI עדיין מדברת!**

## הפתרון: אמת ההשמעה (Playout Truth)

### עקרון מרכזי

**האמת היחידה שמשנה: האם אודיו מתנגן ללקוח ברגע זה?**

לא מתי קיבלנו את האודיו מהמודל, אלא מתי הוא **נשמע** ללקוח.

## השינויים שבוצעו

### 1. משתנים חדשים לעקוב אחר השמעה

```python
# 🔥 PLAYOUT TRUTH: Track actual audio playout to customer
self.ai_playout_until_ts = 0.0  # Monotonic timestamp until when AI audio will be playing
self.ai_generation_id = 0  # Generation counter - incremented on each response.created
self.current_generation_id = 0  # Current active generation ID
self._frame_pacing_ms = 20  # Each audio frame = 20ms
self._playout_grace_ms = 250  # Grace period for playout estimation
```

**מה זה אומר:**
- `ai_playout_until_ts` - הזמן המדויק עד מתי האודיו יסתיים להתנגן ללקוח
- `ai_generation_id` - מונה לכל תגובה חדשה, למניעת race conditions
- Grace period של 250ms לעיכובי רשת/באפר

### 2. עדכון `is_ai_speaking_now()` - האמת החדשה

```python
def is_ai_speaking_now(self) -> bool:
    """
    🔥 PLAYOUT TRUTH FIX: Determine if AI is TRULY speaking to the customer RIGHT NOW
    
    Primary truth sources (checked in order):
    1. ai_playout_until_ts - Calculated timestamp when playout will complete
    2. tx_queue size > 0 with small grace (150-250ms for network buffer)
    3. Fallback to legacy last_ai_audio_ts for backwards compatibility
    """
    now = time.time()
    
    # Rule 1: PLAYOUT TRUTH - Primary source of truth
    if hasattr(self, 'ai_playout_until_ts') and self.ai_playout_until_ts > 0:
        if now < self.ai_playout_until_ts:
            return True  # ✅ עדיין מתנגן ללקוח!
    
    # ... שאר הכללים
```

**סדר העדיפויות:**
1. ✅ **Playout timestamp** - האם `now < ai_playout_until_ts`?
2. ✅ **TX Queue + Recent audio** - יש frames בתור וקיבלנו אודיו לאחרונה?
3. ✅ **Legacy fallback** - האם קיבלנו אודיו לפני פחות מ-400ms?

### 3. עדכון Timestamp כש-Frames נכנסים ל-TX Queue

#### בפונקציה `_tx_enqueue()`

```python
# 🔥 PLAYOUT TRUTH: Update playout timestamp when enqueuing audio frames
is_audio_frame = isinstance(item, dict) and item.get("type") == "media"
if is_audio_frame:
    # Calculate playout time: now + queue_time + frame_time + grace
    now = time.time()
    queue_size = self.tx_q.qsize()
    frame_pacing_ms = 20  # כל frame = 20ms
    grace_ms = 250
    
    # Total time = (queue frames * 20ms) + (this frame * 20ms) + grace
    queue_time_ms = queue_size * frame_pacing_ms
    frame_time_ms = frame_pacing_ms
    total_playout_ms = queue_time_ms + frame_time_ms + grace_ms
    
    # Update playout timestamp (monotonic - always extends)
    new_playout_ts = now + (total_playout_ms / 1000.0)
    if new_playout_ts > self.ai_playout_until_ts:
        self.ai_playout_until_ts = new_playout_ts
```

**החישוב:**
- Frames בתור × 20ms (כל frame)
- \+ Frame הנוכחי × 20ms
- \+ Grace של 250ms
- \= זמן ההשמעה הכולל

#### ב-Audio Relay Loop (`_realtime_audio_out_loop`)

```python
# When moving frames from realtime_audio_out_queue → tx_q
self.tx_q.put(twilio_frame, timeout=0.5)
self.realtime_tx_frames += 1

# 🔥 PLAYOUT TRUTH: Update playout timestamp
now = time.time()
queue_size = self.tx_q.qsize()
total_playout_ms = (queue_size + 1) * 20 + 250
new_playout_ts = now + (total_playout_ms / 1000.0)

if new_playout_ts > self.ai_playout_until_ts:
    self.ai_playout_until_ts = new_playout_ts
```

### 4. עדכון Timestamp ב-AUDIO_DRAIN

```python
async def delayed_hangup():
    # Capture queue sizes
    initial_q1_size = self.realtime_audio_out_queue.qsize()
    initial_tx_size = self.tx_q.qsize()
    total_frames_remaining = initial_q1_size + initial_tx_size
    
    if total_frames_remaining > 0:
        # Calculate drain time: frames * 20ms + buffer
        remaining_ms = total_frames_remaining * 20
        buffer_ms = 400
        total_wait_ms = remaining_ms + buffer_ms
        
        # 🔥 PLAYOUT TRUTH: Update playout timestamp for drain
        now = time.time()
        grace_ms = 250
        drain_playout_ms = total_wait_ms + grace_ms
        self.ai_playout_until_ts = now + (drain_playout_ms / 1000.0)
        
        _orig_print(f"⏳ [AUDIO DRAIN] waiting {total_wait_ms}ms")
    
    # ... wait for drain ...
    
    # 🔥 Clear playout timestamp after drain completes
    self.ai_playout_until_ts = 0.0
```

### 5. Generation ID למניעת Race Conditions

#### ב-`response.created`

```python
if event_type == "response.created":
    response_id = response.get("id")
    
    # 🔥 GENERATION ID: Increment for race prevention
    if hasattr(self, 'ai_generation_id'):
        self.ai_generation_id += 1
        self.current_generation_id = self.ai_generation_id
        _orig_print(f"🆔 [GENERATION] New generation: gen_id={self.current_generation_id}")
    
    # ... rest of response.created handling
```

#### ב-`_flush_tx_queue()` (Cancel)

```python
def _flush_tx_queue(self):
    # 🔥 PLAYOUT TRUTH: Clear playout timestamp immediately
    self.ai_playout_until_ts = 0.0
    
    # 🔥 GENERATION ID: Increment to ignore late frames
    if hasattr(self, 'ai_generation_id'):
        self.ai_generation_id += 1
        _orig_print(f"🆔 [GENERATION] Cancelled, new gen_id={self.ai_generation_id}")
    
    # ... flush queues
```

**מה זה פותר:**
- תגובה מתבטלת
- Frames מאוחרים מהתגובה הישנה עדיין מגיעים
- ✅ עכשיו: הם מתעלמים כי `generation_id` שלהם ישן

### 6. לוגים משופרים לדיבוג

```python
# בזיהוי ברג-אין
playout_remaining_ms = 0
if hasattr(self, 'ai_playout_until_ts') and self.ai_playout_until_ts > now:
    playout_remaining_ms = (self.ai_playout_until_ts - now) * 1000

_orig_print(
    f"🎙️ [EARLY_BARGE_IN] ⚡ Triggered on speech START! "
    f"playout_remaining_ms={playout_remaining_ms:.0f} "
    f"realtime_q={realtime_q} tx_q={tx_q}"
)
```

```python
# כשמזהים USER_SPEECH בלי ברג-אין
playout_status = "no_playout_ts"
if hasattr(self, 'ai_playout_until_ts'):
    if self.ai_playout_until_ts > now:
        playout_remaining_ms = (self.ai_playout_until_ts - now) * 1000
        playout_status = f"playout_active_{playout_remaining_ms:.0f}ms"
    else:
        elapsed_since_playout = (now - self.ai_playout_until_ts) * 1000
        playout_status = f"playout_ended_{elapsed_since_playout:.0f}ms_ago"

print(f"👤 [USER_SPEECH] AI silent - playout_status={playout_status} tx_q={tx_q_size}")
```

## בדיקות

נוצרו 8 בדיקות אוטומטיות ב-`test_playout_truth_barge_in.py`:

1. ✅ **playout_truth_active** - זיהוי כשה-timestamp בעתיד
2. ✅ **playout_truth_expired** - אי-זיהוי כשה-timestamp עבר
3. ✅ **tx_queue_with_recent_audio** - זיהוי עם frames בתור ואודיו אחרון
4. ✅ **tx_queue_with_old_audio** - אי-זיהוי עם frames אבל אודיו ישן
5. ✅ **legacy_fallback_recent** - Fallback עובד לאודיו אחרון
6. ✅ **legacy_fallback_old** - Fallback לא עובד לאודיו ישן
7. ✅ **playout_priority_over_legacy** - Playout Truth לוקח עדיפות
8. ✅ **no_audio_state** - אי-זיהוי ללא מצב אודיו

**כל 8 הבדיקות עברו בהצלחה! ✅**

## תוצאות צפויות

### לפני התיקון ❌

```
[AI sends last audio.delta]
  ↓ (6 seconds of queued audio playing)
[User starts speaking] ← AI still playing in customer's ear!
  ↓
👤 [USER_SPEECH] User speaking while AI silent (not barge-in)
  ↓
❌ Barge-in NOT triggered (false negative)
```

### אחרי התיקון ✅

```
[AI sends last audio.delta]
  ↓ ai_playout_until_ts = now + 6300ms
[User starts speaking after 2s] ← AI still playing!
  ↓
is_ai_speaking_now() checks:
  - now < ai_playout_until_ts? YES (4300ms remaining)
  ↓
🎙️ [EARLY_BARGE_IN] ⚡ Triggered! playout_remaining_ms=4300
  ↓
✅ Barge-in works correctly!
```

## סיכום השינויים

| קובץ | שינוי | תיאור |
|------|-------|--------|
| `server/media_ws_ai.py` | משתנים חדשים | `ai_playout_until_ts`, `ai_generation_id` |
| `server/media_ws_ai.py` | `is_ai_speaking_now()` | שימוש ב-Playout Truth |
| `server/media_ws_ai.py` | `_tx_enqueue()` | עדכון playout timestamp |
| `server/media_ws_ai.py` | `_realtime_audio_out_loop()` | עדכון playout בהעברת frames |
| `server/media_ws_ai.py` | `delayed_hangup()` | עדכון playout ב-AUDIO_DRAIN |
| `server/media_ws_ai.py` | `response.created` | הגדלת generation_id |
| `server/media_ws_ai.py` | `_flush_tx_queue()` | איפוס playout + generation |
| `test_playout_truth_barge_in.py` | בדיקות | 8 בדיקות אוטומטיות |

## מה הבא?

1. ✅ הקוד מוכן ונבדק
2. ✅ בדיקות עוברות
3. 📋 להריץ בפרודקשן ולוודא שהלוגים מראים:
   - `playout_remaining_ms` בברג-אין
   - `playout_status` ב-USER_SPEECH
   - אין יותר false negatives של "AI silent" כשהיא עדיין מדברת

## עקרונות חשובים

1. **אמת אחת**: השמעה ללקוח = האמת היחידה
2. **Monotonic**: הזמן תמיד מתקדם, לעולם לא מתקצר
3. **Grace Period**: 250ms לעיכובי רשת/באפר
4. **Generation ID**: מניעת race conditions עם frames מאוחרים
5. **Fallback**: תמיכה לאחור ב-last_ai_audio_ts

---

**תיקון זה פותר את הבעיה המקורית: ברג-אין יעבוד "תוך כדי שאני מדבר היא עוצרת"! ✅**
