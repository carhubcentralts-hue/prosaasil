# STT Routing Architecture - Visual Diagram

## קריאת שיחה נכנסת (Incoming Call)
```
┌─────────────────────────────────────┐
│   Twilio Media Stream (WebSocket)  │
│         Audio PCM16 @ 8kHz          │
└───────────────┬─────────────────────┘
                │
                ▼
        ┌───────────────┐
        │ Check Business │
        │  ai_provider   │
        └───────┬────────┘
                │
        ┌───────┴────────┐
        │                │
        ▼                ▼
┌─────────────┐    ┌─────────────┐
│  'openai'   │    │  'gemini'   │
└──────┬──────┘    └──────┬──────┘
       │                  │
       │                  │
```

## 🔶 OpenAI Provider Flow
```
ai_provider = 'openai'
USE_REALTIME_API = True
       │
       ▼
┌────────────────────────────────────┐
│  OpenAI Realtime API Connection    │
│  WebSocket bidirectional streaming │
└────────────────┬───────────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
    ▼            ▼            ▼
┌───────┐  ┌─────────┐  ┌─────────┐
│  STT  │  │   LLM   │  │   TTS   │
│ gpt-4o│  │ GPT-4o  │  │ OpenAI  │
│transcr│  │  mini   │  │ voices  │
└───────┘  └─────────┘  └─────────┘
    │            │            │
    └────────────┼────────────┘
                 │
                 ▼
          Audio Response
          
🚫 NO Whisper
🚫 NO batch STT  
🚫 NO duplication
```

## 🔷 Gemini Provider Flow
```
ai_provider = 'gemini'
USE_REALTIME_API = False
       │
       ▼
┌────────────────────────────────────┐
│     Batch Processing Pipeline      │
│  (STT → LLM → TTS sequentially)    │
└────────────────┬───────────────────┘
                 │
         ┌───────┼───────┐
         │       │       │
         ▼       ▼       ▼
     ┌───────────────────────┐
     │    1. STT Phase       │
     │  Google Cloud Speech  │
     │  google.cloud.speech  │
     │  GOOGLE_CLOUD_SERVICE │
     │  _ACCOUNT_JSON        │
     └───────┬───────────────┘
             │
             ▼ Hebrew transcript
     ┌───────────────────────┐
     │    2. LLM Phase       │
     │  Gemini 2.0 Flash     │
     │  google-genai SDK     │
     │  GEMINI_API_KEY       │
     └───────┬───────────────┘
             │
             ▼ AI response text
     ┌───────────────────────┐
     │    3. TTS Phase       │
     │  Gemini Native Speech │
     │  google-genai SDK     │
     │  GEMINI_API_KEY       │
     └───────┬───────────────┘
             │
             ▼
      Audio Response

🚫 NO Whisper
🚫 NO Realtime API
🚫 NO duplication
```

## ❌ What DOESN'T Happen (NO FALLBACK)

### ❌ Blocked: OpenAI → Whisper
```
OpenAI Provider
       │
       ▼
   Whisper?  ❌ BLOCKED
   
Error: "OpenAI should use Realtime API"
```

### ❌ Blocked: Gemini → Whisper
```
Gemini Provider
       │
       ▼
   Whisper?  ❌ BLOCKED
   
Uses: Google Cloud STT only
```

### ❌ Blocked: Gemini → OpenAI Fallback
```
Gemini fails
       │
       ▼
  Try OpenAI?  ❌ BLOCKED
  
Error: "No fallback between providers"
```

### ❌ Blocked: OpenAI → Gemini Fallback
```
OpenAI fails
       │
       ▼
  Try Gemini?  ❌ BLOCKED
  
Error: "No fallback between providers"
```

## ✅ What IS Allowed (Internal Fallback)

### ✅ Allowed: Streaming → Batch (Same Provider)
```
Gemini Streaming STT
       │
       ▼
   Empty result?
       │
       ▼
Gemini Batch STT  ✅ OK

(Same provider, just different mode)
```

## 🔑 Required Environment Variables

### For OpenAI:
```bash
OPENAI_API_KEY=sk-...
```

### For Gemini:
```bash
# For LLM and TTS
GEMINI_API_KEY=AIza...

# For STT (separate service!)
GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
# OR
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

## 🧪 Test Scenarios

### Scenario 1: OpenAI Call ✅
```
1. Call arrives
2. Business has ai_provider='openai'
3. System starts OpenAI Realtime API
4. Audio transcribed via gpt-4o-transcribe
5. Response generated and played
6. _hebrew_stt() never called (returns '' if called)
```

### Scenario 2: Gemini Call ✅
```
1. Call arrives
2. Business has ai_provider='gemini'
3. System uses batch pipeline
4. Audio sent to Google Cloud Speech-to-Text
5. Transcript sent to Gemini LLM
6. Response sent to Gemini TTS
7. Audio played back
```

### Scenario 3: Missing Google Credentials ❌
```
1. Call arrives
2. Business has ai_provider='gemini'
3. GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON not set
4. ❌ ERROR: "Google Cloud Speech-to-Text credentials missing"
5. Call fails immediately with clear error
```

### Scenario 4: Whisper Incorrectly Called ❌
```
1. Somehow _whisper_fallback() is called
2. ❌ ERROR: "Whisper fallback called incorrectly"
3. Raises exception immediately
```

## 📊 Decision Tree

```
              [Call Start]
                   │
                   ▼
         [Get Business Settings]
                   │
                   ▼
           [Check ai_provider]
                   │
         ┌─────────┴─────────┐
         │                   │
         ▼                   ▼
    'openai'             'gemini'
         │                   │
         ▼                   ▼
  [USE_REALTIME_API     [USE_REALTIME_API
     = True]               = False]
         │                   │
         ▼                   ▼
  [Realtime API]      [Batch Pipeline]
         │                   │
         ▼                   ▼
  [gpt-4o-transcribe]  [Google Cloud STT]
         │                   │
         ▼                   ▼
    [GPT-4o]             [Gemini LLM]
         │                   │
         ▼                   ▼
  [OpenAI TTS]         [Gemini TTS]
         │                   │
         └─────────┬─────────┘
                   │
                   ▼
            [Audio Response]
```

## 🎯 Key Principles

1. **Single Path Per Provider**: Each provider has exactly ONE transcription path
2. **No Cross-Provider Fallback**: Never switch from Gemini to OpenAI or vice versa
3. **Fail Fast**: If credentials missing, fail immediately with clear error
4. **No Duplication**: Each audio chunk transcribed exactly once
5. **Clear Logging**: Every routing decision logged with [STT_ROUTING]

## 📝 Log Examples

### OpenAI Call:
```
[CALL_ROUTING] provider=openai voice=ash
🚀 [REALTIME] Starting OpenAI at T0+123ms
[OPENAI_PIPELINE] Call will use OpenAI Realtime API
```

### Gemini Call:
```
[CALL_ROUTING] provider=gemini voice=pulcherrima
🔷 [GEMINI_PIPELINE] starting
[STT_ROUTING] provider=gemini -> google_cloud_stt
🔷 [GOOGLE_STT] Processing 16000 bytes with Google Cloud Speech-to-Text API
✅ [GOOGLE_STT] Success: 'שלום, איך אפשר לעזור?'
```
