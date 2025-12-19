# Deployment Guide - Post-Call Pipeline Fix (Migration #38 + ffmpeg)
# ====================================================================

## Quick Reference

**What:** Fix post-call pipeline errors + add ffmpeg for perfect transcription
**Migration:** #38 (adds recording_sid column) - SAFE, idempotent
**Breaking Changes:** NONE
**Rollback:** Simple (code revert only, keep migration)

---

## 🚀 Deployment in 3 Steps

### Step 1: Rebuild Backend with ffmpeg

```bash
docker-compose build backend
docker-compose up -d backend
```

**Verify ffmpeg:**
```bash
docker exec -it prosaas-backend ffmpeg -version
# Should show: ffmpeg version 4.x or 5.x
```

### Step 2: Run Migration

Migration runs automatically on startup, or manually:

```bash
docker exec -it prosaas-backend python -m server.db_migrate
```

**Verify migration:**
```sql
SELECT column_name FROM information_schema.columns 
WHERE table_name='call_log' AND column_name='recording_sid';
-- Should return 1 row
```

### Step 3: Smoke Test

Make a test call, then:

```bash
docker exec -it prosaas-backend python verify_post_call_pipeline.py
```

**Expected:** 5/5 critical checks pass ✅

---

## 📋 Detailed Checklist

### Pre-Deployment
- [ ] Backup database
- [ ] Review PR changes
- [ ] Understand fixes (see POST_CALL_PIPELINE_FIX_SUMMARY.md)

### Deployment
- [ ] Pull latest code
- [ ] Rebuild backend container (for ffmpeg)
- [ ] Verify ffmpeg installed
- [ ] Run/verify migration #38
- [ ] Check logs for startup errors

### Post-Deployment
- [ ] Run verification script
- [ ] Make test inbound call
- [ ] Check database (recording_sid populated)
- [ ] Verify no historical errors appear

---

## 🔍 Verification Commands

**Check migration:**
```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name='call_log' AND column_name='recording_sid';
```

**Check recent calls:**
```sql
SELECT call_sid, recording_sid, LENGTH(final_transcript) as transcript_chars
FROM call_log ORDER BY created_at DESC LIMIT 3;
```

**Check for errors (should be empty):**
```bash
docker logs prosaas-backend --since 1h | grep -E "(UndefinedColumn|property.*ilike|websocket.close.*ASGI)"
```

---

## ✅ Success Criteria

After test call, verify in logs:
```
✅ Recording started for CA...: RE...
✅ [FINALIZE] Saved recording_sid: RE...
✅ [OFFLINE_STT] Audio converted to optimal format (WAV 16kHz mono)
✅ [OFFLINE_STT] Transcript obtained: XXX chars
```

And in database:
- `recording_sid` = RE... (not NULL)
- `recording_url` = https://... (not NULL)
- `final_transcript` has content (> 0 chars)

---

## 🛟 Troubleshooting

**ffmpeg not found:**
```bash
# Check Dockerfile.backend has: ffmpeg \
cat Dockerfile.backend | grep ffmpeg
# Rebuild: docker-compose build --no-cache backend
```

**Migration error:**
```bash
# Check if column already exists (OK to skip)
docker exec -it prosaas-backend python -c "from server.db_migrate import check_column_exists; print(check_column_exists('call_log', 'recording_sid'))"
```

**recording_sid still NULL:**
- Verify migration ran
- Check code deployed (git log)
- Make NEW test call (old calls won't have it)

---

## 📚 Full Documentation

- `VERIFICATION_GUIDE.md` - Complete testing guide
- `POST_CALL_PIPELINE_FIX_SUMMARY.md` - Technical details
- `verify_post_call_pipeline.py` - Automated checks

---

## Status: ✅ Ready for Production

All fixes validated, zero breaking changes, backward compatible.
