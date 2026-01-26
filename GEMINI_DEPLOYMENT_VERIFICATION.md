# Gemini Initialization Fix - Deployment Verification Checklist

## Pre-Deployment Checks ✅

- [x] Code changes reviewed and approved
- [x] Security scan passed (0 alerts)
- [x] Code review comments addressed
- [x] Tests created for verification
- [x] Documentation created

## Post-Deployment Verification

### 1. Container Boot Logs - Verify Initialization

**Command to check logs:**
```bash
# For prosaas-calls container
docker logs prosaas-calls | grep -A 10 "Warming up Google clients"

# Or with docker-compose
docker-compose logs calls | grep -A 10 "Warming up Google clients"
```

**✅ Expected Output (with GEMINI_API_KEY set):**
```
🔥 Warming up Google clients...
  🚫 Google STT client SKIPPED (DISABLE_GOOGLE=true)
  ✅ GEMINI_LLM_INIT_OK - Client initialized and ready
  ✅ GEMINI_TTS_INIT_OK - Client initialized and ready
🔥 GEMINI_INIT_OK - All Gemini clients ready for use
🔥 Google clients warmup complete
```

**❌ Should NOT see:**
- "Gemini client initialization failed" (unless API key actually missing)
- Any RuntimeError during warmup (unless API key actually missing)

**⚠️ Alternative (without GEMINI_API_KEY):**
```
🔥 Warming up Google clients...
  🚫 Google STT client SKIPPED (DISABLE_GOOGLE=true)
  ⚠️ Gemini LLM client not available: Gemini client initialization failed: GEMINI_API_KEY environment variable not set...
  ⚠️ Gemini TTS client not available: Gemini TTS client initialization failed: GEMINI_API_KEY environment variable not set...
🔥 GEMINI_INIT_SKIP - No Gemini clients initialized (API key not set)
🔥 Google clients warmup complete
```
This is OK - server starts normally, OpenAI businesses work fine.

### 2. During Conversation - Verify No Lazy Loading

**Command to monitor live logs:**
```bash
# Monitor logs during a test call
docker logs -f prosaas-calls | grep -i "gemini"
```

**✅ Expected:**
- Only API call logs (e.g., "Using Gemini LLM for business=X")
- Response processing logs
- No initialization messages

**❌ Should NEVER see during conversation:**
- "Gemini client (singleton) ready"
- "Creating/initializing Gemini client"
- "Lazy load Gemini client"
- Any client initialization logs

### 3. Test Scenarios

#### Scenario A: Gemini Business Makes Call

**Setup:**
1. Business with `ai_provider='gemini'`
2. GEMINI_API_KEY is set
3. Make a test call

**Expected Result:**
```
[AI_SERVICE] Business 123 uses provider: gemini
[LIVE_CALL][CHAT] Using Gemini LLM (singleton) for business=123
✅ GEMINI_SUCCESS: 0.543s
```

**Verify:**
- Call completes successfully
- No initialization logs during call
- Response time reasonable (<2s)

#### Scenario B: OpenAI Business Makes Call

**Setup:**
1. Business with `ai_provider='openai'` (or NULL)
2. Make a test call

**Expected Result:**
```
[AI_SERVICE] Business 456 uses provider: openai
[AI_SERVICE] Using OpenAI LLM for business 456
✅ OPENAI_SUCCESS: 0.234s
```

**Verify:**
- Call completes successfully
- No Gemini-related logs
- OpenAI works normally

#### Scenario C: Gemini Business Without API Key

**Setup:**
1. Business with `ai_provider='gemini'`
2. GEMINI_API_KEY is NOT set (or removed from environment)
3. Make a test call

**Expected Result:**
```
[AI_SERVICE] Business 789 uses provider: gemini
❌ Gemini LLM client not available. This should have been initialized at service startup...
```

**Verify:**
- Call fails immediately with clear error
- Error message points to check logs and API key
- No "NoneType" errors

### 4. Log Analysis - Summary Check

**Command:**
```bash
# Count initialization logs AFTER boot
docker logs prosaas-calls | grep -c "singleton ready"

# Should be 0 (or only appear during boot sequence)
```

**✅ Expected:** 0 occurrences after boot complete

**Command:**
```bash
# Check for any NoneType errors
docker logs prosaas-calls | grep -i "nonetype"

# Should be empty
```

**✅ Expected:** No NoneType errors

## Troubleshooting

### Issue: "GEMINI_INIT_OK" not in logs

**Possible Causes:**
1. GEMINI_API_KEY not set in environment
2. API key is invalid/placeholder
3. Network issue preventing initialization

**Check:**
```bash
# Verify API key is set
docker exec prosaas-calls env | grep GEMINI_API_KEY

# Should show: GEMINI_API_KEY=AIza...
```

**Solution:**
- Ensure API key is set in `.env` file or environment
- Restart container after setting API key

### Issue: Calls still fail with NoneType

**Possible Causes:**
1. Old code still deployed
2. Container not restarted
3. Different issue (not initialization related)

**Check:**
```bash
# Verify fix is deployed - check for new log format
docker logs prosaas-calls | grep "GEMINI_LLM_INIT_OK"

# If not found, fix not deployed yet
```

**Solution:**
- Rebuild and restart container
- Check git branch is correct

### Issue: "singleton ready" still appears during calls

**This means:**
- Old code still deployed OR
- Different code path initializing client

**Check:**
```bash
# Get line number and context
docker logs prosaas-calls | grep -n "singleton ready"
```

**Solution:**
- Verify deployment completed successfully
- Check if there are other code paths creating clients

## Success Criteria ✅

After deployment, all of these should be true:

- [ ] Boot logs show "GEMINI_INIT_OK" (if API key set)
- [ ] No initialization logs during conversations
- [ ] No NoneType errors in logs
- [ ] Gemini businesses make successful calls
- [ ] OpenAI businesses unaffected
- [ ] Clear error message if Gemini unavailable

## Rollback Plan

If issues occur:

```bash
# Revert to previous version
git revert <commit-hash>

# Rebuild and restart
docker-compose build calls
docker-compose restart calls
```

Or temporarily disable Gemini for affected businesses:
```sql
-- Revert businesses to OpenAI
UPDATE business SET ai_provider = 'openai' WHERE ai_provider = 'gemini';
```

## Contact

If verification fails or issues occur:
1. Check troubleshooting section above
2. Review logs for specific error messages
3. Check GEMINI_API_KEY is correctly set
4. Verify container has latest code

## File Changes Summary

**Modified:**
- `server/services/ai_service.py` - Eager initialization
- `server/services/providers/google_clients.py` - Enhanced logging

**New:**
- `test_gemini_init_fix.py` - Test suite
- `GEMINI_INIT_FIX_SUMMARY.md` - Implementation summary
- `GEMINI_DEPLOYMENT_VERIFICATION.md` - This file

**Not Modified (confirmed OK):**
- `server/services/tts_provider.py` - Already using singleton
- `server/routes_live_call.py` - Already using singleton
- `server/app_factory.py` - Already calling warmup
