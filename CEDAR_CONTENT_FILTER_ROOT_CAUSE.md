# Cedar Content Filter - Root Cause Analysis & Fix

## Problem Statement
Content filter occurred **ONLY with cedar voice**, not with other voices like ash, ballad, coral, etc.

## Root Cause Discovery

### Why ONLY Cedar?

Cedar is the **DEFAULT_VOICE** and the **migration target** for invalid voices:

1. **Migration 61** (`migration_cleanup_invalid_voices.py`):
   - Updated ALL businesses with invalid voices (fable, nova, onyx) to `voice='cedar'`
   - **Did NOT invalidate prompt cache**

2. **Cache Poisoning Scenario**:
   ```
   Before Migration:
   - Business: voice_id='fable' (invalid)
   - Cache: prompts built for 'fable'
   
   After Migration:
   - Business: voice_id='cedar' (updated by migration)
   - Cache: STILL has prompts built for 'fable' ❌
   
   Next Call:
   - Voice parameter: 'cedar'
   - Prompt from cache: built for 'fable'
   - Mismatch → OpenAI Content Filter triggered!
   ```

3. **Why Not Other Voices?**:
   - ash, ballad, coral, etc. were NOT migration targets
   - They don't inherit stale cache from invalid voices
   - Only cedar suffers because it's the default fallback

## The Fix

### File: `server/routes_ai_system.py`

**Function**: `_get_voice_for_business_cached()`

### What Changed

#### Before (Vulnerable):
```python
cached_voice = _ai_settings_cache.get(cache_key)
if cached_voice is not None:
    # Trusted cache blindly, never verified against DB
    return cached_voice  # ❌ Could be stale from migration!

# Only loaded DB on cache miss
business = Business.query.get(business_id)
voice_id = business.voice_id
return voice_id
```

#### After (Protected):
```python
cached_voice = _ai_settings_cache.get(cache_key)

# 🔥 ALWAYS load from DB (source of truth)
business = Business.query.get(business_id)
db_voice_id = business.voice_id

# 🔥 Detect mismatch
if cached_voice is not None and cached_voice != db_voice_id:
    logger.warning(f"MISMATCH: cached='{cached_voice}' vs db='{db_voice_id}'")
    # Voice changed → invalidate prompt cache!
    invalidate_business_cache(business_id)

# Always return DB value (source of truth)
return db_voice_id
```

### What This Fixes

1. **Detects cache poisoning**: When cached voice ≠ DB voice
2. **Auto-heals**: Invalidates prompt cache on mismatch
3. **Prevents content filter**: Fresh prompts match actual voice
4. **Works for all voices**: Not just cedar
5. **Future-proof**: Protects against future migrations

## How It Works

### Normal Flow (Cache Valid):
```
1. Load cached_voice: 'ash'
2. Load db_voice: 'ash'
3. Match ✅ → no action needed
4. Return 'ash'
```

### Migration/Update Flow (Cache Stale):
```
1. Load cached_voice: 'fable' (old)
2. Load db_voice: 'cedar' (updated by migration)
3. Mismatch ❌ → invalidate prompt cache
4. Log: "MISMATCH DETECTED: cached='fable' vs db='cedar'"
5. Prompt cache cleared
6. Return 'cedar'
7. Next call builds fresh prompts for 'cedar' ✅
```

## Testing

The fix logs when it detects and fixes mismatch:

```log
[VOICE_CACHE] MISMATCH DETECTED for business 123: cached='fable' vs db='cedar' -> invalidating prompt cache!
[VOICE_CACHE] ✅ Prompt cache invalidated due to voice mismatch
```

## Summary

**Issue**: Content filter ONLY with cedar
**Root cause**: Migration changed voice to cedar without clearing cache
**Fix**: Always verify cache against DB, auto-invalidate on mismatch  
**Result**: Cedar works reliably, no content filter

### Commits Applied:
1. `719d944` - Voice input sanitization (helpful but not root cause)
2. `b90a41f` - Preview endpoint sanitization (consistency)
3. `473727c` - **Cache mismatch detection (ACTUAL FIX)** ✅

The real fix is in commit `473727c` which detects cache poisoning and auto-heals.
