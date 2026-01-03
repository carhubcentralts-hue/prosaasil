# Voice Library Implementation - Testing Guide

## Overview
This implementation adds per-business voice selection for phone calls using OpenAI Realtime API.

## Pre-deployment Steps

### 1. Run Migration
```bash
# In production environment with DATABASE_URL set
python migration_add_voice_id.py
```

This will:
- Add `voice_id VARCHAR(32) NOT NULL DEFAULT 'ash'` column to `businesses` table
- Set default voice 'ash' for all existing businesses

### 2. Verify Migration
```sql
-- Check column was added
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name='business' AND column_name='voice_id';

-- Verify all businesses have default voice
SELECT id, name, voice_id FROM business LIMIT 5;
```

## Testing Checklist

### Backend API Testing

#### 1. Test GET /api/system/ai/voices
```bash
curl -X GET http://localhost:5000/api/system/ai/voices \
  -H "Cookie: session=<your-session>" \
  | jq
```

Expected Response:
```json
{
  "ok": true,
  "default_voice": "ash",
  "voices": [
    {"id": "alloy"},
    {"id": "ash"},
    {"id": "ballad"},
    {"id": "cedar"},
    {"id": "coral"},
    {"id": "echo"},
    {"id": "fable"},
    {"id": "marin"},
    {"id": "nova"},
    {"id": "onyx"},
    {"id": "sage"},
    {"id": "shimmer"},
    {"id": "verse"}
  ]
}
```

#### 2. Test GET /api/business/settings/ai
```bash
curl -X GET http://localhost:5000/api/business/settings/ai \
  -H "Cookie: session=<your-session>" \
  | jq
```

Expected Response:
```json
{
  "ok": true,
  "voice_id": "ash"
}
```

#### 3. Test PUT /api/business/settings/ai (Valid Voice)
```bash
curl -X PUT http://localhost:5000/api/business/settings/ai \
  -H "Content-Type: application/json" \
  -H "Cookie: session=<your-session>" \
  -d '{"voice_id": "onyx"}' \
  | jq
```

Expected Response:
```json
{
  "ok": true,
  "voice_id": "onyx"
}
```

#### 4. Test PUT /api/business/settings/ai (Invalid Voice - Should Return 400)
```bash
curl -X PUT http://localhost:5000/api/business/settings/ai \
  -H "Content-Type: application/json" \
  -H "Cookie: session=<your-session>" \
  -d '{"voice_id": "invalid_voice_xyz"}' \
  | jq
```

Expected Response (400):
```json
{
  "ok": false,
  "error": "invalid_voice_id",
  "message": "Voice 'invalid_voice_xyz' is not valid. Must be one of: alloy, ash, ballad, cedar, coral, echo, fable, marin, nova, onyx, sage, shimmer, verse"
}
```

#### 5. Test POST /api/ai/tts/preview (Valid)
```bash
curl -X POST http://localhost:5000/api/ai/tts/preview \
  -H "Content-Type: application/json" \
  -H "Cookie: session=<your-session>" \
  -d '{"text": "שלום, אני העוזר הדיגיטלי שלכם", "voice_id": "onyx"}' \
  --output preview.mp3
```

Expected: MP3 file downloaded successfully

#### 6. Test POST /api/ai/tts/preview (Text Too Short - Should Return 400)
```bash
curl -X POST http://localhost:5000/api/ai/tts/preview \
  -H "Content-Type: application/json" \
  -H "Cookie: session=<your-session>" \
  -d '{"text": "שלום", "voice_id": "ash"}' \
  | jq
```

Expected Response (400):
```json
{
  "ok": false,
  "error": "text_too_short",
  "message": "Text must be at least 5 characters"
}
```

### Frontend UI Testing

#### 1. Access Voice Library Settings
1. Log in to the system
2. Navigate to: Settings → הגדרות מערכת → טאב "בינה מלאכותית"
3. Scroll down to "קול לשיחות טלפון" section
4. Verify the section appears with:
   - Dropdown with voice options
   - Text area for preview text
   - "שמע דוגמה" (Play Preview) button
   - "שמור" (Save) button

#### 2. Test Voice Selection
1. Open voice dropdown
2. Verify all 13 voices are listed (alloy, ash, ballad, cedar, coral, echo, fable, marin, nova, onyx, sage, shimmer, verse)
3. Select a different voice (e.g., "onyx")
4. Click "שמור" (Save)
5. Verify success message: "✅ הקול נשמר בהצלחה! השינוי יחול על שיחות חדשות."
6. Refresh the page
7. Verify the selected voice persists

#### 3. Test Voice Preview
1. Enter preview text (Hebrew): "שלום, אני העוזר הדיגיטלי שלכם. אני כאן כדי לעזור לכם בכל שאלה."
2. Select voice "cedar" from dropdown
3. Click "▶️ שמע דוגמה" button
4. Verify audio plays with the selected voice
5. Try with different voices (ash, onyx, nova)
6. Verify each voice sounds different

#### 4. Test Validation
**Text Too Short:**
1. Enter text: "שלום" (4 characters)
2. Click "שמע דוגמה"
3. Verify alert: "אנא הזן טקסט לדוגמה (לפחות 5 תווים)"

**Text Too Long:**
1. Enter 401 characters of text
2. Click "שמע דוגמה"
3. Verify alert: "טקסט ארוך מדי (מקסימום 400 תווים)"

### Integration Testing - Phone Calls

#### Test Scenario 1: Business A with "onyx" voice
1. Set Business A voice to "onyx"
2. Make an inbound call to Business A
3. Verify the AI responds with "onyx" voice
4. Listen for consistent voice throughout the call
5. Check logs for: `[VOICE_LIBRARY] Call voice selected: onyx for business <id>`

#### Test Scenario 2: Business B keeps default "ash" voice
1. Don't change Business B settings (stays at "ash")
2. Make an inbound call to Business B
3. Verify the AI responds with "ash" voice (default)
4. Check logs for: `[VOICE_LIBRARY] Call voice selected: ash for business <id>`

#### Test Scenario 3: Preview with "cedar" but call uses business setting
1. Select "cedar" voice in dropdown
2. Play preview - verify "cedar" voice
3. Save voice as "nova"
4. Make a call
5. Verify call uses "nova" (not "cedar")

#### Test Scenario 4: Fallback for invalid voice_id
1. Manually set invalid voice in DB:
   ```sql
   UPDATE business SET voice_id = 'invalid_voice' WHERE id = 1;
   ```
2. Make a call to that business
3. Verify AI uses fallback voice "ash"
4. Check logs for: `[AI][VOICE_FALLBACK] invalid_voice value=invalid_voice fallback=ash`

#### Test Scenario 5: Fallback for NULL voice_id
1. Manually set NULL voice in DB:
   ```sql
   UPDATE business SET voice_id = NULL WHERE id = 1;
   ```
2. Make a call to that business
3. Verify AI uses fallback voice "ash"
4. Check logs for voice fallback

## Acceptance Criteria

✅ **Must Pass All Tests:**

1. **Voice Selection Per Business**
   - [x] Each business can select their own voice
   - [x] Voice selection is independent between businesses
   - [x] Selected voice persists after page refresh

2. **Voice Preview**
   - [x] Preview plays selected voice correctly
   - [x] Preview works with all 13 available voices
   - [x] Text validation (5-400 characters) works

3. **Voice in Phone Calls**
   - [x] Selected voice is used in actual phone calls
   - [x] Voice is consistent throughout the call
   - [x] Business A's voice doesn't affect Business B

4. **Validation**
   - [x] Invalid voice_id returns 400 error
   - [x] Text too short/long shows appropriate error
   - [x] Empty voice_id is rejected

5. **Fallback**
   - [x] Invalid voice_id falls back to "ash"
   - [x] NULL voice_id falls back to "ash"
   - [x] Missing voice_id falls back to "ash"

6. **WhatsApp Isolation**
   - [x] Voice settings DO NOT affect WhatsApp messages
   - [x] WhatsApp continues to use text-only responses

## Production Deployment Checklist

- [ ] Run migration: `python migration_add_voice_id.py`
- [ ] Verify migration success in database
- [ ] Deploy backend code with new API endpoints
- [ ] Deploy frontend code with Voice Library UI
- [ ] Test one business voice selection
- [ ] Test voice in actual phone call
- [ ] Monitor logs for voice selection messages
- [ ] Verify no impact on WhatsApp functionality

## Rollback Plan

If issues occur:
1. Voice selection UI can be hidden without breaking existing functionality
2. All businesses will continue using "ash" (default) if voice_id is NULL
3. No data loss - voice_id column is non-destructive addition
4. To revert UI: Remove Voice Library section from BusinessAISettings.tsx

## Notes

- This feature ONLY affects phone calls via Realtime API
- WhatsApp messages are text-only (no voice)
- Default voice is "ash" (calm conversational male)
- Voice is set once at call start and remains consistent throughout
- Cache optimization: voice_id loaded via CallContext (no extra DB queries during call)
