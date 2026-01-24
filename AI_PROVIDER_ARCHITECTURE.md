# AI Provider Architecture: "Same Logic, Different Brain"

## תיאור מערכת: אותה לוגיקה, מוח אחר

### עקרון המפתח 🔥
**Gemini מחליף רק את המוח (LLM) וה-TTS שלו. כל החוקים, הזרימה, הגארדים, האודיו והפרומפטים נשארים 1:1 כמו ב-OpenAI.**

---

## 🏗️ ארכיטקטורה: מקור אמת אחד (SSOT)

### 1. מקורות האמת (Single Sources of Truth)

בכל מקום בקוד יש **רק מקור אמת אחד** ל:

| רכיב | מיקום | תיאור |
|------|-------|-------|
| **System/Business Prompt** | `server/services/realtime_prompt_builder.py` | בונה פרומפטים - אותה פונקציה לשני הספקים |
| **חוקי שיחה** | `server/services/realtime_prompt_builder.py` | שאלות/תסריט/איסורים/טון - זהה לכולם |
| **Guardrails** | `server/media_ws_ai.py` | ג'יבריש, לולאות, חסימות, fallbacks |
| **Audio Pipeline** | `server/media_ws_ai.py::_send_pcm16_as_mulaw_frames*` | PCMU 8k, 20ms, TX queue - זהה לכולם |
| **State Machine** | `server/media_ws_ai.py::MediaStreamHandler` | מתי מקשיב/מעבד/מדבר - זהה |
| **AI Provider Selection** | `server/models_sql.py::Business.ai_provider` | הגדרה אחת שולטת בהכל |
| **Voice Catalog** | `server/config/voice_catalog.py` | קטלוג קולות לכל ספק |

---

## 🔄 מה משתנה (ורק זה!)

### ✅ משתנים רק שני דברים:

#### 1. LLM Client
```
OpenAIChatClient → GeminiChatClient
```
**אבל מקבל בדיוק את אותם inputs:**
- ✓ אותו system_prompt
- ✓ אותו conversation_history  
- ✓ אותם "style rules"
- ✓ אותם temp/max_tokens (או מיפוי הכי קרוב)

**מיקום בקוד:**
- `server/services/ai_service.py::generate_response()`
- בודק `ai_provider` ומנתב ל-OpenAI או Gemini
- שניהם מקבלים **אותם messages** ו**אותו prompt**

#### 2. TTS Provider  
```
openai_tts() → gemini_tts()
```
**אבל הפלט חייב להיכנס לאותו audio_out pipeline:**
- ✓ PCM16 8kHz → μ-law
- ✓ 160 bytes per frame (20ms)
- ✓ דרך `_send_pcm16_as_mulaw_frames()`

**מיקום בקוד:**
- `server/media_ws_ai.py::_hebrew_tts()`
- `server/services/tts_provider.py::synthesize()`
- **שניהם** מחזירים PCM16 8kHz שנשלח דרך אותה פונקציה

---

## 🚫 מה אסור להשתנות (1:1)

### 1) פרומפטים
- ✅ **אותה פונקציה** בונה את הפרומפט לשני הספקים
- ✅ **לא לכתוב** "גרסה לג'מיני"
- ✅ **לא לשנות** ניסוח, לא לקצר, לא להוסיף "הסברים"
- ✅ Gemini מקבל את הפרומפט **כמו שהוא**, נקודה

**אימות:**
```python
# server/services/realtime_prompt_builder.py
def build_full_business_prompt(business_id, call_direction):
    # ✅ פונקציה אחת, לא תלוי בספק
    # משמש גם ל-OpenAI וגם ל-Gemini
```

### 2) לוגיקת השיחה
- ✅ אותם שלבים, אותו זיכרון
- ✅ אותם timeouts/limits/anti-loop
- ✅ אותם חוקים: "לא מבטיח סכומים", "לא ממציא מידע"
- ✅ "שאלה אחת בכל פעם"

**אימות:**
```python
# server/media_ws_ai.py::MediaStreamHandler
# State machine זהה לשני הספקים:
# STATE_LISTEN → STATE_PROCESSING → STATE_SPEAK
```

### 3) גארדים (Guards)
- ✅ gibberish detector - זהה
- ✅ profanity filter - זהה
- ✅ quality gates - זהה
- ✅ retries - זהה
- ✅ **אין** quality gate חדש לג'מיני
- ✅ **אין** bypass

**אימות:**
```python
# server/services/hebrew_stt_validator.py
# validate_stt_output(), is_gibberish()
# משמשים לשני הספקים בלי הבדל
```

### 4) אודיו (הכי חשוב!)
- ✅ כל ספק חייב להוציא **PCMU 8k / 20ms**
- ✅ דרך **אותה פונקציה**: `_send_pcm16_as_mulaw_frames()`
- ✅ **אין** שום נתיב "Gemini TX" נפרד

**אימות:**
```python
# server/media_ws_ai.py
def _send_pcm16_as_mulaw_frames_with_mark(self, pcm16_8k: bytes):
    """שליחת אודיו - משותף לכל הספקים"""
    mulaw = audioop.lin2ulaw(pcm16_8k, 2)  # ✅ PCMU
    FR = 160  # ✅ 20ms @ 8kHz
    # שני הספקים משתמשים בפונקציה זו!
```

---

## 🎯 יישום בפועל (ללא הסתבכויות)

### א) AIEngine אחד

שכבה אחת מנתבת את כל הבקשות:

```python
# server/services/ai_service.py::AIService
class AIService:
    def generate_response(self, message, business_id, ...):
        # ✅ בודק ai_provider
        ai_provider = self._get_ai_provider(business_id)
        
        # ✅ טוען אותו prompt
        prompt_data = self.get_business_prompt(business_id)
        messages = self._build_messages(...)
        
        # ✅ מנתב לספק המתאים
        if ai_provider == 'gemini':
            response = gemini_client.models.generate_content(...)
        else:
            response = self.client.chat.completions.create(...)
```

**עקרון:** 
- פונקציה אחת: `generate_response()`
- קלט זהה: `business_id, messages, system_prompt`
- פלט זהה: `text response`
- רק השורה של הקריאה ל-API משתנה

### ב) AudioOut אחד

```python
# server/media_ws_ai.py
def _send_pcm16_as_mulaw_frames(self, pcm16_8k: bytes):
    """פונקציה אחת לשליחת אודיו - לכל הספקים"""
    mulaw = audioop.lin2ulaw(pcm16_8k, 2)
    FR = 160  # 20ms @ 8kHz
    for i in range(0, len(mulaw), FR):
        frame = mulaw[i:i+FR]
        # שליחה ל-Twilio
```

**עקרון:**
- OpenAI משתמש בזה ✅
- Gemini משתמש בזה ✅
- תוך הפונקציה: decode/resample/pcmu/chunk

### ג) Provider = Brain+Voice (חוק ברזל)

```python
# server/models_sql.py::Business
ai_provider = db.Column(db.String(32), default="openai")
voice_name = db.Column(db.String(64), default="alloy")
```

**חוקים:**
- ✅ אם `ai_provider=gemini` → גם LLM=gemini **וגם** voices=gemini **בלבד**
- ✅ אם `ai_provider=openai` → גם LLM=openai **וגם** voices=openai **בלבד**
- ✅ **אין ערבוב**, אין fallback לספק השני
- ✅ הצליל תואם לספק האינטליגנציה

**אכיפה בקוד:**
```python
# server/media_ws_ai.py::MediaStreamHandler
# CRITICAL: Load ai_provider and voice BEFORE starting AI service
ai_provider = getattr(business, 'ai_provider', 'openai')
voice_name = getattr(business, 'voice_name', None)

# Validate voice matches provider
if not is_valid_voice(voice_name, ai_provider):
    voice_name = default_voice(ai_provider)
```

---

## 📊 בדיקת הצלחה - מה חייב להראות בלוגים

### כשבחרת Gemini (`ai_provider=gemini`):

```log
[CALL_ROUTING] business=123 provider=gemini voice=pulcherrima direction=inbound
[AI_SERVICE] Business 123 uses provider: gemini
[GEMINI_PIPELINE] Call will use Gemini: STT (Whisper) → LLM (Gemini) → TTS (Gemini)
[AI_SERVICE] Using Gemini LLM for business 123
[GEMINI_TTS] Synthesizing: 45 chars
[GEMINI_TTS] Success: 87040 bytes (audio/wav)
audio_out: format=pcmu sr=8000 frame=160B
frames_forwarded increasing
tx_q not stuck on 200+
```

### כשבחרת OpenAI (`ai_provider=openai`):

```log
[CALL_ROUTING] business=123 provider=openai voice=alloy direction=inbound
[AI_SERVICE] Business 123 uses provider: openai
[OPENAI_PIPELINE] Call will use OpenAI Realtime API
[REALTIME] Starting OpenAI...
audio_out: format=pcmu sr=8000 frame=160B
frames_forwarded increasing
tx_q not stuck on 200+
```

---

## 🔍 Pipeline Comparison

### OpenAI Pipeline:
```
Call Start
    ↓
[CALL_ROUTING] provider=openai
    ↓
OpenAI Realtime API (WebSocket)
    ├─ STT: Built-in (streaming)
    ├─ LLM: gpt-4o-realtime-preview
    └─ TTS: Built-in (streaming)
    ↓
Audio Output: PCM16 8kHz
    ↓
_send_pcm16_as_mulaw_frames()
    ↓
PCMU 8k / 160B frames (20ms)
    ↓
Twilio
```

### Gemini Pipeline:
```
Call Start
    ↓
[CALL_ROUTING] provider=gemini
    ↓
Gemini Pipeline (Sequential)
    ├─ STT: Whisper (batch)
    ├─ LLM: gemini-2.0-flash-exp
    └─ TTS: gemini-2.5-flash-preview-tts
    ↓
Audio Output: PCM16 8kHz (from WAV)
    ↓
_send_pcm16_as_mulaw_frames()  ← אותה פונקציה!
    ↓
PCMU 8k / 160B frames (20ms)  ← אותו פורמט!
    ↓
Twilio
```

**הבדל מרכזי:**
- OpenAI: Bidirectional WebSocket (streaming real-time)
- Gemini: Sequential pipeline (STT → LLM → TTS)
- **אבל:** Audio output pipeline **זהה לחלוטין** ✅

---

## 📁 מיפוי קבצים

### Core Files

| קובץ | תפקיד | ספק |
|------|-------|-----|
| `server/models_sql.py` | הגדרת `Business.ai_provider` | Universal |
| `server/services/ai_service.py` | AIEngine - LLM routing | OpenAI + Gemini |
| `server/services/realtime_prompt_builder.py` | Prompt Builder (SSOT) | Universal |
| `server/media_ws_ai.py` | Media handler + Audio pipeline | Universal |
| `server/services/tts_provider.py` | TTS abstraction | OpenAI + Gemini |
| `server/services/openai_realtime_client.py` | OpenAI Realtime client | OpenAI only |
| `server/config/voice_catalog.py` | Voice catalog (both providers) | Universal |
| `server/services/gemini_voice_catalog.py` | Gemini voice discovery | Gemini only |

### Configuration Files

| קובץ | תיאור |
|------|--------|
| `server/config/voices.py` | OpenAI voices configuration |
| `server/config/calls.py` | Call settings (VAD, barge-in, etc.) |
| `server/services/name_validation.py` | Name validation rules |
| `server/services/prompt_hashing.py` | Prompt integrity |

---

## ✅ Verification Checklist

### עבור כל ספק, ודא:

#### 1. Prompt Consistency
- [ ] אותה פונקציה בונה את הפרומפט
- [ ] אין קוד פרומפט ייעודי לג'מיני
- [ ] prompt hash זהה לשני הספקים

#### 2. Audio Pipeline Unity
- [ ] שני הספקים משתמשים ב-`_send_pcm16_as_mulaw_frames()`
- [ ] פורמט אחיד: PCMU 8kHz, 160B frames (20ms)
- [ ] אין נתיב TX נפרד

#### 3. Provider Isolation
- [ ] `ai_provider` שולט גם ב-LLM וגם ב-TTS
- [ ] אין fallback בין ספקים
- [ ] voice validation לפי ספק

#### 4. State Machine Consistency
- [ ] אותה state machine (LISTEN/PROCESSING/SPEAK)
- [ ] אותם guards ו-validators
- [ ] אותם timeouts ו-limits

#### 5. Logging Requirements
- [ ] `[CALL_ROUTING] provider=X` - חובה!
- [ ] `LLM provider=X` - ברור באיזה LLM משתמשים
- [ ] `TTS provider=X` - ברור באיזה TTS משתמשים
- [ ] `audio_out: format=pcmu sr=8000` - אודיו מתועד

---

## 🚀 How to Add New Provider

אם רוצים להוסיף ספק נוסף (למשל: Claude, Anthropic):

### 1. הוסף לקטלוג
```python
# server/models_sql.py
# ai_provider supports: "openai" | "gemini" | "claude"
```

### 2. הוסף ל-Voice Catalog
```python
# server/config/voice_catalog.py
CLAUDE_VOICES = [...]

def get_voices(provider: str):
    if provider == "claude":
        return CLAUDE_VOICES
    # ...
```

### 3. הוסף ל-AIService
```python
# server/services/ai_service.py
def generate_response(self, ...):
    ai_provider = self._get_ai_provider(business_id)
    
    if ai_provider == 'claude':
        # שימוש באותם messages ו-prompt!
        response = claude_client.messages.create(...)
    # ...
```

### 4. הוסף ל-TTS Provider
```python
# server/services/tts_provider.py
def synthesize(text, provider, ...):
    if provider == "claude":
        # חייב להחזיר PCM16 8kHz!
        return synthesize_claude(text, ...)
```

### 5. ודא Audio Output
```python
# server/media_ws_ai.py::_hebrew_tts()
# הפלט חייב להיות PCM16 8kHz
# שייכנס ל-_send_pcm16_as_mulaw_frames()
```

**זהו!** הכל שאר נשאר **זהה** - אותם prompts, guards, state machine.

---

## 🎓 Key Principles Summary

1. **Single Source of Truth** - כל רכיב יש לו מיקום אחד בקוד
2. **Provider Isolation** - ai_provider שולט בהכל (LLM+TTS)
3. **Unified Audio Pipeline** - פונקציה אחת לכל הספקים
4. **Shared Logic** - prompts, guards, state machine זהים
5. **Clear Routing** - logging מפורש של כל החלטה
6. **No Mixing** - אין fallback או ערבוב בין ספקים

---

## 📞 Contact & Support

לשאלות או בעיות:
- בדוק קודם את הלוגים: `[CALL_ROUTING]`, `[AI_SERVICE]`, `[GEMINI_TTS]`
- הרץ את הטסט: `python3 test_ai_provider_routing.py`
- וודא שה-API keys מוגדרים: `OPENAI_API_KEY`, `GEMINI_API_KEY`

---

**סיכום:** אותה לוגיקה, מוח אחר. Gemini זה סתם swap של ה-LLM וה-TTS. הכל שאר נשאר זהה 1:1 כמו OpenAI. 🎯
