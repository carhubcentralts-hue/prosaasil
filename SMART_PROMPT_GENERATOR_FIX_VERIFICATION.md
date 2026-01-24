# Smart Prompt Generator Fix - Verification Guide

## Quick Verification Checklist

### 1. Code Changes ✅
- [x] `server/routes_smart_prompt_generator.py` modified
- [x] Enhanced GENERATOR_SYSTEM_PROMPT with critical rules
- [x] Added timeout, retry logic, and constants
- [x] Removed Gemini provider option
- [x] Quality gate converted from error to warning
- [x] Documentation created (SMART_PROMPT_GENERATOR_FIX_SUMMARY.md)

### 2. Security Check ✅
- [x] CodeQL analysis: 0 alerts found
- [x] No security vulnerabilities introduced
- [x] API key validation added

### 3. Code Quality ✅
- [x] Code review completed
- [x] All review comments addressed
- [x] Named constants for configuration
- [x] Clean error handling
- [x] Proper logging

## Manual Testing Steps

### Test 1: Minimal Data (Required Only)
```bash
curl -X POST http://localhost:5000/api/ai/smart_prompt_generator/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "questionnaire": {
      "business_name": "Test Business",
      "business_type": "Service",
      "main_goal": "מידע",
      "conversation_style": "מקצועי"
    }
  }'
```

**Expected Result:**
- Status: 200 OK
- Response contains `prompt_text` with placeholders
- Response contains `"provider": "openai"`
- Response contains `"success": true`
- May contain `quality_warning` field (acceptable)

### Test 2: Missing API Key
```bash
# Temporarily unset or remove OPENAI_API_KEY
unset OPENAI_API_KEY
# Then restart server and make same request
```

**Expected Result:**
- Status: 503 Service Unavailable
- Response contains error about missing OPENAI_API_KEY
- Clear error message in Hebrew and English

### Test 3: Complete Data
```bash
curl -X POST http://localhost:5000/api/ai/smart_prompt_generator/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "questionnaire": {
      "business_name": "קליניקת אסתטיקה יופי טבעי",
      "business_type": "קליניקת אסתטיקה",
      "target_audience": "נשים בגילאי 25-50",
      "main_goal": "תיאום פגישה",
      "what_is_quality_lead": "לקוח שרוצה להזמין טיפול בשבועיים הקרובים",
      "services": ["בוטוקס", "פילר", "טיפול פנים"],
      "working_hours": "א-ה 09:00-18:00, ו 09:00-13:00",
      "conversation_style": "מקצועי",
      "forbidden_actions": ["הבטחת מחירים", "התחייבות לזמנים"],
      "handoff_rules": "תלונות רציניות או בקשות מורכבות",
      "integrations": ["Google Calendar", "CRM"]
    }
  }'
```

**Expected Result:**
- Status: 200 OK
- Response contains complete, structured prompt
- All 6 sections present (זהות הסוכן, מטרת השיחה, etc.)
- No quality warnings
- `"validation": {"passed": true}`

### Test 4: Verify Logs
```bash
# Check server logs for quality gate handling
grep "quality" /var/log/prosaas/server.log | tail -20
```

**Expected Log Messages:**
- ✅ "Generated prompt has quality issues (returning anyway): ..."  (warning)
- ❌ NOT: "Generated prompt failed quality gate" (should never appear as error)
- ✅ "OpenAI prompt generation completed in X.XXs (attempt N)"
- ✅ "Generating smart prompt with openai for business: ..."

### Test 5: Verify Placeholders
When minimal data is provided, check that generated prompt includes:
- `{{BUSINESS_NAME}}` or similar placeholders
- `{{HOURS}}` for missing working hours
- `{{SERVICES}}` for missing services
- No text like "חסרות שאלות" or "צריך עוד פרטים"

## Integration Testing

### Frontend Changes Needed
If you have a UI for the smart prompt generator:

1. **Remove provider selection**
   - Remove dropdown for selecting OpenAI/Gemini
   - Remove provider configuration inputs

2. **Handle quality warnings**
   ```javascript
   if (response.quality_warning) {
     // Show as informational message, NOT error
     showInfo(response.note || "הפרומפט נוצר בהצלחה - ייתכנו שיפורים אפשריים");
   }
   ```

3. **Handle 503 errors**
   ```javascript
   if (response.status === 503) {
     showError("מחולל הפרומפטים דורש הגדרת OpenAI API Key");
   }
   ```

## Performance Verification

### Expected Timings
- Normal generation: 2-8 seconds
- With retry: up to 16 seconds (8s + 8s)
- Timeout after: 12 seconds per attempt

### Log Analysis
```bash
# Find slow generations
grep "OpenAI prompt generation completed" /var/log/prosaas/server.log | grep -E "[89]\.[0-9]{2}s|1[0-2]\.[0-9]{2}s"

# Find retries
grep "OpenAI call failed.*retrying" /var/log/prosaas/server.log
```

## Monitoring Recommendations

### Alerts to Set Up

1. **High 503 Error Rate**
   - Indicates OPENAI_API_KEY issues
   - Alert if > 5% of requests return 503

2. **High Quality Warning Rate**
   - Monitor `quality_warning` field in responses
   - Alert if > 20% of prompts have quality issues

3. **Slow Generation**
   - Alert if average generation time > 10 seconds
   - May indicate OpenAI API slowness

4. **Retry Rate**
   - Monitor "retrying" log messages
   - Alert if > 10% of requests need retry

## Rollback Procedure

If critical issues arise:

```bash
# 1. Checkout previous working version
git checkout 952446b  # commit before this fix

# 2. Rebuild and deploy
./rebuild_frontend.sh
./build_production.sh

# 3. Restart services
docker-compose restart backend

# 4. Verify rollback
curl http://localhost:5000/api/ai/smart_prompt_generator/providers
# Should show both OpenAI and Gemini again
```

## Success Criteria

All of the following must be true:

- [ ] Generate endpoint returns 200 for minimal data
- [ ] Generate endpoint returns 503 when API key missing
- [ ] Logs show warnings, not errors, for quality issues
- [ ] No 422 errors returned from generator
- [ ] Generated prompts include placeholders when data missing
- [ ] No "חסרות שאלות" text in any generated prompt
- [ ] Only OpenAI provider shown in providers endpoint
- [ ] CodeQL security scan passes
- [ ] Average generation time < 8 seconds

## Contact & Support

For issues or questions:
1. Check logs: `/var/log/prosaas/server.log`
2. Review documentation: `SMART_PROMPT_GENERATOR_FIX_SUMMARY.md`
3. Check git history: `git log --oneline server/routes_smart_prompt_generator.py`

## Commits in This Fix

1. `b631901` - Main fix: OpenAI only, no quality gate failures, best-effort generation
2. `f21e2d3` - Code review: move imports to top, use named constants for retry logic
