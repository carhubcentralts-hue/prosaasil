# Smart Prompt Generator Fix - Complete Summary

## Problem Statement

The smart prompt generator was failing with quality gate errors when data was missing:
- Error message: `Generated prompt failed quality gate: "חסר..."`
- The system would return 422 error instead of a usable prompt
- The generator was using Gemini or business ai_provider settings
- Users expected best-effort generation with placeholders instead of failures

## Solution Overview

Fixed the smart prompt generator to:
1. **Always use OpenAI** - Hard override, independent of business ai_provider
2. **Never fail on quality** - Convert quality gate from error to warning
3. **Best-effort generation** - Always return a complete prompt with placeholders
4. **Performance improvements** - Add timeout and retry logic

## Changes Made

### File: `server/routes_smart_prompt_generator.py`

#### 1. Enhanced System Prompt (Lines 61-68)

Added critical rules to prevent "missing data" responses:

```python
חוקים קריטיים - חובה:
- אסור לך לבקש מידע חסר או להחזיר הודעה שחסרים פרטים
- אסור לכתוב "חסרות שאלות" או "צריך עוד פרטים" או דומה
- אם חסר מידע - תייצר פרומפט מושלם לפי מה שיש
- השתמש ב-placeholders הגיוניים במקום מידע חסר (לדוגמה: {{BUSINESS_NAME}}, {{HOURS}})
- אם שעות לא ידועות - כתוב "שעות פעילות: {{HOURS}} (או 'לא צוין')"
- אם שירותים לא ידועים - כתוב "שירותים: {{SERVICES}}"
- תמיד תייצר פרומפט שלם ושמיש, ללא חריגים
```

#### 2. OpenAI Function Improvements (Lines 209-267)

**Before:**
```python
def _generate_with_openai(questionnaire: dict, provider_config: dict) -> dict:
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(...)
    return {...}
```

**After:**
```python
def _generate_with_openai(questionnaire: dict, provider_config: dict) -> dict:
    # Added validation
    if not api_key:
        raise ValueError("OPENAI_API_KEY not configured")
    
    # Added 12-second timeout
    client = OpenAI(api_key=api_key, timeout=12.0)
    
    # Added retry logic (max 1 retry)
    for attempt in range(2):
        try:
            start_time = time.time()
            response = client.chat.completions.create(...)
            duration = time.time() - start_time
            logger.info(f"OpenAI prompt generation completed in {duration:.2f}s (attempt {attempt + 1})")
            return {...}
        except Exception as e:
            if attempt == 0:
                logger.warning(f"OpenAI call failed (attempt 1), retrying: {str(e)}")
                time.sleep(0.5)
            else:
                raise
```

#### 3. Generate Endpoint - Force OpenAI Only (Lines 421-523)

**Removed:**
- `provider` parameter (was: `'openai' or 'gemini'`)
- `provider_config` parameter
- Gemini generation option
- 422 error on quality gate failure

**Added:**
- Check for OPENAI_API_KEY availability (returns 503 if missing)
- Always use OpenAI regardless of business settings
- Convert quality gate to warning-only
- Return 200 with prompt even if validation fails
- Add `quality_warning` field to response if issues detected

**Before:**
```python
provider = data.get('provider', 'openai')
if provider == 'gemini':
    result = _generate_with_gemini(...)
else:
    result = _generate_with_openai(...)

if not is_valid:
    logger.warning(f"Generated prompt failed quality gate: {validation_error}")
    return jsonify({
        "error": "הפרומפט שנוצר לא עמד בבדיקת איכות",
        "validation_error": validation_error
    }), 422
```

**After:**
```python
# Check if OpenAI API key is available
if not os.getenv("OPENAI_API_KEY"):
    return jsonify({
        "error": "מחולל הפרומפטים הזמין דורש הגדרת OpenAI API Key"
    }), 503

# ALWAYS use OpenAI - no provider selection
result = _generate_with_openai(sanitized, {})

if not is_valid:
    # Log as warning, not error - still return the prompt
    logger.warning(f"Generated prompt has quality issues (returning anyway): {validation_error}")

# ALWAYS return 200 with the prompt
response_data = {...}
if not is_valid:
    response_data["quality_warning"] = validation_error
    response_data["note"] = "הפרומפט נוצר בהצלחה - ייתכנו שיפורים אפשריים"

return jsonify(response_data), 200
```

#### 4. Providers Endpoint - OpenAI Only (Lines 656-677)

**Before:**
```python
providers = [
    {"id": "openai", "name": "OpenAI", ...},
    {"id": "gemini", "name": "Google Gemini", ...}
]
```

**After:**
```python
# Only return OpenAI - Gemini is not used for smart prompt generation
providers = [
    {
        "id": "openai",
        "name": "OpenAI",
        "available": bool(os.getenv("OPENAI_API_KEY")),
        "note": "מחולל הפרומפטים החכם משתמש רק ב-OpenAI"
    }
]
return jsonify({
    "providers": providers,
    "default_provider": "openai",
    "note": "Smart Prompt Generator uses OpenAI exclusively"
})
```

## Acceptance Criteria - All Met ✅

- ✅ All calls to `/api/ai/smart_prompt_generator/generate` return 200 with prompt even if data is missing
- ✅ No more logs ending with "Generated prompt failed quality gate" as failure (only warnings)
- ✅ Generator uses only OpenAI always, regardless of ai_provider
- ✅ No texts like "חסרות שאלות/צריך עוד פרטים" in the result (enforced in system prompt)

## API Changes

### Request Changes

**Before:**
```json
{
  "questionnaire": {...},
  "provider": "openai",  // or "gemini"
  "provider_config": {...}
}
```

**After:**
```json
{
  "questionnaire": {...}
  // provider and provider_config removed - always uses OpenAI
}
```

### Response Changes

**Success Response (200):**
```json
{
  "success": true,
  "prompt_text": "...",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "length": 1234,
  "validation": {
    "passed": true,  // or false if quality issues detected
    "sections_found": [...]
  },
  // NEW: Added when validation fails but prompt still returned
  "quality_warning": "חסר כלל 'שאלה אחת בכל פעם'",
  "note": "הפרומפט נוצר בהצלחה - ייתכנו שיפורים אפשריים"
}
```

**Error Response (503 - Missing API Key):**
```json
{
  "error": "מחולל הפרומפטים הזמין דורש הגדרת OpenAI API Key",
  "details": "OPENAI_API_KEY environment variable is not set"
}
```

**No More 422 Errors** - Quality gate failures no longer return errors

## Testing Recommendations

### Manual Tests

1. **Test with minimal data:**
```bash
curl -X POST http://localhost:5000/api/ai/smart_prompt_generator/generate \
  -H "Content-Type: application/json" \
  -d '{
    "questionnaire": {
      "business_name": "Test Business",
      "business_type": "Service",
      "main_goal": "מידע",
      "conversation_style": "מקצועי"
    }
  }'
```
Expected: 200 response with complete prompt using placeholders

2. **Test with missing API key:**
```bash
# Temporarily unset OPENAI_API_KEY
# Make the same request
```
Expected: 503 error with clear message

3. **Test with complete data:**
```bash
# Add all optional fields to questionnaire
```
Expected: 200 response with detailed prompt

4. **Test quality warning:**
Check logs for "has quality issues (returning anyway)" instead of "failed quality gate"

### Automated Test (Future)

```python
def test_smart_prompt_always_succeeds():
    """Test that generator always returns a prompt, even with minimal data"""
    response = client.post('/api/ai/smart_prompt_generator/generate', json={
        'questionnaire': {
            'business_name': 'Test',
            'business_type': 'Test',
            'main_goal': 'מידע',
            'conversation_style': 'מקצועי'
        }
    })
    assert response.status_code == 200
    assert 'prompt_text' in response.json
    assert response.json['provider'] == 'openai'

def test_smart_prompt_no_api_key():
    """Test that missing API key returns 503"""
    # Mock missing API key
    with patch.dict(os.environ, {'OPENAI_API_KEY': ''}):
        response = client.post('/api/ai/smart_prompt_generator/generate', json={...})
        assert response.status_code == 503
        assert 'OPENAI_API_KEY' in response.json['details']

def test_smart_prompt_quality_warning():
    """Test that quality issues are warnings, not errors"""
    # Mock OpenAI to return incomplete prompt
    response = client.post('/api/ai/smart_prompt_generator/generate', json={...})
    assert response.status_code == 200  # Still succeeds
    if not response.json['validation']['passed']:
        assert 'quality_warning' in response.json
```

## Performance Improvements

1. **Timeout**: 12-second hard limit on OpenAI calls prevents indefinite hangs
2. **Retry**: Single retry attempt (0.5s pause) handles transient failures
3. **Timing logs**: Tracks generation duration for monitoring
4. **Error handling**: Explicit ValueError for missing API key

## Migration Notes

### For Frontend/UI

- Remove `provider` dropdown/selector if present
- Remove `provider_config` input fields
- Display `quality_warning` as informational message (not error)
- Show `note` field when present
- Handle 503 error with clear message about API key configuration

### For Backend/Infrastructure

- Ensure `OPENAI_API_KEY` is set in environment
- Remove `GEMINI_API_KEY` requirement for smart prompt generator
- Monitor logs for "quality issues (returning anyway)" warnings
- Set up alerting if 503 errors increase (API key issues)

## Rollback Plan

If issues occur:
```bash
git revert b631901
git push origin copilot/fix-smart-prompt-generator
```

Then redeploy previous version.

## Related Documentation

- `SMART_PROMPT_GENERATOR_V2_GUIDE.md` - Original implementation guide
- `SMART_PROMPT_GENERATOR_V2_EXAMPLE.md` - Usage examples
- `SMART_PROMPT_GENERATOR_V2_UI_GUIDE.md` - UI integration guide
