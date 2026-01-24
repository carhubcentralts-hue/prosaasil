# STT Routing Fix - Summary

## Problem Statement
The original problem (in Hebrew) requested:
1. Fix UI crash due to undefined `setShowSmartGenerator`
2. Use Google STT (not Whisper) when Gemini is selected
3. OpenAI should NOT use Whisper - use Realtime API as before
4. NO transcription duplication
5. NO fallback between providers
6. Everything based on `ai_provider` setting

## Solution

### 1. UI Fix ✅
**File**: `client/src/pages/Admin/PromptStudioPage.tsx`
- Fixed line 230: Changed `setShowSmartGenerator(true)` → `setShowChatBuilder(true)`
- No other occurrences of the undefined variable

### 2. STT Routing Overhaul ✅
**File**: `server/media_ws_ai.py`

#### OpenAI Provider (`ai_provider='openai'`)
```
OpenAI Realtime API (bidirectional WebSocket)
├─ STT: gpt-4o-transcribe (built into Realtime API)
├─ LLM: GPT-4o
└─ TTS: OpenAI voices

✅ NO Whisper
✅ NO batch processing  
✅ NO duplication
```

#### Gemini Provider (`ai_provider='gemini'`)
```
Batch Pipeline (STT → LLM → TTS)
├─ STT: Google Cloud Speech-to-Text (google.cloud.speech)
├─ LLM: Gemini 2.0 Flash
└─ TTS: Gemini Native Speech

✅ NO Whisper
✅ NO Realtime API
✅ NO duplication
```

### 3. No Fallback Policy ✅
- **OpenAI provider** → ONLY OpenAI (no Gemini fallback)
- **Gemini provider** → ONLY Gemini (no OpenAI fallback)
- **Missing credentials** → Immediate error with clear message
- **No silent provider switching**

### 4. No Duplication ✅
- Each provider has **exactly ONE** transcription path
- OpenAI: Realtime API handles STT internally
- Gemini: Google Cloud STT only (batch mode)
- `_whisper_fallback()` disabled - raises error if called

## Environment Variables

### OpenAI:
```bash
OPENAI_API_KEY=sk-...
```

### Gemini:
```bash
# For LLM and TTS
GEMINI_API_KEY=AIza...

# For STT (separate Google Cloud service)
GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
# OR
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

**Important**: `GEMINI_API_KEY` and `GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON` are for **different services**:
- GEMINI_API_KEY: Gemini LLM and TTS
- GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON: Google Cloud Speech-to-Text

## Testing

### Check Logs for OpenAI:
```bash
grep "CALL_ROUTING.*openai" server.log
grep "REALTIME" server.log
```

### Check Logs for Gemini:
```bash
grep "STT_ROUTING.*gemini" server.log
grep "GOOGLE_STT" server.log
```

### Expected Log Output

**OpenAI Call**:
```
[CALL_ROUTING] provider=openai voice=ash
🚀 [REALTIME] Starting OpenAI at T0+123ms
```

**Gemini Call**:
```
[CALL_ROUTING] provider=gemini voice=pulcherrima  
[STT_ROUTING] provider=gemini -> google_cloud_stt
🔷 [GOOGLE_STT] Processing audio with Google Cloud Speech-to-Text API
✅ [GOOGLE_STT] Success: 'שלום, איך אפשר לעזור?'
```

## Code Changes

### Modified Files:
1. `client/src/pages/Admin/PromptStudioPage.tsx` - UI fix
2. `server/media_ws_ai.py` - Complete STT routing overhaul

### Key Functions Modified:
- `_hebrew_stt()` - Now routes based on `ai_provider`, no fallback
- `_hebrew_stt_wrapper()` - Internal fallback (streaming→batch) only
- `_google_stt_batch()` - NEW: Google Cloud STT integration for Gemini
- `_whisper_fallback()` - Disabled, raises error if called

### Documentation Added:
- `FIX_SUMMARY_STT_ROUTING_HE.md` - Hebrew documentation
- `STT_ROUTING_ARCHITECTURE_DIAGRAM.md` - Visual architecture
- File header in `media_ws_ai.py` - Complete routing explanation

## Error Messages

### Missing Google Credentials:
```
❌ [CONFIG] Google Cloud Speech-to-Text credentials missing.
Set GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS.
GEMINI_API_KEY is for Gemini LLM/TTS only, not STT.
```

### OpenAI Incorrectly Using Batch STT:
```
❌ [STT_ERROR] OpenAI provider reached batch STT - this is a bug!
OpenAI should use Realtime API for STT, not batch processing.
```

### Whisper Incorrectly Called:
```
❌ [BUG] _whisper_fallback called - this should never happen!
OpenAI should use Realtime API, Gemini should use Google STT.
```

## Architecture Principles

1. **Provider Isolation**: Each provider operates independently
2. **Single Transcription Path**: No duplication possible
3. **Fail Fast**: Missing credentials cause immediate failure
4. **Clear Errors**: Every misconfiguration has explicit error message
5. **Immutable Routing**: Provider selection cannot change mid-call

## Verification Checklist

- [ ] UI: Prompt generator button works without errors
- [ ] OpenAI: Uses Realtime API (check logs for [REALTIME])
- [ ] Gemini: Uses Google Cloud STT (check logs for [GOOGLE_STT])
- [ ] No Whisper usage for either provider
- [ ] Clear errors when credentials missing
- [ ] No transcription duplication
- [ ] No silent provider switching

## Related Files

- `FIX_SUMMARY_STT_ROUTING_HE.md` - Detailed Hebrew explanation
- `STT_ROUTING_ARCHITECTURE_DIAGRAM.md` - Visual flow diagrams
- `server/media_ws_ai.py` - Main implementation
- `client/src/pages/Admin/PromptStudioPage.tsx` - UI fix

## Support

If issues occur:
1. Check logs: `grep "STT_ROUTING\|CALL_ROUTING" server.log`
2. Verify environment variables are set correctly
3. Ensure `ai_provider` is configured in business settings
4. Remember: NO FALLBACK - missing credentials will fail immediately
