# VAD and Gate Timing Improvements - Implementation Summary

## תיאור הבעיה (Problem Description)

במצב של שקט מוחלט, VAD (Voice Activity Detection) ו-noise gates "מתלבטים" מתי התחיל דיבור אמיתי, מה שגורם לחיתוך של ההברות הראשונות ולירידה בדיוק התמלול. כשיש רעש רקע קטן רציף, ה-VAD והגייט "נשארים יותר יציבים" ויש פחות clipping בתחילת הדיבור.

When there is complete silence, VAD (Voice Activity Detection) and noise gates "hesitate" about when real speech starts, causing clipping of initial syllables and reduced transcription accuracy. With small continuous background noise, VAD and gates remain "more stable" with less clipping at speech onset.

## הפתרון (Solution)

השינויים הבאים מבוססים על ההנחיה:
1. **הגדלת prefix padding של VAD** - מ-300ms ל-500ms (הגדלה של 200ms)
2. **הקלה על פתיחת gate** - הורדת threshold מ-270.0 ל-250.0
3. **הוספת decay** - 200ms המתנה לפני re-enable של gate אחרי END OF UTTERANCE

These changes are based on the directive:
1. **Increase VAD prefix padding** - from 300ms to 500ms (200ms increase)
2. **Ease gate opening** - reduce threshold from 270.0 to 250.0
3. **Add decay** - 200ms wait before re-enabling gate after END OF UTTERANCE

## שינויים טכניים (Technical Changes)

### 1. server/config/calls.py

#### SERVER_VAD_PREFIX_PADDING_MS
```python
# Before:
SERVER_VAD_PREFIX_PADDING_MS = 300  # Standard padding for Hebrew

# After:
SERVER_VAD_PREFIX_PADDING_MS = 500  # Increased padding to avoid clipping speech start
```

**הסבר (Explanation):**
- הגדלה מ-300ms ל-500ms (200ms נוספים)
- מונע חיתוך של הברות ראשונות כשהדיבור מתחיל משקט מוחלט
- נותן ל-VAD יותר זמן "לתפוס" את התחלת הדיבור
- Increase from 300ms to 500ms (additional 200ms)
- Prevents clipping of initial syllables when speech starts from complete silence
- Gives VAD more time to "catch" speech onset

#### ECHO_GATE_MIN_RMS
```python
# Before:
ECHO_GATE_MIN_RMS = 270.0  # Stronger protection from background noise

# After:
ECHO_GATE_MIN_RMS = 250.0  # Easier gate opening for better speech capture
```

**הסבר (Explanation):**
- הורדה מ-270.0 ל-250.0 (יותר קל לפתוח את הגייט)
- מאפשר לדיבור אמיתי לעבור ביתר קלות
- מפחית "היסוס" של ה-VAD בתחילת הדיבור משקט
- Reduction from 270.0 to 250.0 (easier gate opening)
- Allows real speech to pass through more easily
- Reduces VAD "hesitation" at speech onset from silence

#### ECHO_GATE_DECAY_MS (חדש / New)
```python
# New parameter:
ECHO_GATE_DECAY_MS = 200  # 200ms decay - prevents clipping end/start of turns
```

**הסבר (Explanation):**
- פרמטר חדש: 200ms המתנה לפני re-enable של gate
- מונע חיתוך של סוף המשפט או תחילת הטורן הבא
- הגייט נשאר "פתוח" ל-200ms אחרי שהדיבור נגמר
- New parameter: 200ms wait before re-enabling gate
- Prevents clipping of utterance ending or start of next turn
- Gate stays "open" for 200ms after speech ends

### 2. server/media_ws_ai.py

#### Import Statement
```python
from server.config.calls import (
    ...
    ECHO_GATE_MIN_RMS, ECHO_GATE_MIN_FRAMES, ECHO_GATE_DECAY_MS,
    ...
)
```

#### Initialization
```python
# New state variable to track when speech stopped
self._speech_stopped_ts = None  # Timestamp when speech stopped (for decay calculation)
```

#### Speech Stopped Handler
```python
if event_type == "input_audio_buffer.speech_stopped":
    # Store timestamp when speech stopped, gate will re-enable after decay period
    self._speech_stopped_ts = time.time()
    print(f"🎤 [BUILD 166] Speech ended - gate decay started ({ECHO_GATE_DECAY_MS}ms)")
```

#### Gate Bypass Logic with Decay
```python
# Check if we're in decay period (gate stays open after speech stops)
in_decay_period = False
if hasattr(self, '_speech_stopped_ts') and self._speech_stopped_ts:
    decay_elapsed_ms = (time.time() - self._speech_stopped_ts) * 1000
    if decay_elapsed_ms < ECHO_GATE_DECAY_MS:
        in_decay_period = True
    else:
        # Decay period expired, fully re-enable gate
        if self._realtime_speech_active:
            self._realtime_speech_active = False
            print(f"🎤 [GATE_DECAY] Decay period complete ({decay_elapsed_ms:.0f}ms) - gate RE-ENABLED")
        self._speech_stopped_ts = None

speech_bypass_active = self._realtime_speech_active or in_decay_period
```

### 3. server/services/openai_realtime_client.py

#### Fallback Value Update
```python
# Before:
if prefix_padding_ms is None:
    prefix_padding_ms = 300  # Match default from config

# After:
if prefix_padding_ms is None:
    prefix_padding_ms = 500  # Match default from config - increased for better speech capture
```

## תועלות צפויות (Expected Benefits)

### 1. שיפור בתמלול של הברות ראשונות
- ה-VAD "תופס" את תחילת הדיבור יותר מוקדם
- פחות clipping של מילים ראשונות
- Better transcription of initial syllables
- VAD "catches" speech onset earlier
- Less clipping of first words

### 2. פתיחה מהירה יותר של gate
- דיבור שקט עובר ביתר קלות
- פחות היסוס במעבר משקט לדיבור
- Faster gate opening
- Quiet speech passes more easily
- Less hesitation in silence-to-speech transition

### 3. אין clipping בגבולות utterance
- הגייט נשאר פתוח ל-200ms אחרי סוף דיבור
- מונע חיתוך של סוף המשפט
- מונע חיתוך של תחילת הטורן הבא
- Gate stays open for 200ms after speech ends
- Prevents clipping of sentence ending
- Prevents clipping of next turn start

## בדיקות (Testing)

הרצת הבדיקה:
```bash
cd /home/runner/work/prosaasil/prosaasil
python test_vad_gate_timing_improvements.py
```

תוצאות צפויות:
```
✅ VAD prefix padding: 500ms (prevents initial syllable clipping)
✅ Echo gate threshold: 250.0 RMS (easier gate opening at speech start)
✅ Echo gate decay: 200ms (prevents end/start clipping)
✅ All tests passed! Configuration is correctly set for improved transcription.
```

## פריסה לפרודקשן (Production Deployment)

### ללא שינוי קוד נוסף (No Additional Code Changes)
השינויים כבר מיושמים במלואם. אין צורך בשינויים נוספים.

### ניטור (Monitoring)
לאחר פריסה, יש לנטר:
1. **דיוק תמלול** - האם יש שיפור בתמלול של הברות ראשונות?
2. **False positives** - האם יש יותר זיהויי דיבור מוטעים מרעש רקע?
3. **Barge-in quality** - האם הפרעות למשתמש עדיין עובדות טוב?

After deployment, monitor:
1. **Transcription accuracy** - Is there improvement in transcribing initial syllables?
2. **False positives** - Are there more false speech detections from background noise?
3. **Barge-in quality** - Do user interruptions still work well?

### התאמות אפשריות (Possible Adjustments)

אם יש יותר מדי false positives:
```python
SERVER_VAD_PREFIX_PADDING_MS = 400  # הפחתה ל-400ms
ECHO_GATE_MIN_RMS = 260.0  # העלאה ל-260.0
```

אם עדיין יש clipping:
```python
SERVER_VAD_PREFIX_PADDING_MS = 600  # הגדלה ל-600ms
ECHO_GATE_DECAY_MS = 250  # הגדלה ל-250ms
```

## סיכום (Summary)

השינויים מיישמים את ההנחיה בצורה מדויקת:
- ✅ הגדלת prefix padding ב-100-200ms (היישום: 200ms)
- ✅ הקלה על פתיחת gate בתחילת דיבור (270→250)
- ✅ הוספת decay של 150-250ms (היישום: 200ms)

Changes implement the directive accurately:
- ✅ Increase prefix padding by 100-200ms (implementation: 200ms)
- ✅ Ease gate opening at speech start (270→250)
- ✅ Add decay of 150-250ms (implementation: 200ms)

זהו שינוי קטן בפרמטרים/טיימינג, לא "מערכת חדשה", שישפר תמלול!
This is a small change in parameters/timing, not a "new system", that will improve transcription!
